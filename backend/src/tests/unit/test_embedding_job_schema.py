"""
Unit tests for queues.pgmq.schemas.EmbeddingJob.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from queues.pgmq.schemas import EmbeddingJob


class TestValid:
    def test_accepts_tenant_id_and_decision_id(self):
        job = EmbeddingJob(tenant_id=uuid.uuid4(), decision_id=uuid.uuid4())
        assert isinstance(job.tenant_id, uuid.UUID)
        assert isinstance(job.decision_id, uuid.UUID)

    def test_round_trips_through_json(self):
        job = EmbeddingJob(tenant_id=uuid.uuid4(), decision_id=uuid.uuid4())
        dumped = job.model_dump(mode="json")
        restored = EmbeddingJob.model_validate(dumped)
        assert restored == job


class TestRejectsExtraFields:
    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            EmbeddingJob(
                tenant_id=uuid.uuid4(),
                decision_id=uuid.uuid4(),
                searchable_text="never allowed on the wire",
            )


class TestRequiredFields:
    def test_missing_tenant_id_is_rejected(self):
        with pytest.raises(ValidationError):
            EmbeddingJob(decision_id=uuid.uuid4())

    def test_missing_decision_id_is_rejected(self):
        with pytest.raises(ValidationError):
            EmbeddingJob(tenant_id=uuid.uuid4())
