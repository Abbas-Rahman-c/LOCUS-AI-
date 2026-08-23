import { useEffect, useState } from 'react'
import {
  ApiError,
  confirmNewEntity,
  dismissUnresolvedEntity,
  listUnresolvedEntities,
  mergeEntity,
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

export default function EntityReviewQueuePage() {
  const [items, setItems] = useState<ReviewQueueItem[] | null>(null)
  const [index, setIndex] = useState(0)
  const [error, setError] = useState('')
  const [acting, setActing] = useState(false)
  const [actionError, setActionError] = useState('')

  const load = () => {
    setError('')
    listUnresolvedEntities()
      .then((res) => {
        setItems(res.pending)
        setIndex((i) => Math.min(i, Math.max(res.pending.length - 1, 0)))
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : 'Unable to load the review queue.'))
  }

  useEffect(load, [])

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

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <p className="text-[13px] text-[#DC2626]">{error}</p>
      </div>
    )
  }

  if (items === null) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <p className="text-[13px] text-[#9CA3AF]">Loading…</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-[22px] font-bold text-[#111827]">Entity Review Queue</h1>
      <p className="mt-1 text-[13px] text-[#6B7280]">
        Possible duplicates and unconfirmed mentions flagged by extraction. Nothing here has been merged automatically -
        every decision needs your click.
      </p>

      {items.length === 0 ? (
        <div className="mt-6 rounded-xl border border-[#E5E7EB] bg-white p-6 text-center">
          <p className="text-[14px] font-semibold text-[#111827]">Nothing pending.</p>
          <p className="mt-1 text-[13px] text-[#9CA3AF]">The queue is clear.</p>
        </div>
      ) : current ? (
        <div className="mt-6">
          <p className="text-[11px] font-semibold tracking-[0.06em] text-[#9CA3AF]">
            {current.kind === 'confirmed_duplicate' ? 'POSSIBLE DUPLICATE' : 'UNCONFIRMED MENTION'} · {current.left.entity_type} ·{' '}
            {index + 1} of {items.length}
          </p>

          <div className="mt-3 flex flex-col gap-3 sm:flex-row">
            <SideCard side={current.left} label={current.kind === 'confirmed_duplicate' ? 'Flagged entity' : 'New mention'} />
            {current.right ? (
              <SideCard side={current.right} label="Possible match" />
            ) : (
              <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-[#E5E7EB] p-4 text-center text-[13px] text-[#9CA3AF]">
                No existing entity looks like a match.
              </div>
            )}
          </div>

          {actionError ? <p className="mt-3 text-[12px] text-[#DC2626]">{actionError}</p> : null}

          <div className="mt-4 flex flex-wrap gap-2">
            {current.kind === 'confirmed_duplicate' && current.right ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => mergeEntity(current.id, current.right!.entity_id as string))}
                className="rounded-full bg-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#4C39E0] disabled:opacity-50"
              >
                Merge into {current.right.name}
              </button>
            ) : null}
            {current.kind === 'raw_mention' && current.right ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => mergeEntity(current.id, current.right!.entity_id as string))}
                className="rounded-full bg-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#4C39E0] disabled:opacity-50"
              >
                Merge into {current.right.name}
              </button>
            ) : null}
            {current.kind === 'raw_mention' ? (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => confirmNewEntity(current.id))}
                className="rounded-full border border-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-[#5A45FF] hover:bg-[#F8F7FF] disabled:opacity-50"
              >
                Confirm as new
              </button>
            ) : (
              <button
                type="button"
                disabled={acting}
                onClick={() => void runAction(() => dismissUnresolvedEntity(current.id))}
                className="rounded-full border border-[#E5E7EB] px-4 py-2 text-[13px] font-semibold text-[#374151] hover:bg-[#F9FAFB] disabled:opacity-50"
              >
                Keep separate
              </button>
            )}
            <button
              type="button"
              disabled={acting}
              onClick={() => void runAction(() => dismissUnresolvedEntity(current.id))}
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
