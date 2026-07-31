import { useEffect, useState } from 'react'
import { ApiError, listDecisions, type DecisionOut, type DecisionRecordType } from '../lib/api'

const TAG_LABELS: Record<DecisionRecordType, string> = {
  decision: 'Decision',
  action_item: 'Action Item',
  blocker: 'Blocker',
}

const TAG_STYLES: Record<DecisionRecordType, string> = {
  decision: 'bg-[#EEEBFF] text-[#5A45FF]',
  blocker: 'bg-[#FEE2E2] text-[#DC2626]',
  action_item: 'bg-[#ECFCCB] text-[#4D7C0F]',
}

const PLATFORM_LABELS: Record<string, string> = {
  gmail: 'Gmail',
  slack: 'Slack',
  notion: 'Notion',
}

function isKnownRecordType(value: string): value is DecisionRecordType {
  return value === 'decision' || value === 'action_item' || value === 'blocker'
}

function timeAgo(iso: string, now = Date.now()) {
  const elapsedMs = Math.max(0, now - new Date(iso).getTime())
  const hours = Math.floor(elapsedMs / 3_600_000)
  if (hours < 1) return 'just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function DashboardCaptures() {
  const [captures, setCaptures] = useState<DecisionOut[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    listDecisions(5, 0)
      .then((response) => {
        if (active) setCaptures(response.items)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof ApiError ? err.message : 'Unable to load recent captures.')
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <section>
      <h2 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
        Build Memory
      </h2>
      <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        {isLoading ? (
          <p className="px-4 py-6 text-center text-[13px] text-[#9CA3AF]">Loading...</p>
        ) : error ? (
          <p className="px-4 py-6 text-center text-[13px] text-[#B4232C]">{error}</p>
        ) : captures.length === 0 ? (
          <p className="px-4 py-6 text-center text-[13px] text-[#9CA3AF]">No captures yet.</p>
        ) : (
          <ul>
            {captures.map((capture, i) => {
              const recordType = isKnownRecordType(capture.record_type)
                ? capture.record_type
                : 'decision'
              return (
                <li
                  key={capture.id}
                  className={`flex items-center gap-3 px-4 py-3.5 ${
                    i < captures.length - 1 ? 'border-b border-[#F0F0F4]' : ''
                  }`}
                >
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${TAG_STYLES[recordType]}`}
                  >
                    {TAG_LABELS[recordType]}
                  </span>
                  <p className="min-w-0 flex-1 truncate text-[14px] text-[#111827]">
                    {capture.decision_statement}
                  </p>
                  <span className="shrink-0 text-[12px] text-[#9CA3AF]">
                    {capture.source_platforms[0]
                      ? `${PLATFORM_LABELS[capture.source_platforms[0]] ?? capture.source_platforms[0]} · ${timeAgo(capture.created_at)}`
                      : timeAgo(capture.created_at)}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}
