// supabase/functions/_shared/memory/types.ts
//
// Canonical types for the Memory Intelligence layer (MVP 02 spec Section 3).
// Mirrors the schema in supabase/migrations/20260822000000_memory_core_schema.sql
// exactly - entities/source_events/citations/contradicted_by are join tables
// in Postgres, assembled into this shape at read time (see loadMemories.ts),
// never stored as raw arrays.

export type MemoryType =
  | "Context" | "Change" | "Commitment" | "Decision"
  | "Rationale" | "Blocker" | "Outcome" | "Requirement" | "CustomerSignal";

export type MemoryStatus =
  | "proposed" | "current" | "stale" | "superseded" | "contradicted" | "unresolved";

export type FreshnessState = "fresh" | "aging" | "stale";

export type EntityType = "Person" | "Team" | "Project" | "Customer" | "Product" | "Topic" | "System";

export interface EntityRef {
  entity_id: string;
  entity_type: EntityType;
  // Added for the Memory Timeline's entity picker - without a display name
  // there's nothing a person can search or click on to pick an entity.
  canonical_name: string;
  // True when this entity has a pending row in unresolved_entities with
  // source_entity_id = this entity (flagged as a possible duplicate after
  // confirmation, not a fresh unconfirmed mention). The picker must never
  // render this identically to a clean, unflagged entity - same rule
  // already applied to memory status badges.
  flagged: boolean;
}

export interface SourceEventRef {
  event_id: string;
  source: string;
  source_id: string;
  url: string | null;
}

export interface Citation {
  source_event: SourceEventRef;
  excerpt_ref: string;
}

export interface PermissionMetadata {
  inherited_from: SourceEventRef[];
  visible_to: string[];
}

// ── Documented payload sub-shapes per type (spec Section 3: "each type
// should have a documented sub-shape - don't leave payload as an untyped
// bag long-term"). Only Commitment and Decision are spec-verbatim; the
// other 7 are inferred from how Sections 9-10 use payload.attribute_key /
// due_date / decision_status / resolved_by_memory_id - flagged in the plan
// as inference, not spec-given. ──────────────────────────────────────────

interface BasePayload {
  attribute_key: string;
}

export interface CommitmentPayload extends BasePayload {
  due_date: string; // ISO 8601
  owner_entity_id: string | null;
  resolved_by_memory_id?: string | null; // Attention strip's hasLinkedOutcome
}

export interface DecisionPayload extends BasePayload {
  decision_status: "proposed" | "decided";
  alternatives_considered: string[];
}

export interface ChangePayload extends BasePayload {
  from_value?: string | null;
  to_value?: string | null;
}

export interface ContextPayload extends BasePayload {
  statement: string;
}

export interface RationalePayload extends BasePayload {
  reasoning: string;
  referenced_change_memory_id?: string | null;
}

export interface BlockerPayload extends BasePayload {
  blocking_what: string;
  resolved_by_memory_id?: string | null;
}

export interface OutcomePayload extends BasePayload {
  resolves_memory_id?: string | null;
}

export interface RequirementPayload extends BasePayload {
  statement: string;
}

export interface CustomerSignalPayload extends BasePayload {
  customer_entity_id: string;
  sentiment?: "positive" | "neutral" | "negative" | null;
}

export type MemoryPayload =
  | CommitmentPayload | DecisionPayload | ChangePayload | ContextPayload
  | RationalePayload | BlockerPayload | OutcomePayload | RequirementPayload
  | CustomerSignalPayload;

export interface CanonicalMemoryObject {
  memory_id: string;
  organization_id: string; // = tenant_id
  type: MemoryType;

  title: string;
  summary: string;
  payload: Record<string, unknown>;

  entities: EntityRef[];

  occurred_at: string;
  valid_from: string;
  valid_until: string | null;
  observed_at: string;

  source_events: SourceEventRef[];
  citations: Citation[];

  confidence: number;
  freshness: FreshnessState; // always computed on read, never stored
  authority: number | null;

  status: MemoryStatus;
  supersedes: string | null;
  // A single sibling id, not an array - memory_conflicts stores one
  // directed pair per conflict (see loadMemories.ts's siblingByMemory,
  // a Map<string,string>), matching the frontend's CanonicalMemory type.
  contradicted_by: string | null;

  permissions: PermissionMetadata;

  embedding: number[];
  searchable_text: string;
}

/** A candidate memory not yet persisted - same shape minus the fields the
 * DB assigns (memory_id, freshness, embedding until computed). */
export type MemoryCandidate = Omit<CanonicalMemoryObject, "memory_id" | "freshness" | "embedding"> & {
  memory_id?: string;
};
