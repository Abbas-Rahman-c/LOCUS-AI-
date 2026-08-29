import { useEffect, useState } from 'react'
import { listAttentionItems, type AttentionConflictItem } from '../lib/api'

// Rebuilt after the memory-intelligence layer (Memory Timeline, Attention
// strip v1, entity review queue) was removed entirely - that backend read
// from memories/memory_conflicts, both gone now. This version reads real
// decision_conflicts rows instead (the decisions pipeline you kept
// already populates this table during normal ingestion - see ai-worker's
// conflict-detection call), so it's live again with zero new backend
// infrastructure and zero added Claude API cost: GET /attention is a
// plain SQL read, no model call in that path at all.
//
// Deliberately smaller than the original: conflicts only, no
// commitment/staleness categories (those were memory-layer concepts with
// no decisions-pipeline equivalent), and no resolve/dismiss action -
// decision_conflicts has no resolution-tracking column today, so a
// "Resolve" button would have nothing real to write to. Read-only for
// now; a real dismiss action is a genuine follow-up, not done here.
// Collapsible, collapsed by default, same as before - never a hollow
// container, renders nothing substantial until there's confirmed to be
// something (or confirmed there isn't).

function ConflictCard({ item }: { item: AttentionConflictItem }) {
  return (
    <div className="rounded-xl border border-[#E5E7EB] bg-white p-4">
      <span className="inline-flex rounded-full bg-[#FEE2E2] px-2.5 py-1 text-[11px] font-semibold text-[#DC2626]">
        Conflict
      </span>
      <p className="mt-2 text-[14px] font-semibold text-[#111827]">{item.decision_statement}</p>
      <p className="mt-1 text-[13px] text-[#6B7280]">
        <span className="text-[#9CA3AF]">vs.</span> {item.related_decision_statement}
      </p>
      <p className="mt-2 text-[13px] leading-relaxed text-[#374151]">{item.reason}</p>
    </div>
  )
}

export function AttentionStrip() {
  const [items, setItems] = useState<AttentionConflictItem[]>([])
  const [total, setTotal] = useState<number | null>(null) // null = not loaded yet
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    listAttentionItems()
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
      })
      .catch(() => {
        // Fails quiet - this is a convenience surface above search, not
        // something that should show an error banner on the dashboard if
        // the endpoint has a hiccup.
        setTotal(0)
      })
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
          {items.map((item) => (
            <ConflictCard key={item.id} item={item} />
          ))}
          {total > items.length ? (
            <p className="text-center text-[12px] text-[#9CA3AF]">+{total - items.length} more</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
