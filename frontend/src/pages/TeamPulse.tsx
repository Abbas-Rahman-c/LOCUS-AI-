import { useEffect, useMemo, useState } from 'react'
import { DashboardNav } from '../components/DashboardNav'

type PulseSection = {
  count: number
  description: string
  items: string[]
}

type TeamPulseData = {
  decisions: PulseSection
  actionItems: PulseSection
  blockers: PulseSection
}

const FALLBACK_PULSE: TeamPulseData = {
  decisions: {
    count: 5,
    description: 'Top 3 by confidence and recency — 2 more below',
    items: [
      'Q3 ship date moved to July 29 after the design review conflict surfaced',
      'Engineering confirmed the two-week buffer is enough — no scope cuts needed',
      'Client will be told proactively about the date change, not at next check-in',
    ],
  },
  actionItems: {
    count: 3,
    description: 'All 3 captured this week shown',
    items: [
      'Notify client services of the revised July 29 launch date',
      'Update sprint calendar to reflect shifted milestones',
      'Update public release notes once the date is finalized internally',
    ],
  },
  blockers: {
    count: 1,
    description: 'Only blocker still active as of Sunday night',
    items: ['Design review still blocked pending legal sign-off on new copy'],
  },
}

const DAY_IN_MS = 24 * 60 * 60 * 1000
const TEAM_PULSE_ENDPOINT =
  import.meta.env.VITE_TEAM_PULSE_API_URL || '/api/team-pulse'

function startOfWeek(date: Date) {
  const result = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const daysSinceMonday = (result.getDay() + 6) % 7
  result.setDate(result.getDate() - daysSinceMonday)
  return result
}

function addDays(date: Date, days: number) {
  const result = new Date(date)
  result.setDate(result.getDate() + days)
  return result
}

function toInputDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatNumericDate(date: Date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${month}-${day}-${date.getFullYear()}`
}

function formatWeekTitle(start: Date, end: Date) {
  const startText = start.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
  const endText = end.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
  return `${startText} – ${endText}`
}

function getIsoWeek(date: Date) {
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const dayNumber = target.getUTCDay() || 7
  target.setUTCDate(target.getUTCDate() + 4 - dayNumber)
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1))
  return Math.ceil(((target.getTime() - yearStart.getTime()) / DAY_IN_MS + 1) / 7)
}

function isPulseSection(value: unknown): value is PulseSection {
  if (!value || typeof value !== 'object') return false
  const section = value as Partial<PulseSection>
  return (
    typeof section.count === 'number' &&
    typeof section.description === 'string' &&
    Array.isArray(section.items) &&
    section.items.every((item) => typeof item === 'string')
  )
}

function isTeamPulseData(value: unknown): value is TeamPulseData {
  if (!value || typeof value !== 'object') return false
  const pulse = value as Partial<TeamPulseData>
  return (
    isPulseSection(pulse.decisions) &&
    isPulseSection(pulse.actionItems) &&
    isPulseSection(pulse.blockers)
  )
}

function PulseGroup({
  title,
  color,
  section,
}: {
  title: string
  color: string
  section: PulseSection
}) {
  return (
    <section className="flex gap-3">
      <span
        className="mt-[7px] h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      <div>
        <h2 className="text-[14px] font-medium text-[#242334]">
          {title} <span className="font-normal text-[#8B91A1]">{section.count}</span>
        </h2>
        <p className="mt-0.5 text-[12px] leading-5 text-[#858B9B]">
          {section.description}
        </p>
        <ul className="mt-2 space-y-1.5">
          {section.items.map((item) => (
            <li key={item} className="flex text-[13px] leading-5 text-[#30303E]">
              <span className="mr-2.5 text-[#9197A5]" aria-hidden="true">
                —
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function FeedbackIcon({ direction }: { direction: 'up' | 'down' }) {
  const transform = direction === 'down' ? 'rotate(180 12 12)' : undefined
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M7.5 10.5v9H4v-9h3.5Zm0 7.5h8.9c1 0 1.8-.7 2-1.7l1.1-5.3a2 2 0 0 0-2-2.5H14l.5-2.7c.2-1.1-.5-2.2-1.6-2.5L8.8 10.5H7.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        transform={transform}
      />
    </svg>
  )
}

export default function TeamPulse() {
  const currentWeekStart = useMemo(() => startOfWeek(new Date()), [])
  const currentWeekEnd = useMemo(() => addDays(currentWeekStart, 6), [currentWeekStart])
  const [rangeStart, setRangeStart] = useState(currentWeekStart)
  const [rangeEnd, setRangeEnd] = useState(currentWeekEnd)
  const [draftStart, setDraftStart] = useState(toInputDate(currentWeekStart))
  const [draftEnd, setDraftEnd] = useState(toInputDate(currentWeekEnd))
  const [isRangePickerOpen, setIsRangePickerOpen] = useState(false)
  const [pulse, setPulse] = useState(FALLBACK_PULSE)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)
  const rangeDays = Math.round((rangeEnd.getTime() - rangeStart.getTime()) / DAY_IN_MS) + 1
  const isFullWeek = rangeDays === 7 && rangeStart.getDay() === 1
  const isCurrentWeek =
    toInputDate(rangeStart) === toInputDate(currentWeekStart) &&
    toInputDate(rangeEnd) === toInputDate(currentWeekEnd)
  const periodLabel = isCurrentWeek
    ? 'This Week'
    : isFullWeek
      ? 'Selected Week'
      : 'Selected Date Range'

  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams({
      start_date: toInputDate(rangeStart),
      end_date: toInputDate(rangeEnd),
    })

    void fetch(`${TEAM_PULSE_ENDPOINT}?${params}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Team Pulse data is unavailable')
        return response.json() as Promise<unknown>
      })
      .then((data) => {
        if (isTeamPulseData(data)) setPulse(data)
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setPulse(FALLBACK_PULSE)
      })

    return () => controller.abort()
  }, [rangeEnd, rangeStart])

  const moveRange = (amount: number) => {
    const dayOffset = amount * rangeDays
    const nextStart = addDays(rangeStart, dayOffset)
    const nextEnd = addDays(rangeEnd, dayOffset)
    setRangeStart(nextStart)
    setRangeEnd(nextEnd)
    setDraftStart(toInputDate(nextStart))
    setDraftEnd(toInputDate(nextEnd))
  }

  const openRangePicker = () => {
    setDraftStart(toInputDate(rangeStart))
    setDraftEnd(toInputDate(rangeEnd))
    setIsRangePickerOpen(true)
  }

  const applyRange = () => {
    const [startYear, startMonth, startDay] = draftStart.split('-').map(Number)
    const [endYear, endMonth, endDay] = draftEnd.split('-').map(Number)
    setRangeStart(new Date(startYear, startMonth - 1, startDay))
    setRangeEnd(new Date(endYear, endMonth - 1, endDay))
    setIsRangePickerOpen(false)
  }

  return (
    <div className="min-h-screen bg-[#F7F7FA]">
      <DashboardNav />

      <main className="mx-auto max-w-[1064px] px-4 py-6 sm:px-8">
        <div className="mb-4">
          <h1 className="text-[24px] font-semibold leading-tight text-[#17171D]">Pulse</h1>
          <p className="mt-1 text-[14px] text-[#7C8392]">
            Your week, synthesized. New every Monday.
          </p>
        </div>

        <article className="rounded-[8px] border border-[#E2E4EA] bg-white">
          <header className="flex min-h-[98px] flex-col items-start justify-between gap-5 border-b border-[#E6E7EC] px-6 py-4 md:flex-row md:items-center md:gap-6">
            <div>
              <p className="text-[12px] font-medium text-[#7D8494]">
                {periodLabel}
              </p>
              <div className="mt-4 flex items-center gap-3">
                <h2 className="text-[22px] font-semibold leading-none text-[#17171D]">
                  {formatWeekTitle(rangeStart, rangeEnd)}
                </h2>
                <span className="rounded-full bg-[#E8E5FF] px-3 py-1 text-[11px] font-medium text-[#6254D9]">
                  {isFullWeek
                    ? `Q${Math.floor(rangeStart.getMonth() / 3) + 1} · W${getIsoWeek(rangeStart)}`
                    : `${rangeDays} days`}
                </span>
              </div>
            </div>

            <div className="flex w-full items-center gap-2 md:w-auto md:shrink-0">
              <button
                type="button"
                aria-label="Previous week"
                onClick={() => moveRange(-1)}
                className="flex h-8 w-8 items-center justify-center rounded-[7px] border border-[#E0E2E8] text-[20px] text-[#4A4F5B] hover:bg-[#F7F7FA]"
              >
                ‹
              </button>
              <div className="relative min-w-0 flex-1 md:min-w-[245px]">
                <button
                  type="button"
                  aria-label="Choose date range"
                  aria-expanded={isRangePickerOpen}
                  onClick={() => (isRangePickerOpen ? setIsRangePickerOpen(false) : openRangePicker())}
                  className="flex h-8 w-full items-center justify-center gap-2 rounded-[16px] border border-[#E0E2E8] px-2 text-[11px] text-[#3F424C] hover:bg-[#F7F7FA] sm:gap-3 sm:px-4 sm:text-[13px]"
                >
                  <span>{formatNumericDate(rangeStart)}</span>
                  <span className="text-[#8B91A0]">–</span>
                  <span>{formatNumericDate(rangeEnd)}</span>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M7 3v3M17 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                  </svg>
                </button>

                {isRangePickerOpen ? (
                  <div className="absolute right-0 top-10 z-30 w-[290px] rounded-[8px] border border-[#E0E2E8] bg-white p-4 shadow-[0_12px_30px_rgba(24,24,35,0.14)]">
                    <p className="text-[13px] font-semibold text-[#242334]">Select date range</p>
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      <label className="text-[11px] font-medium text-[#747B8A]">
                        Start date
                        <input
                          type="date"
                          value={draftStart}
                          max={draftEnd}
                          onInput={(event) => setDraftStart(event.currentTarget.value)}
                          className="mt-1 block h-9 w-full rounded-[6px] border border-[#DDE0E7] px-2 text-[12px] text-[#30303E] outline-none focus:border-[#6254D9]"
                        />
                      </label>
                      <label className="text-[11px] font-medium text-[#747B8A]">
                        End date
                        <input
                          type="date"
                          value={draftEnd}
                          min={draftStart}
                          onInput={(event) => setDraftEnd(event.currentTarget.value)}
                          className="mt-1 block h-9 w-full rounded-[6px] border border-[#DDE0E7] px-2 text-[12px] text-[#30303E] outline-none focus:border-[#6254D9]"
                        />
                      </label>
                    </div>
                    <div className="mt-4 flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setIsRangePickerOpen(false)}
                        className="h-8 px-3 text-[12px] font-medium text-[#6F7685]"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        disabled={!draftStart || !draftEnd || draftEnd < draftStart}
                        onClick={applyRange}
                        className="h-8 rounded-[6px] bg-[#5143DB] px-4 text-[12px] font-medium text-white hover:bg-[#4033C5] disabled:cursor-not-allowed disabled:bg-[#B7B3E8]"
                      >
                        Apply
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
              <button
                type="button"
                aria-label="Next week"
                onClick={() => moveRange(1)}
                className="flex h-8 w-8 items-center justify-center rounded-[7px] border border-[#E0E2E8] text-[20px] text-[#4A4F5B] hover:bg-[#F7F7FA]"
              >
                ›
              </button>
            </div>
          </header>

          <div className="min-h-[405px] space-y-7 px-6 py-5">
            <PulseGroup title="Decisions" color="#5644DF" section={pulse.decisions} />
            <PulseGroup title="Action items" color="#9CDD24" section={pulse.actionItems} />
            <PulseGroup title="Blockers" color="#F3464B" section={pulse.blockers} />
          </div>

          <footer className="flex h-[58px] items-center justify-between border-t border-[#E6E7EC] px-6">
            <div className="flex items-center gap-2 text-[13px] text-[#818897]">
              <span>Useful?</span>
              {(['up', 'down'] as const).map((direction) => (
                <button
                  key={direction}
                  type="button"
                  aria-label={direction === 'up' ? 'Helpful' : 'Not helpful'}
                  aria-pressed={feedback === direction}
                  onClick={() => setFeedback((current) => (current === direction ? null : direction))}
                  className={`flex h-7 w-7 items-center justify-center rounded-[7px] border transition-colors ${
                    feedback === direction
                      ? 'border-[#6254D9] bg-[#F0EEFF] text-[#6254D9]'
                      : 'border-[#E1E3E9] text-[#858C9B] hover:bg-[#F7F7FA]'
                  }`}
                >
                  <FeedbackIcon direction={direction} />
                </button>
              ))}
            </div>
            <a
              href="/decision-log"
              className="text-[14px] font-medium text-[#5544E6] hover:text-[#4030CA]"
            >
              View full Decision Log
            </a>
          </footer>
        </article>
      </main>
    </div>
  )
}
