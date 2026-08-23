import { useEffect, useState } from 'react'
import {
  ApiError,
  dismissUnresolvedEntity,
  listAttentionItems,
  mergeEntity,
  resolveMemory,
  type AttentionCategory,
  type AttentionItem,
} from '../lib/api'

// Spec Section 10: collapsible, collapsed by default - this replaces a
// generic "what changed" feed with a short, ranked list of only the items
// that need an actual decision. Never a hollow container: renders nothing
// substantial until it's confirmed there's something (or confirmed there
// isn't).

const CATEGORY_LABEL: Record<AttentionCategory, string> = {
  conflict: 'Conflict',
  decision: 'Awaiting confirmation',
  commitment: 'Overdue commitment',
  staleness: 'Aging',
}

const CATEGORY_STYLE: Record<AttentionCategory, string> = {
  conflict: 'bg-[#FEE2E2] text-[#DC2626]',
  decision: 'bg-[#EEEBFF] text-[#5A45FF]',
  commitment: 'bg-[#FEF3C7] text-[#92400E]',
  staleness: 'bg-[#F3F4F6] text-[#6B7280]',
}

// Possible duplicate found via the judgment tier - genuinely ambiguous
// after both similarity AND a real model call, not the common case.
// Reuses this same card shape and the same merge/dismiss mutations the
// internal review-queue page calls - no separate action path.
function EntityDuplicateCard({ item, onResolved }: { item: Extract<AttentionItem, { kind: 'entity_duplicate' }>; onResolved: () => void }) {
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const act = async (fn: () => Promise<unknown>) => {
    setActing(true)
    setError('')
    try {
      await fn()
      onResolved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to act on this item.')
      setActing(false)
    }
  }

  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-[#E5E7EB] bg-white p-4">
      <div className="min-w-0">
        <span className="inline-flex rounded-full bg-[#F3F4F6] px-2.5 py-1 text-[11px] font-semibold text-[#6B7280]">
          Possible duplicate
        </span>
        <p className="mt-2 text-[14px] font-semibold text-[#111827]">{item.mention_text}</p>
        <p className="mt-0.5 text-[13px] text-[#6B7280]">Might be the same as “{item.candidate_name}”</p>
        {error ? <p className="mt-1 text-[12px] text-[#DC2626]">{error}</p> : null}
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          disabled={acting}
          onClick={() => void act(() => dismissUnresolvedEntity(item.unresolved_id))}
          className="rounded-lg border border-[#E5E7EB] px-3 py-2 text-[12px] font-semibold text-[#374151] hover:bg-[#F9FAFB] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Keep separate
        </button>
        <button
          type="button"
          disabled={acting}
          onClick={() => void act(() => mergeEntity(item.unresolved_id, item.candidate_entity_id))}
          className="rounded-lg bg-[#5A45FF] px-3.5 py-2 text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {acting ? '...' : `Merge`}
        </button>
      </div>
    </div>
  )
}

// Matches the action enum names exactly - "Resolve / Confirm / Check in /
// Recheck" per spec, one button label per category.
const ACTION_LABEL: Record<AttentionCategory, string> = {
  conflict: 'Resolve',
  decision: 'Confirm',
  commitment: 'Check in',
  staleness: 'Recheck',
}

function AttentionCard({ item, onResolved }: { item: Extract<AttentionItem, { kind: 'memory' }>; onResolved: () => void }) {
  const [resolving, setResolving] = useState(false)
  const [error, setError] = useState('')

  const handleResolve = async () => {
    setResolving(true)
    setError('')
    try {
      // The SAME mutation Memory Timeline uses - never a client-side-only
      // dismiss. The card only leaves the list because a refetch shows the
      // server no longer considers it attention-worthy, not because this
      // click removed it locally.
      await resolveMemory(item.memory_id, item.action)
      onResolved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to resolve this item.')
      setResolving(false)
    }
  }

  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-[#E5E7EB] bg-white p-4">
      <div className="min-w-0">
        <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${CATEGORY_STYLE[item.category]}`}>
          {CATEGORY_LABEL[item.category]}
        </span>
        <p className="mt-2 truncate text-[14px] font-semibold text-[#111827]">{item.title}</p>
        <p className="mt-0.5 line-clamp-2 text-[13px] text-[#6B7280]">{item.summary}</p>
        {error ? <p className="mt-1 text-[12px] text-[#DC2626]">{error}</p> : null}
      </div>
      <button
        type="button"
        onClick={() => void handleResolve()}
        disabled={resolving}
        className="shrink-0 rounded-lg bg-[#5A45FF] px-3.5 py-2 text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {resolving ? '...' : ACTION_LABEL[item.category]}
      </button>
    </div>
  )
}

export function AttentionStrip() {
  const [items, setItems] = useState<AttentionItem[]>([])
  const [total, setTotal] = useState<number | null>(null) // null = not loaded yet
  const [expanded, setExpanded] = useState(false)

  const load = () => {
    listAttentionItems(4)
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
      })
      .catch(() => {
        // Fails quiet - the Attention strip is a convenience surface above
        // search, not something that should show an error banner on the
        // dashboard if memory-api has a hiccup.
        setTotal(0)
      })
  }

  useEffect(() => {
    load()
  }, [])

  if (total === null) return null // still loading - render nothing, not a placeholder box
  if (total === 0) {
    return <p className="mb-5 text-[13px] text-[#9CA3AF]">You're caught up - nothing needs attention right now.</p>
  }

  return (
    <div className="mb-5 rounded-2xl border border-[#E5E7EB] bg-white">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left"
      >
        <span className="text-[14px] font-semibold text-[#111827]">
          Needs attention <span className="text-[#9CA3AF] font-normal">({total})</span>
        </span>
        <span className="text-[12px] text-[#5A45FF]">{expanded ? 'Hide' : 'Show'}</span>
      </button>

      {expanded ? (
        <div className="flex flex-col gap-2.5 border-t border-[#F0F0F4] px-5 pb-5 pt-4">
          {items.map((item) =>
            item.kind === 'entity_duplicate' ? (
              <EntityDuplicateCard key={item.unresolved_id} item={item} onResolved={load} />
            ) : (
              <AttentionCard key={item.memory_id} item={item} onResolved={load} />
            ),
          )}
          {total > items.length ? (
            <p className="text-center text-[12px] text-[#9CA3AF]">+{total - items.length} more</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
