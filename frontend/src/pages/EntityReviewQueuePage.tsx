import { useEffect, useState } from 'react'
import {
  ApiError,
  confirmNewEntity,
  dismissUnresolvedEntity,
  listUnresolvedEntities,
  mergeEntity,
  searchEntities,
  type EntitySearchResult,
  type ReviewQueueItem,
  type ReviewQueueSide,
} from '../lib/api'

function SideCard({ side, label }: { side: ReviewQueueSide; label: string }) {
  return (
    <div className="flex-1 rounded-xl border border-[#E5E7EB] bg-white p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#9CA3AF]">{label}</p>
      <p className="mt-1 text-[15px] font-semibold text-[#111827]">{side.name}</p>
      {side.snippet ? (
        <p className="mt-2 text-[13px] italic leading-relaxed text-[#4B5563]">&ldquo;{side.snippet}&rdquo;</p>
      ) : (
        <p className="mt-2 text-[13px] text-[#9CA3AF]">No linked memory yet.</p>
      )}
      <p className="mt-3 text-[12px] text-[#9CA3AF]">
        {side.memory_count} {side.memory_count === 1 ? 'memory' : 'memories'}
        {side.sources.length > 0 ? ` · ${side.sources.join(', ')}` : ''}
      </p>
    </div>
  )
}

// Shown when a card has no suggested candidate at all (roughly two-thirds
// of real pending rows - confirmNewEntity only pre-fills a candidate when
// its own re-check found one; a manually-flagged "genuinely ambiguous"
// row never gets one). Without this, those rows were a dead end - the
// only options were two buttons that both just dismissed, with no way to
// say "I found the match myself."
function ManualMatchSearch({ tenantId, onPick }: { tenantId: string; onPick: (result: EntitySearchResult) => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<EntitySearchResult[]>([])
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 2) {
      setResults([])
      return
    }
    let active = true
    setSearching(true)
    const timer = setTimeout(() => {
      searchEntities(trimmed, tenantId)
        .then((res) => {
          if (active) setResults(res.entities)
        })
        .catch(() => {
          if (active) setResults([])
        })
        .finally(() => {
          if (active) setSearching(false)
        })
    }, 250)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [query, tenantId])

  return (
    <div className="flex-1 rounded-xl border border-dashed border-[#E5E7EB] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#9CA3AF]">No suggested match — search for one</p>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search existing entities…"
        className="mt-2 h-9 w-full rounded-lg border border-[#E5E7EB] px-3 text-[13px] outline-none placeholder:text-[#9CA3AF] focus:border-[#5A45FF]"
      />
      {searching ? <p className="mt-2 text-[12px] text-[#9CA3AF]">Searching…</p> : null}
      {!searching && results.length > 0 ? (
        <ul className="mt-2 flex flex-col gap-1">
          {results.map((r) => (
            <li key={r.entity_id}>
              <button
                type="button"
                onClick={() => onPick(r)}
                className="w-full rounded-lg px-2 py-1.5 text-left text-[13px] text-[#374151] hover:bg-[#F8F7FF] hover:text-[#5A45FF]"
              >
                {r.canonical_name} <span className="text-[11px] text-[#9CA3AF]">({r.entity_type})</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {!searching && query.trim().length >= 2 && results.length === 0 ? (
        <p className="mt-2 text-[12px] text-[#9CA3AF]">No matches found.</p>
      ) : null}
    </div>
  )
}

// Internal-only tool, not linked from the customer-facing nav - staff use
// this to inspect extraction/resolution quality across tenants, entering
// whichever tenant_id they want to look at. Left blank, it shows the
// caller's own tenant (harmless if a non-staff account somehow lands on
// this URL - they only ever see their own data; the backend refuses any
// other tenant_id from a non-staff caller). Requesting a different tenant
// requires the caller's email to be on the STAFF_EMAILS backend allowlist.
export default function EntityReviewQueuePage() {
  const [tenantIdInput, setTenantIdInput] = useState('')
  const [activeTenantId, setActiveTenantId] = useState<string | undefined>(undefined)
  const [items, setItems] = useState<ReviewQueueItem[] | null>(null)
  const [index, setIndex] = useState(0)
  const [error, setError] = useState('')
  const [acting, setActing] = useState(false)
  const [actionError, setActionError] = useState('')

  const load = () => {
    setError('')
    setItems(null)
    listUnresolvedEntities(activeTenantId)
      .then((res) => {
        setItems(res.pending)
        setIndex((i) => Math.min(i, Math.max(res.pending.length - 1, 0)))
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : 'Unable to load the review queue.'))
  }

  useEffect(load, [activeTenantId])

  const current = items && items.length > 0 ? items[index] : null

  const advance = () => {
    setItems((prev) => (prev ? prev.filter((_, i) => i !== index) : prev))
    setIndex((i) => Math.max(0, Math.min(i, (items?.length ?? 1) - 2)))
  }

  const runAction = async (fn: () => Promise<unknown>) => {
    if (!current) return
    setActing(true)
    setActionError('')
    try {
      await fn()
      advance()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'That action failed - try again.')
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-[22px] font-bold text-[#111827]">Entity Review Queue</h1>
      <p className="mt-1 text-[13px] text-[#6B7280]">
        Internal only - possible duplicates and unconfirmed mentions flagged by extraction, for checking
        extraction/resolution quality across tenants. Nothing here is customer-facing or required of anyone.
      </p>

      <div className="mt-4 flex items-center gap-2">
        <input
          type="text"
          value={tenantIdInput}
          onChange={(e) => setTenantIdInput(e.target.value)}
          placeholder="tenant_id (blank = your own tenant)"
          className="h-9 flex-1 rounded-lg border border-[#E5E7EB] px-3 text-[12px] font-mono outline-none placeholder:font-sans placeholder:text-[#9CA3AF] focus:border-[#5A45FF]"
        />
        <button
          type="button"
          onClick={() => setActiveTenantId(tenantIdInput.trim() || undefined)}
          className="h-9 shrink-0 rounded-lg border border-[#E5E7EB] px-3 text-[12px] font-semibold text-[#374151] hover:bg-[#F9FAFB]"
        >
          Load
        </button>
      </div>

      {error ? <p className="mt-4 text-[13px] text-[#DC2626]">{error}</p> : null}
      {!error && items === null ? <p className="mt-4 text-[13px] text-[#9CA3AF]">Loading…</p> : null}

      {!error && items && items.length === 0 ? (
        <div className="mt-6 rounded-xl border border-[#E5E7EB] bg-white p-6 text-center">
          <p className="text-[14px] font-semibold text-[#111827]">Nothing pending.</p>
          <p className="mt-1 text-[13px] text-[#9CA3AF]">The queue is clear.</p>
        </div>
      ) : current ? (
        <div className="mt-6">
          <p className="text-[11px] font-semibold tracking-[0.06em] text-[#9CA3AF]">
            {current.kind === 'confirmed_duplicate' ? 'POSSIBLE DUPLICATE' : 'UNCONFIRMED MENTION'} · {current.left.entity_type} ·{' '}
            {index + 1} of {items?.length ?? 0}
          </p>

          <div className="mt-3 flex flex-col gap-3 sm:flex-row">
            <SideCard side={current.left} label={current.kind === 'confirmed_duplicate' ? 'Flagged entity' : 'New mention'} />
            {current.right ? (
              <SideCard side={current.right} label="Possible match" />
            ) : (
              <ManualMatchSearch
                tenantId={activeTenantId ?? ''}
                onPick={(result) => void runAction(() => mergeEntity(current.id, result.entity_id, activeTenantId))}
              />
            )}
          </div>

          {actionError ? <p className="mt-3 text-[12px] text-[#DC2626]">{actionError}</p> : null}

          <div className="mt-4 flex flex-wrap gap-2">
            {current.kind === 'confirmed_duplicate' && current.right ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => mergeEntity(current.id, current.right!.entity_id as string, activeTenantId))}
                className="rounded-full bg-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#4C39E0] disabled:opacity-50"
              >
                Merge into {current.right.name}
              </button>
            ) : null}
            {current.kind === 'raw_mention' && current.right ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => mergeEntity(current.id, current.right!.entity_id as string, activeTenantId))}
                className="rounded-full bg-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#4C39E0] disabled:opacity-50"
              >
                Merge into {current.right.name}
              </button>
            ) : null}
            {current.kind === 'raw_mention' ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => confirmNewEntity(current.id, activeTenantId))}
                className="rounded-full border border-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-[#5A45FF] hover:bg-[#F8F7FF] disabled:opacity-50"
              >
                Confirm as new
              </button>
            ) : null}
            {/* "Keep separate" only makes sense when there's a specific
                candidate to be separate FROM - with no suggested match,
                it's just a second dismiss button next to "Skip for now"
                doing the exact same thing. */}
            {current.right ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => dismissUnresolvedEntity(current.id, activeTenantId))}
                className="rounded-full border border-[#E5E7EB] px-4 py-2 text-[13px] font-semibold text-[#374151] hover:bg-[#F9FAFB] disabled:opacity-50"
              >
                Keep separate
              </button>
            ) : null}
            <button
              type="button"
              disabled={acting}
              onClick={() => void runAction(() => dismissUnresolvedEntity(current.id, activeTenantId))}
              className="rounded-full border border-[#E5E7EB] px-4 py-2 text-[13px] font-semibold text-[#374151] hover:bg-[#F9FAFB] disabled:opacity-50"
            >
              Skip for now
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
