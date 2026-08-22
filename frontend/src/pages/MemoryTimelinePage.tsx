import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ApiError,
  getMemoryEvidence,
  listMemories,
  type CanonicalMemory,
  type MemoryEvidence,
  type MemoryStatus,
  type MemoryType,
} from '../lib/api'
import { getStateAsOf } from '../lib/memoryTemporal'

// Wider status set than MemoryRecordDetail's STATUS_STYLES (Current/
// Superseded only, for the old decisions table) - the memory layer has six
// real states, and superseded/contradicted/unresolved need to read as
// visually distinct from each other, not just "not current", per the plan's
// Checkpoint C requirement.
const STATUS_STYLES: Record<MemoryStatus, string> = {
  proposed: 'bg-[#F3F4F6] text-[#6B7280]',
  current: 'bg-[#EEEBFF] text-[#5A45FF]',
  stale: 'bg-[#FEF3C7] text-[#92400E]',
  superseded: 'bg-[#F3F4F6] text-[#6B7280]',
  contradicted: 'bg-[#FEE2E2] text-[#DC2626]',
  unresolved: 'bg-[#FEE2E2] text-[#DC2626]',
}

const STATUS_LABELS: Record<MemoryStatus, string> = {
  proposed: 'Proposed',
  current: 'Current',
  stale: 'Stale',
  superseded: 'Superseded',
  contradicted: 'Contradicted',
  unresolved: 'Unresolved conflict',
}

const FRESHNESS_STYLES: Record<string, string> = {
  fresh: 'bg-[#ECFCCB] text-[#4D7C0F]',
  aging: 'bg-[#FEF3C7] text-[#92400E]',
  stale: 'bg-[#FEE2E2] text-[#DC2626]',
}

const ALL_TYPES = 'All Types'
const ALL_SOURCES = 'All Sources'
const ALL_STATUSES = 'All Statuses'

type TypeFilter = typeof ALL_TYPES | MemoryType
type SourceFilter = typeof ALL_SOURCES | string
type StatusFilter = typeof ALL_STATUSES | MemoryStatus

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function MemoryCard({
  memory,
  onSelectSibling,
  onOpenEvidence,
}: {
  memory: CanonicalMemory
  onSelectSibling: (memoryId: string) => void
  onOpenEvidence: (memory: CanonicalMemory) => void
}) {
  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-[#EEEBFF] px-2.5 py-1 text-[11px] font-semibold text-[#5A45FF]">
            {memory.type}
          </span>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${STATUS_STYLES[memory.status]}`}>
            {STATUS_LABELS[memory.status]}
          </span>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${FRESHNESS_STYLES[memory.freshness]}`}>
            {memory.freshness}
          </span>
        </div>
        <span className="text-[12px] text-[#9CA3AF]">{formatDate(memory.valid_from)}</span>
      </div>

      <p className="mt-3 text-[15px] font-semibold leading-snug text-[#111827]">{memory.title}</p>
      <p className="mt-1.5 text-[13px] leading-relaxed text-[#374151]">{memory.summary}</p>

      {memory.status === 'unresolved' && memory.contradicted_by ? (
        <button
          type="button"
          onClick={() => onSelectSibling(memory.contradicted_by as string)}
          className="mt-3 rounded-lg border border-[#FECACA] bg-[#FFF7F7] px-3 py-2 text-left text-[12px] font-semibold text-[#B4232C] hover:bg-[#FEF2F2]"
        >
          Conflicts with another memory - view it →
        </button>
      ) : null}

      {memory.supersedes ? (
        <button
          type="button"
          onClick={() => onSelectSibling(memory.supersedes as string)}
          className="mt-3 block text-[12px] font-medium text-[#5A45FF] hover:underline"
        >
          ← Supersedes an earlier memory
        </button>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {memory.entities.map((e) => (
          <span key={e.entity_id} className="rounded-full bg-[#F3F4F6] px-2.5 py-1 text-[11px] text-[#6B7280]">
            {e.canonical_name}
          </span>
        ))}
      </div>

      <button
        type="button"
        onClick={() => onOpenEvidence(memory)}
        className="mt-3 text-[12px] font-semibold text-[#5A45FF] hover:underline"
      >
        View evidence ({memory.source_events.length} source{memory.source_events.length === 1 ? '' : 's'})
      </button>
    </div>
  )
}

function EvidenceDrawer({ memoryId, onClose }: { memoryId: string; onClose: () => void }) {
  const [evidence, setEvidence] = useState<MemoryEvidence | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setEvidence(null)
    setError('')
    getMemoryEvidence(memoryId)
      .then((data) => {
        if (active) setEvidence(data)
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(err instanceof ApiError ? err.message : 'Unable to load evidence for this memory.')
      })
    return () => {
      active = false
    }
  }, [memoryId])

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/20" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" onClick={onClose} className="text-[13px] font-semibold text-[#5A45FF]">
          ← Close
        </button>

        {error ? <p className="mt-4 text-[13px] text-[#DC2626]">{error}</p> : null}
        {!error && !evidence ? <p className="mt-4 text-[13px] text-[#9CA3AF]">Loading…</p> : null}

        {evidence ? (
          <>
            <p className="mt-4 text-[16px] font-semibold text-[#111827]">{evidence.title}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-[#374151]">{evidence.summary}</p>

            <p className="mt-5 text-[11px] font-semibold tracking-[0.06em] text-[#9CA3AF]">
              SOURCE EVENTS ({evidence.source_events.length})
            </p>
            <ul className="mt-2 flex flex-col gap-2">
              {evidence.source_events.map((se) => (
                <li key={se.event_id} className="rounded-lg border border-[#E5E7EB] p-2.5 text-[12px] text-[#374151]">
                  {se.source} · {se.source_id}
                </li>
              ))}
            </ul>

            {evidence.citations.length > 0 ? (
              <>
                <p className="mt-5 text-[11px] font-semibold tracking-[0.06em] text-[#9CA3AF]">CITED EXCERPTS</p>
                <ul className="mt-2 flex flex-col gap-2">
                  {evidence.citations.map((c, i) => (
                    <li key={i} className="rounded-lg border border-[#E5E7EB] p-2.5 text-[12px] text-[#374151]">
                      <span className="font-semibold">{c.source_event.source}</span>: {c.excerpt_ref}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            <p className="mt-5 text-[12px] text-[#9CA3AF]">
              Confidence {(evidence.confidence * 100).toFixed(0)}% · {evidence.freshness}
            </p>
          </>
        ) : null}
      </div>
    </div>
  )
}

export default function MemoryTimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const entityId = searchParams.get('entity') ?? undefined

  const [memories, setMemories] = useState<CanonicalMemory[]>([])
  const [hiddenCount, setHiddenCount] = useState(0)
  const [someContentHidden, setSomeContentHidden] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const [typeFilter, setTypeFilter] = useState<TypeFilter>(ALL_TYPES)
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>(ALL_SOURCES)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(ALL_STATUSES)
  const [pointInTime, setPointInTime] = useState('')
  const [entityQuery, setEntityQuery] = useState('')
  const [evidenceMemoryId, setEvidenceMemoryId] = useState<string | null>(null)

  // One fetch on mount (or when the selected entity changes) - every other
  // filter, and the point-in-time slider, runs client-side over this same
  // list. No network round trip per slider move or filter click.
  useEffect(() => {
    let active = true
    setIsLoading(true)
    setError('')
    listMemories(entityId)
      .then((res) => {
        if (!active) return
        setMemories(res.memories)
        setHiddenCount(res.hidden_count)
        setSomeContentHidden(res.some_content_hidden)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof ApiError ? err.message : 'Unable to load the memory timeline.')
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [entityId])

  const entityOptions = useMemo(() => {
    const byId = new Map<string, string>()
    for (const m of memories) {
      for (const e of m.entities) byId.set(e.entity_id, e.canonical_name)
    }
    return [...byId.entries()]
      .map(([id, name]) => ({ id, name }))
      .filter((e) => e.name.toLowerCase().includes(entityQuery.toLowerCase()))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [memories, entityQuery])

  const selectedEntityName = entityId ? memories.find((m) => m.entities.some((e) => e.entity_id === entityId))?.entities.find((e) => e.entity_id === entityId)?.canonical_name : undefined

  const sourceOptions = useMemo(() => {
    const set = new Set<string>()
    for (const m of memories) for (const se of m.source_events) set.add(se.source)
    return [...set].sort()
  }, [memories])

  const displayedMemories = useMemo(() => {
    let list = memories
    if (entityId && pointInTime) {
      const targetIso = new Date(pointInTime).toISOString()
      list = getStateAsOf(memories, entityId, targetIso)
    }
    return list
      .filter((m) => typeFilter === ALL_TYPES || m.type === typeFilter)
      .filter((m) => sourceFilter === ALL_SOURCES || m.source_events.some((se) => se.source === sourceFilter))
      .filter((m) => statusFilter === ALL_STATUSES || m.status === statusFilter)
      .sort((a, b) => b.valid_from.localeCompare(a.valid_from))
  }, [memories, entityId, pointInTime, typeFilter, sourceFilter, statusFilter])

  const selectEntity = (id: string) => {
    setSearchParams({ entity: id })
    setPointInTime('')
  }

  const selectSibling = (memoryId: string) => {
    const sibling = memories.find((m) => m.memory_id === memoryId)
    if (sibling?.entities[0]) selectEntity(sibling.entities[0].entity_id)
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-[22px] font-bold text-[#111827]">Memory Timeline</h1>
      <p className="mt-1 text-[13px] text-[#6B7280]">
        What your team knows about one thing, reconstructed over time - decisions, changes, blockers, and how they resolved.
      </p>

      {someContentHidden ? (
        <div className="mt-4 rounded-xl border border-[#F5E6C8] bg-[#FFFBF0] p-4 text-[13px] text-[#946C00]">
          Some content isn't shown yet because we can't confirm who has access to it ({hiddenCount} item
          {hiddenCount === 1 ? '' : 's'} hidden). This resolves automatically as real permission checks roll out - it's a
          disclosed limitation, not missing data.
        </div>
      ) : null}

      {!entityId ? (
        <div className="mt-6 rounded-2xl border border-[#E5E7EB] bg-white p-5">
          <p className="text-[13px] font-semibold text-[#111827]">Pick an entity to see its timeline</p>
          <input
            type="text"
            value={entityQuery}
            onChange={(e) => setEntityQuery(e.target.value)}
            placeholder="Search people, projects, customers…"
            className="mt-3 h-10 w-full rounded-full border border-[#E5E7EB] px-4 text-[13px] outline-none placeholder:text-[#9CA3AF] focus:border-[#5A45FF]"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {entityOptions.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => selectEntity(e.id)}
                className="rounded-full border border-[#E5E7EB] bg-white px-3 py-1.5 text-[12px] font-medium text-[#374151] hover:bg-[#F9FAFB]"
              >
                {e.name}
              </button>
            ))}
            {entityOptions.length === 0 && !isLoading ? (
              <p className="text-[13px] text-[#9CA3AF]">No entities found yet.</p>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setSearchParams({})}
            className="rounded-full border border-[#E5E7EB] bg-white px-3 py-1.5 text-[12px] font-semibold text-[#5A45FF] hover:bg-[#F8F7FF]"
          >
            ← Change entity
          </button>
          <span className="text-[15px] font-semibold text-[#111827]">{selectedEntityName ?? entityId}</span>
        </div>
      )}

      {entityId ? (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-[12px] font-semibold text-[#6B7280]">
            As of
            <input
              type="date"
              value={pointInTime}
              onChange={(e) => setPointInTime(e.target.value)}
              className="h-9 rounded-lg border border-[#E5E7EB] px-2 text-[13px] outline-none focus:border-[#5A45FF]"
            />
          </label>
          {pointInTime ? (
            <button
              type="button"
              onClick={() => setPointInTime('')}
              className="text-[12px] font-semibold text-[#5A45FF] hover:underline"
            >
              Back to current state
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
          className="h-9 rounded-lg border border-[#E5E7EB] px-2 text-[12px] text-[#374151]"
        >
          <option value={ALL_TYPES}>{ALL_TYPES}</option>
          {(['Context', 'Change', 'Commitment', 'Decision', 'Rationale', 'Blocker', 'Outcome', 'Requirement', 'CustomerSignal'] as MemoryType[]).map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="h-9 rounded-lg border border-[#E5E7EB] px-2 text-[12px] text-[#374151]"
        >
          <option value={ALL_SOURCES}>{ALL_SOURCES}</option>
          {sourceOptions.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          className="h-9 rounded-lg border border-[#E5E7EB] px-2 text-[12px] text-[#374151]"
        >
          <option value={ALL_STATUSES}>{ALL_STATUSES}</option>
          {(Object.keys(STATUS_LABELS) as MemoryStatus[]).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </div>

      {error ? <p className="mt-6 text-[13px] text-[#DC2626]">{error}</p> : null}
      {isLoading ? <p className="mt-6 text-[13px] text-[#9CA3AF]">Loading…</p> : null}

      {!isLoading && entityId ? (
        <div className="mt-6 flex flex-col gap-3">
          {displayedMemories.length === 0 ? (
            <p className="text-[13px] text-[#9CA3AF]">No memories match these filters.</p>
          ) : (
            displayedMemories.map((m) => (
              <MemoryCard
                key={m.memory_id}
                memory={m}
                onSelectSibling={selectSibling}
                onOpenEvidence={(mem) => setEvidenceMemoryId(mem.memory_id)}
              />
            ))
          )}
        </div>
      ) : null}

      {evidenceMemoryId ? (
        <EvidenceDrawer memoryId={evidenceMemoryId} onClose={() => setEvidenceMemoryId(null)} />
      ) : null}
    </div>
  )
}
