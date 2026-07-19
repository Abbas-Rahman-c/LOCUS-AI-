"""
Golden Evaluation Dataset for the retrieval/RAG pipeline.

Distinct from modules/ai/evaluation/golden_set/, which scores the
triage+extraction classification stage (Haiku recall vs Sonnet precision on
raw event -> decision extraction). This dataset scores the *retrieval and
answer generation* stage: given a user question, did we find the right
decision records and write a correct, grounded, well-cited answer.

Each example pins down:
  - a representative user question
  - the decision records that SHOULD be retrieved (ground truth relevance)
  - a reference answer summary and the decisions a good answer MUST cite

Recommended size: 40-80 examples to start, covering a spread of question
types (see `category` below) rather than 150+ narrow variants — retrieval
questions vary more by *pattern* than by wording.
"""
from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuestionCategory(StrEnum):
    """Rough coverage buckets. Not exhaustive — extend as gaps are found."""

    SINGLE_HOP = "single_hop"  # one decision record answers it directly
    MULTI_HOP = "multi_hop"  # requires synthesizing across 2+ records
    TEMPORAL = "temporal"  # "what did we decide most recently about X" / supersession
    NEGATIVE = "negative"  # no relevant decision exists; correct answer is "we haven't decided"
    AMBIGUOUS_ENTITY = "ambiguous_entity"  # entity name collides across workspaces/threads
    PARAPHRASE = "paraphrase"  # phrased far from the source wording (tests embedding recall, not keyword match)


class TranscriptSource(StrEnum):
    """Mirrors modules.ingestion.envelope.schemas.EventSource — kept as a separate
    enum here rather than importing it, so the eval harness has zero import-time
    dependency on the backend's DB/queue-wired modules."""

    SLACK = "slack"
    GMAIL = "gmail"
    NOTION = "notion"


class DistractorType(StrEnum):
    """Why a non-ground-truth decision was deliberately planted alongside the
    real answer. Each type targets a specific way retrieval can go wrong."""

    NONE = "none"  # not a distractor -- a true positive
    SUPERSEDED = "superseded"  # an earlier, now-replaced version of the same decision
    REJECTED_ALTERNATIVE = "rejected_alternative"  # the option that was considered and turned down
    SIMILAR_TOPIC = "similar_topic"  # same domain, different decision -- tests over-broad matching
    CROSS_TENANT = "cross_tenant"  # belongs to a different tenant entirely -- tests permission-scope leakage


class ScenarioDecision(BaseModel):
    """One decision record inside a scenario pack. Field names mirror
    modules.ai.extraction.schemas.ExtractionResult (record_type, status,
    decision_statement, rationale) plus persistence-layer identity so the
    mock/live pipeline can serve it as a candidate."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    tenant_id: UUID
    record_type: str = Field(..., description="decision | action_item | blocker")
    status: str = Field(..., description="proposed | decided | superseded")
    decision_statement: str = Field(..., min_length=1)
    rationale: str | None = None
    source_permalink: str | None = None
    distractor_type: DistractorType = DistractorType.NONE


class ScenarioPack(BaseModel):
    """A synthetic source transcript plus the decision(s) extracted from it.

    This is the unit real authoring happens against: write the transcript the
    way a person actually talks, THEN derive decisions from it -- never the
    reverse. Golden questions (see GoldenExample) are authored from the
    transcript's narrative, not from `decision_statement`'s clean wording, to
    avoid leaking exact-match vocabulary into the eval.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Stable short id, e.g. 'sp-014'.")
    tenant_id: UUID
    source: TranscriptSource
    domain: str = Field(..., description="Free-text topic tag, e.g. 'pricing', 'oncall' -- for coverage reporting.")
    raw_transcript: str = Field(..., min_length=1)
    decisions: list[ScenarioDecision]


class LabelingRecord(BaseModel):
    """Audit trail for the double-label + adjudication process on one
    GoldenExample. `simulated=True` means labeler_a/labeler_b were not
    independent humans yet -- see AUTHORING_GUIDE.md. Replace with real
    labeler identities before treating agreement_rate as a real signal.
    """

    model_config = ConfigDict(extra="forbid")

    labeler_a: str = Field(..., description="Labeler id/role, or 'simulated-a' pending a real reviewer.")
    labeler_b: str = Field(..., description="Labeler id/role, or 'simulated-b' pending a real reviewer.")
    simulated: bool = Field(default=True)
    agreed: bool = Field(..., description="Whether A and B's relevance sets matched before adjudication.")
    adjudicator: str | None = Field(default=None, description="Who broke the tie, if agreed=False.")
    adjudication_note: str | None = Field(
        default=None, description="Why the final label was chosen -- required when agreed=False."
    )

    @model_validator(mode="after")
    def _disagreement_needs_a_reason(self) -> LabelingRecord:
        if not self.agreed and not self.adjudication_note:
            raise ValueError("adjudication_note is required when agreed=False")
        return self


class GoldenExample(BaseModel):
    """One row of the golden evaluation dataset."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Stable short id, e.g. 'ge-014'. Used in reports/diffs.")
    question: str = Field(..., min_length=1)
    tenant_id: UUID
    category: QuestionCategory

    scenario_pack_ids: list[str] = Field(
        default_factory=list,
        description="ScenarioPack ids whose decisions form the candidate pool this question was labeled against.",
    )
    expected_decision_ids: list[UUID] = Field(
        default_factory=list,
        description="Ground-truth relevant decisions, ordered most- to least-relevant. "
        "Empty list is valid and expected for category=negative.",
    )
    expected_citation_ids: list[UUID] = Field(
        default_factory=list,
        description="Subset of expected_decision_ids a correct answer MUST cite. "
        "Usually equal to expected_decision_ids[:1] for single_hop.",
    )
    reference_answer: str = Field(
        ..., min_length=1, description="A correct, human-written reference answer for correctness grading."
    )
    labeling: LabelingRecord | None = Field(
        default=None, description="Double-label/adjudication audit trail. None only for legacy pre-v2 examples."
    )
    notes: str | None = Field(default=None, description="Why this example is in the set / what it's meant to catch.")

    @model_validator(mode="after")
    def _citations_are_subset_of_expected(self) -> GoldenExample:
        expected = set(self.expected_decision_ids)
        cited = set(self.expected_citation_ids)
        if not cited.issubset(expected):
            raise ValueError(
                f"{self.id}: expected_citation_ids {cited - expected} not present in expected_decision_ids"
            )
        return self


class GoldenDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examples: list[GoldenExample]

    @model_validator(mode="after")
    def _unique_ids(self) -> GoldenDataset:
        ids = [ex.id for ex in self.examples]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate golden example ids: {dupes}")
        return self

    def by_category(self, category: QuestionCategory) -> list[GoldenExample]:
        return [ex for ex in self.examples if ex.category == category]

    def coverage_report(self) -> dict[str, int]:
        """Count of examples per category — use this to spot-check the set isn't
        all single_hop before relying on the aggregate metrics."""
        counts = {c.value: 0 for c in QuestionCategory}
        for ex in self.examples:
            counts[ex.category.value] += 1
        return counts


def load_golden_dataset(path: str | Path) -> GoldenDataset:
    """Loads and validates the golden dataset from a JSON fixture.

    Raises pydantic.ValidationError on malformed entries rather than silently
    skipping them — a bad fixture should fail the eval run loudly, not
    quietly shrink the dataset.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return GoldenDataset.model_validate(raw)


def load_scenario_packs(path: str | Path) -> list[ScenarioPack]:
    """Loads and validates scenario packs (transcripts + decisions) from a
    JSON fixture of the form {"scenario_packs": [...]}."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ScenarioPack.model_validate(sp) for sp in raw["scenario_packs"]]
