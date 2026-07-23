import { useMemo, useState } from 'react'
import { DashboardNav } from '../components/DashboardNav'

type EntryType = 'Decision' | 'Action Item'
type FilterType = 'All Types' | EntryType
type StatusType = 'Current' | 'Superseded'

type LogEntry = {
  id: number
  type: EntryType
  summary: string
  source: string
  date: string
  status: StatusType
}

const FILTERS: FilterType[] = ['All Types', 'Decision', 'Action Item']

const LOG_ENTRIES: LogEntry[] = Array.from({ length: 9 }, (_, i) => ({
  id: i + 1,
  type: 'Action Item' as const,
  summary: 'Adopt PostgreSQL for the context layer persistence over',
  source: 'Slack #engineering',
  date: 'Aug 24, 2026',
  status: (i === 2 ? 'Superseded' : 'Current') as StatusType,
}))

const TYPE_STYLES: Record<EntryType, string> = {
  Decision: 'bg-[#EEEBFF] text-[#5A45FF]',
  'Action Item': 'bg-[#ECFCCB] text-[#4D7C0F]',
}

const STATUS_STYLES: Record<StatusType, string> = {
  Current: 'bg-[#EEEBFF] text-[#5A45FF]',
  Superseded: 'bg-[#F3F4F6] text-[#6B7280]',
}

export default function DecisionLogPage() {
  const [selectedType, setSelectedType] = useState<FilterType>('All Types')
  const [currentPage, setCurrentPage] = useState(1)

  const filteredEntries = useMemo(() => {
    if (selectedType === 'All Types') return LOG_ENTRIES
    return LOG_ENTRIES.filter((entry) => entry.type === selectedType)
  }, [selectedType])

  return (
    <div className="min-h-screen bg-[#F7F7FA]">
      <DashboardNav />

      <main className="mx-auto max-w-[1120px] px-8 py-8">
        <h1 className="text-[32px] font-bold leading-tight tracking-[-0.02em] text-[#111827]">
          Decision Log
        </h1>
        <p className="mt-2 text-[15px] text-[#6B7280]">
          Every captured decision, action item, and blocker — searchable and
          cited.
        </p>

        <div className="mt-6 flex flex-wrap gap-2.5" role="radiogroup" aria-label="Filter by type">
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
              {filteredEntries.map((entry, index) => (
                <tr
                  key={entry.id}
                  className={
                    index < filteredEntries.length - 1
                      ? 'border-b border-[#F0F0F4]'
                      : ''
                  }
                >
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${TYPE_STYLES[entry.type]}`}
                    >
                      {entry.type}
                    </span>
                  </td>
                  <td className="max-w-[360px] truncate px-5 py-3.5 text-[14px] text-[#111827]">
                    {entry.summary}
                  </td>
                  <td className="whitespace-nowrap px-5 py-3.5 text-[14px] text-[#6B7280]">
                    {entry.source}
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
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-5 flex items-center justify-between">
          <p className="text-[13px] text-[#9CA3AF]">
            Showing 1-{filteredEntries.length} of 100 Results
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
    </div>
  )
}
