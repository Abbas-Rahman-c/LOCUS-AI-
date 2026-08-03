import { useState } from 'react'
import {
  MemoryRecordDetail,
  TYPE_STYLES,
  createDefaultMemoryRecord,
  type MemoryRecord,
  type MemoryRecordType,
} from './MemoryRecordDetail'

const CAPTURES: MemoryRecord[] = [
  createDefaultMemoryRecord({
    id: 'dash-1',
    type: 'Decision',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  }),
  createDefaultMemoryRecord({
    id: 'dash-2',
    type: 'Blocker',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
    confidence: '0.81, open blocker',
    status: 'Current',
  }),
  createDefaultMemoryRecord({
    id: 'dash-3',
    type: 'Action Item',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
    confidence: '0.88, assigned action',
  }),
  createDefaultMemoryRecord({
    id: 'dash-4',
    type: 'Decision',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  }),
  createDefaultMemoryRecord({
    id: 'dash-5',
    type: 'Decision',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  }),
]

export function DashboardCaptures() {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  return (
    <section>
      <h2 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
        Memory Feed
      </h2>
      <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        <ul>
          {CAPTURES.map((capture, i) => {
            const isExpanded = expandedId === capture.id
            return (
              <li
                key={capture.id}
                className={i < CAPTURES.length - 1 ? 'border-b border-[#F0F0F4]' : ''}
              >
                {isExpanded ? (
                  <div className="bg-white px-4 py-4">
                    <MemoryRecordDetail
                      record={capture}
                      onHeaderClick={() => setExpandedId(null)}
                    />
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setExpandedId(capture.id)}
                    className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-[#FAFAFB]"
                    aria-expanded={false}
                  >
                    <span
                      className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${TYPE_STYLES[capture.type as MemoryRecordType]}`}
                    >
                      {capture.type}
                    </span>
                    <p className="min-w-0 flex-1 truncate text-[14px] text-[#111827]">
                      {capture.title}
                    </p>
                    <span className="shrink-0 text-[12px] text-[#9CA3AF]">
                      {capture.meta}
                    </span>
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
