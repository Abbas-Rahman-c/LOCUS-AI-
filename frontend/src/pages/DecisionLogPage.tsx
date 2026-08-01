import { Fragment, useMemo, useState } from 'react'
import {
  MemoryRecordDetail,
  STATUS_STYLES,
  TYPE_STYLES,
  createDefaultMemoryRecord,
  type MemoryRecord,
  type MemoryRecordType,
} from '../components/MemoryRecordDetail'

type FilterType = 'All Types' | MemoryRecordType

const FILTERS: FilterType[] = ['All Types', 'Decision', 'Action Item', 'Blocker']

const LOG_ENTRIES: MemoryRecord[] = Array.from({ length: 9 }, (_, i) =>
  createDefaultMemoryRecord({
    id: `log-${i + 1}`,
    type: i === 0 || i === 3 || i === 6 ? 'Decision' : i === 2 || i === 5 ? 'Blocker' : 'Action Item',
    title: 'Adopt PostgreSQL for the context layer persistence over',
    summary:
      'Adopt PostgreSQL for the context layer persistence over vector-only stores',
    listSource: 'Slack #engineering',
    date: 'Aug 24, 2026',
    status: i === 2 ? 'Superseded' : 'Current',
    meta: 'Slack · 3h ago',
  }),
)

export default function DecisionLogPage() {
  const [selectedType, setSelectedType] = useState<FilterType>('All Types')
  const [currentPage, setCurrentPage] = useState(1)
  const [expandedId, setExpandedId] = useState<string | null>('log-1')
  const [activeFilter, setActiveFilter] = useState<string | null>(
    'Q3 timeline specific answer summary',
  )

  const filteredEntries = useMemo(() => {
    if (selectedType === 'All Types') return LOG_ENTRIES
    return LOG_ENTRIES.filter((entry) => entry.type === selectedType)
  }, [selectedType])

  return (
    <main className="mx-auto max-w-[1120px] px-8 py-8">
      <h1 className="text-[32px] font-bold leading-tight tracking-[-0.02em] text-[#111827]">
        Memory Explorer
      </h1>
      <p className="mt-2 text-[15px] text-[#6B7280]">
        Every captured decision, action item, and blocker is searchable and cited.
      </p>

      {activeFilter ? (
        <div className="mt-4 flex items-center gap-2 text-[14px] text-[#6B7280]">
          <span>
            Filtered by:{' '}
            <span className="font-semibold text-[#111827]">{activeFilter}</span>
          </span>
          <button
            type="button"
            aria-label="Clear filter"
            onClick={() => setActiveFilter(null)}
            className="flex h-5 w-5 items-center justify-center rounded-full text-[#5A45FF] hover:bg-[#F3F0FF]"
          >
            ×
          </button>
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-2.5" role="radiogroup" aria-label="Filter by type">
        {FILTERS.map((filter) => {
          const isSelected = selectedType === filter
          return (
            <button
              key={filter}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => {
                setSelectedType(filter)
                setCurrentPage(1)
              }}
              className={`rounded-full px-4 py-2 text-[13px] font-semibold transition-colors ${
                isSelected
                  ? 'bg-[#5A45FF] text-white'
                  : 'border border-[#E5E7EB] bg-white text-[#374151] hover:bg-[#F9FAFB]'
              }`}
            >
              {filter}
            </button>
          )
        })}
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-[#F0F0F4]">
              {['Type', 'Summary', 'Source', 'Date', 'Status'].map((heading) => (
                <th
                  key={heading}
                  className="px-5 py-3.5 text-[12px] font-semibold tracking-[0.02em] text-[#9CA3AF]"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredEntries.map((entry, index) => {
              const isExpanded = expandedId === entry.id
              return (
                <Fragment key={entry.id}>
                  <tr
                    onClick={() =>
                      setExpandedId((current) =>
                        current === entry.id ? null : entry.id,
                      )
                    }
                    className={`cursor-pointer transition-colors hover:bg-[#FAFAFB] ${
                      isExpanded ? 'bg-[#FAFAFB]' : ''
                    } ${
                      index < filteredEntries.length - 1 || isExpanded
                        ? 'border-b border-[#F0F0F4]'
                        : ''
                    }`}
                    aria-expanded={isExpanded}
                  >
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${TYPE_STYLES[entry.type]}`}
                      >
                        {entry.type}
                      </span>
                    </td>
                    <td className="max-w-[360px] truncate px-5 py-3.5 text-[14px] text-[#111827]">
                      {entry.title}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-[14px] text-[#6B7280]">
                      {entry.listSource}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-[14px] text-[#6B7280]">
                      {entry.date}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${STATUS_STYLES[entry.status]}`}
                      >
                        {entry.status}
                      </span>
                    </td>
                  </tr>
                  {isExpanded ? (
                    <tr className="border-b border-[#F0F0F4]">
                      <td colSpan={5} className="bg-[#F7F7F9] px-5 py-5">
                        <MemoryRecordDetail record={entry} compactHeader />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-5 flex items-center justify-between">
        <p className="text-[13px] text-[#9CA3AF]">
          Showing 1 to {filteredEntries.length} of 100 Results
        </p>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            aria-label="Previous page"
            className="flex h-8 w-8 items-center justify-center rounded-full text-[#6B7280] hover:bg-[#F3F4F6]"
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M15 6l-6 6 6 6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          {[1, 2].map((page) => (
            <button
              key={page}
              type="button"
              onClick={() => setCurrentPage(page)}
              className={`flex h-8 w-8 items-center justify-center rounded-full text-[13px] font-semibold ${
                currentPage === page
                  ? 'bg-[#5A45FF] text-white'
                  : 'text-[#6B7280] hover:bg-[#F3F4F6]'
              }`}
            >
              {page}
            </button>
          ))}

          <span className="px-1 text-[13px] text-[#9CA3AF]">...</span>

          <button
            type="button"
            onClick={() => setCurrentPage(8)}
            className={`flex h-8 w-8 items-center justify-center rounded-full text-[13px] font-semibold ${
              currentPage === 8
                ? 'bg-[#5A45FF] text-white'
                : 'text-[#6B7280] hover:bg-[#F3F4F6]'
            }`}
          >
            8
          </button>

          <button
            type="button"
            aria-label="Next page"
            className="flex h-8 w-8 items-center justify-center rounded-full text-[#6B7280] hover:bg-[#F3F4F6]"
            onClick={() => setCurrentPage((page) => Math.min(8, page + 1))}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M9 6l6 6-6 6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>
    </main>
  )
}
