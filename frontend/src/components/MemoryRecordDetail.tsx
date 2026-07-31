import { useState, type ReactNode } from 'react'

export type MemoryRecordType = 'Decision' | 'Blocker' | 'Action Item'
export type MemoryStatus = 'Current' | 'Superseded'

export type MemoryRecord = {
  id: string
  type: MemoryRecordType
  title: string
  meta: string
  summary: string
  participants: string
  source: string
  confidence: string
  status: MemoryStatus
  date?: string
  listSource?: string
  /** Real source URL (Slack permalink, Gmail/Notion link) - "View Original" opens this when present. */
  sourceLink?: string
}

export const TYPE_STYLES: Record<MemoryRecordType, string> = {
  Decision: 'bg-[#EEEBFF] text-[#5A45FF]',
  Blocker: 'bg-[#FEE2E2] text-[#DC2626]',
  'Action Item': 'bg-[#ECFCCB] text-[#4D7C0F]',
}

export const STATUS_STYLES: Record<MemoryStatus, string> = {
  Current: 'bg-[#EEEBFF] text-[#5A45FF]',
  Superseded: 'bg-[#F3F4F6] text-[#6B7280]',
}

const FLAG_REASONS = ['Inaccurate', 'Outdated', 'Other'] as const
type FlagReason = (typeof FLAG_REASONS)[number]

function FlagIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M5 21V4h9l-.8 3.2L14 10.5H5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function DetailRow({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] items-start gap-3 py-2.5">
      <span className="pt-0.5 text-[11px] font-semibold tracking-[0.06em] text-[#9CA3AF]">
        {label}
      </span>
      <div className="min-w-0 text-[14px] leading-relaxed text-[#111827]">{children}</div>
    </div>
  )
}

export function FlagPanel({
  onCancel,
  onSubmit,
}: {
  onCancel: () => void
  onSubmit: (reason: FlagReason, note: string) => void
}) {
  const [reason, setReason] = useState<FlagReason | null>(null)
  const [note, setNote] = useState('')

  return (
    <div className="mt-4 rounded-2xl border border-[#E5E7EB] bg-white p-5">
      <p className="text-[15px] font-semibold text-[#111827]">Why are you flagging this?</p>

      <div className="mt-3.5 flex flex-wrap gap-2.5">
        {FLAG_REASONS.map((option) => {
          const selected = reason === option
          return (
            <button
              key={option}
              type="button"
              onClick={() => setReason(option)}
              className={`rounded-full border px-4 py-2 text-[13px] font-medium transition-colors ${
                selected
                  ? 'border-[#5A45FF] bg-[#F5F3FF] text-[#5A45FF]'
                  : 'border-[#E5E7EB] bg-white text-[#6B7280] hover:bg-[#F9FAFB]'
              }`}
            >
              {option}
            </button>
          )
        })}
      </div>

      <input
        type="text"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Optional Note"
        className="mt-3.5 h-11 w-full rounded-full border border-[#E5E7EB] px-4 text-[14px] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#5A45FF]"
      />

      <div className="mt-4 flex justify-end gap-2.5">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-[#E5E7EB] bg-white px-4 py-2 text-[13px] font-semibold text-[#5A45FF] transition-colors hover:bg-[#F8F7FF]"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={!reason}
          onClick={() => {
            if (!reason) return
            onSubmit(reason, note)
          }}
          className="rounded-lg bg-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Submit Flag
        </button>
      </div>
    </div>
  )
}

export function MemoryRecordDetail({
  record,
  compactHeader = false,
  onHeaderClick,
}: {
  record: MemoryRecord
  compactHeader?: boolean
  onHeaderClick?: () => void
}) {
  const [isFlagging, setIsFlagging] = useState(false)
  const [flagSubmitted, setFlagSubmitted] = useState(false)

  return (
    <div>
      {!compactHeader ? (
        <button
          type="button"
          onClick={onHeaderClick}
          className="mb-4 flex w-full items-start gap-3 text-left"
        >
          <span
            className={`mt-0.5 shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${TYPE_STYLES[record.type]}`}
          >
            {record.type}
          </span>
          <p className="min-w-0 flex-1 text-[15px] font-semibold leading-snug text-[#111827]">
            {record.title}
          </p>
          <span className="shrink-0 text-[12px] text-[#9CA3AF]">{record.meta}</span>
        </button>
      ) : null}

      <div className="border-t border-[#F0F0F4] pt-1">
        <DetailRow label="SUMMARY">{record.summary}</DetailRow>
        <DetailRow label="PARTICIPANTS">
          <span className="text-[#5A45FF]">{record.participants}</span>
        </DetailRow>
        <DetailRow label="SOURCE">{record.source}</DetailRow>
        <DetailRow label="CONFIDENCE">{record.confidence}</DetailRow>
        <DetailRow label="STATUS">
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${STATUS_STYLES[record.status]}`}
          >
            {record.status}
          </span>
        </DetailRow>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          disabled={!record.sourceLink}
          onClick={() => {
            if (record.sourceLink) window.open(record.sourceLink, '_blank', 'noopener,noreferrer')
          }}
          className="rounded-lg border border-[#5A45FF] bg-white px-4 py-2 text-[13px] font-semibold text-[#5A45FF] transition-colors hover:bg-[#F8F7FF] disabled:cursor-not-allowed disabled:border-[#E5E7EB] disabled:text-[#9CA3AF] disabled:hover:bg-white"
        >
          View Original
        </button>
        <button
          type="button"
          onClick={() => {
            setIsFlagging((open) => !open)
            setFlagSubmitted(false)
          }}
          className="inline-flex items-center gap-2 rounded-lg bg-[#5A45FF] px-4 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
        >
          <FlagIcon />
          Flag
        </button>
        {flagSubmitted ? (
          <span className="text-[13px] font-medium text-[#16A34A]">Flag submitted</span>
        ) : null}
      </div>

      {isFlagging ? (
        <FlagPanel
          onCancel={() => setIsFlagging(false)}
          onSubmit={() => {
            setIsFlagging(false)
            setFlagSubmitted(true)
          }}
        />
      ) : null}
    </div>
  )
}

export function createDefaultMemoryRecord(
  partial: Partial<MemoryRecord> & Pick<MemoryRecord, 'id' | 'title'>,
): MemoryRecord {
  return {
    type: 'Decision',
    meta: 'Slack · 3h ago',
    summary:
      'Adopt PostgreSQL for the context layer persistence over vector-only stores',
    participants: '@jwest, @priya, @mtanaka',
    source: 'Notion · #product-planning · Mar 12, 9:41am',
    confidence: '0.92 — confirmed decision',
    status: 'Current',
    listSource: 'Slack #engineering',
    date: 'Aug 24, 2026',
    ...partial,
  }
}
