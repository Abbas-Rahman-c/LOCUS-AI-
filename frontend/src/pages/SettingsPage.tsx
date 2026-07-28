import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { User } from '@supabase/supabase-js'
import { useNavigate } from 'react-router-dom'
import { getSupabaseClient } from '../lib/supabase'

type SettingsSection =
  | 'Account'
  | 'Connected Sources'
  | 'Capture Controls'
  | 'Privacy'
  | 'Search'
  | 'Notifications'

type CaptureMode = 'decisions-actions' | 'decisions-only'
type SourceFilter = 'All' | 'Gmail' | 'Notion' | 'Slack'

type ChannelRow = {
  id: string
  name: string
  included: boolean
  app: SourceFilter
}

type SearchHistoryItem = {
  id: string
  query: string
  result_count: number
  searched_at: string
}

const SIDEBAR_ITEMS: { id: SettingsSection; label: string }[] = [
  { id: 'Account', label: 'Account' },
  { id: 'Connected Sources', label: 'Connected Sources' },
  { id: 'Capture Controls', label: 'Capture Controls' },
  { id: 'Privacy', label: 'Privacy' },
  { id: 'Search', label: 'Search' },
  { id: 'Notifications', label: 'Notifications' },
]

const SOURCE_FILTERS: SourceFilter[] = ['All', 'Gmail', 'Notion', 'Slack']

const INITIAL_CHANNELS: ChannelRow[] = [
  { id: '1', name: '# product-planning', included: false, app: 'Slack' },
  { id: '2', name: '# product-planning', included: true, app: 'Slack' },
  { id: '3', name: '# product-planning', included: true, app: 'Slack' },
  { id: '4', name: '# product-planning', included: true, app: 'Slack' },
  { id: '5', name: '# eng-standup', included: true, app: 'Slack' },
  { id: '6', name: 'Product Specs', included: true, app: 'Notion' },
  { id: '7', name: 'Launch checklist', included: true, app: 'Notion' },
  { id: '8', name: 'team@company.com', included: false, app: 'Gmail' },
]

function AccountIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M5 19.5c0-3.6 3.1-6 7-6s7 2.4 7 6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  )
}

function LightningIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M13 2L4 14h7l-1 8 10-14h-7l0-6z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function HashIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 4L7 20M17 4l-2 16M4 9h16M3 15h16"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M16.5 16.5L21 21" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

function BellIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M6 10a6 6 0 1112 0c0 4 1.5 5.5 1.5 5.5H4.5S6 14 6 10z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M10 19a2 2 0 004 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

const SIDEBAR_ICONS: Record<SettingsSection, ReactNode> = {
  Account: <AccountIcon />,
  'Connected Sources': <LightningIcon />,
  'Capture Controls': <HashIcon />,
  Privacy: <ShieldIcon />,
  Search: <SearchIcon />,
  Notifications: <BellIcon />,
}

function TrashIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function FeatureCheckIcon() {
  return (
    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#4B3BD4] text-[12px] font-bold text-white">
      &#10003;
    </span>
  )
}

function RocketIcon() {
  return (
    <svg
      className="mt-0.5 h-5 w-5 shrink-0 text-[#4B3BD4]"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M14.5 5.5c2.3-2.3 4.7-2.5 5.8-2.4.1 1.1-.1 3.5-2.4 5.8l-5.8 5.8-3.4-3.4 5.8-5.8zM8.8 8.5l-3.7.7-2 2 4.3.8M14.9 14l-.7 3.7-2 2-.8-4.3M7.5 15.7l-2.8 2.8M6.2 14.4l-3 1.2M8.8 17l-1.2 3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 3v11M8 10l4 4 4-4M5 16v4h14v-4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const CORE_PLAN_FEATURES = [
  'Own sources (Slack, Notion, Gmail — with SharePoint/OneDrive/Teams on the roadmap)',
  'Own decision register (private, not shared)',
  'Context Search with saved search history',
  'Personal Pulse — weekly digest of your own decisions, action items, and blockers',
  'Catch-Up Brief — self-serve, parameterized by scope and time window',
  'Capture refresh rate: 6 hours',
  'MCP access — search_team_context, get_team_pulse, get_onboarding_brief callable from Claude',
]

function PlanFeature({
  children,
  upcoming = false,
}: {
  children: string
  upcoming?: boolean
}) {
  return (
    <li className="flex items-start gap-3 text-[15px] leading-[1.45] text-[#202027]">
      {upcoming ? <RocketIcon /> : <FeatureCheckIcon />}
      <span>{children}</span>
    </li>
  )
}

function PlanPicker({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/25 p-3 sm:p-5"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="plan-picker-title"
        className="relative mx-auto h-full max-h-[calc(100vh-24px)] w-full max-w-[1440px] overflow-y-auto rounded-[18px] border border-[#E0E2E8] bg-[#F8F8FC] px-5 py-8 shadow-[0_24px_70px_rgba(20,24,35,0.22)] sm:max-h-[calc(100vh-40px)] sm:px-10 lg:px-12"
      >
        <button
          type="button"
          aria-label="Close plan selection"
          onClick={onClose}
          className="absolute top-4 right-5 flex h-10 w-10 items-center justify-center text-[38px] font-light leading-none text-[#4437D5] hover:text-[#2F259E]"
        >
          &times;
        </button>

        <h2
          id="plan-picker-title"
          className="pr-14 text-[30px] font-medium text-[#111116] sm:text-[34px]"
        >
          Find the right plan for you.
        </h2>

        <div className="mt-7 grid items-stretch gap-7 lg:grid-cols-2">
          <article className="flex min-h-[720px] flex-col overflow-hidden rounded-[18px] border border-[#DFE1E8] bg-white">
            <header className="relative aspect-[774/241] w-full shrink-0 overflow-hidden rounded-t-[17px] border-b border-[#E3E4E9]">
              <img
                src="/individual-plan-header.png"
                alt="Individual plan, $12 per month"
                className="block h-full w-full object-cover"
              />
              <img
                src="/individual-plan-art.png"
                alt=""
                aria-hidden="true"
                className="absolute inset-y-0 right-0 h-full w-[36%] rounded-tr-[17px] object-cover object-right"
                style={{
                  WebkitMaskImage:
                    'linear-gradient(to right, transparent 0%, black 18%)',
                  maskImage:
                    'linear-gradient(to right, transparent 0%, black 18%)',
                }}
              />
            </header>

            <div className="flex flex-1 flex-col px-8 pt-7 pb-5">
              <ul className="space-y-4">
                {CORE_PLAN_FEATURES.map((feature) => (
                  <PlanFeature key={feature}>{feature}</PlanFeature>
                ))}
                <PlanFeature>
                  Privacy controls, audit log, data export, cookie controls
                </PlanFeature>
              </ul>
              <div className="mt-auto border-t border-[#E0E2E8] pt-6">
                <button
                  type="button"
                  disabled
                  className="h-12 w-full rounded-[8px] border border-[#DCE0E7] bg-white text-[16px] font-medium text-[#4B3BD4]"
                >
                  Current
                </button>
              </div>
            </div>
          </article>

          <article className="flex min-h-[720px] flex-col overflow-hidden rounded-[18px] border border-[#4B3BD4] bg-white">
            <header className="relative aspect-[774/241] w-full shrink-0 overflow-hidden rounded-t-[17px]">
              <img
                src="/team-plan-header.png"
                alt="Team plan, $15 per month"
                className="block h-full w-full object-cover"
              />
              <img
                src="/team-plan-art.png"
                alt=""
                aria-hidden="true"
                className="absolute -top-[7px] right-0 h-[calc(100%+7px)] w-[40%] object-cover object-right"
                style={{
                  WebkitMaskImage:
                    'linear-gradient(to right, transparent 0%, black 18%)',
                  maskImage:
                    'linear-gradient(to right, transparent 0%, black 18%)',
                }}
              />
            </header>

            <div className="flex flex-1 flex-col px-8 pt-7 pb-5">
              <ul className="space-y-4">
                {CORE_PLAN_FEATURES.map((feature) => (
                  <PlanFeature key={feature}>{feature}</PlanFeature>
                ))}
                <li className="border-t border-[#E0E2E8] pt-4">
                  <PlanFeature upcoming>
                    Privacy controls, audit log, data export, cookie controls
                  </PlanFeature>
                </li>
                <PlanFeature upcoming>
                  Privacy controls, audit log, data export, cookie controls
                </PlanFeature>
                <PlanFeature upcoming>
                  Privacy controls, audit log, data export, cookie controls
                </PlanFeature>
              </ul>
              <div className="mt-auto border-t border-[#E0E2E8] pt-6">
                <button
                  type="button"
                  className="h-12 w-full rounded-[8px] bg-[#4B3BD4] text-[16px] font-semibold text-white hover:bg-[#3F30BC]"
                >
                  Upgrade
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
  )
}

function BillingInformation({
  onClose,
  onUpdate,
}: {
  onClose: () => void
  onUpdate: () => void
}) {
  const invoices = [
    { id: 'invoice-1', date: 'July 07, 2026', total: '$12', status: 'Paid' },
    { id: 'invoice-2', date: 'July 07, 2026', total: '$12', status: 'Paid' },
    { id: 'invoice-3', date: 'July 07, 2026', total: '$12', status: 'Paid' },
    { id: 'invoice-4', date: 'July 07, 2026', total: '$12', status: 'Paid' },
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="billing-information-title"
        className="relative w-full max-w-[1180px] overflow-hidden rounded-[18px] border border-[#E0E2E8] bg-white shadow-[0_24px_70px_rgba(20,24,35,0.22)]"
      >
        <header className="flex min-h-[88px] items-center justify-between border-b border-[#E0E2E8] px-8">
          <h2
            id="billing-information-title"
            className="text-[20px] font-semibold text-[#202027]"
          >
            Billing
          </h2>
          <button
            type="button"
            aria-label="Close billing information"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center text-[38px] font-light leading-none text-[#4437D5] hover:text-[#2F259E]"
          >
            &times;
          </button>
        </header>

        <div className="flex min-h-[104px] items-center justify-between gap-5 border-b border-[#E0E2E8] px-8 py-5">
          <p className="text-[17px] font-medium text-[#24242A]">
            Link by Stripe
          </p>
          <button
            type="button"
            onClick={onUpdate}
            className="h-11 rounded-[8px] border border-[#DEE1E8] bg-white px-8 text-[16px] font-medium text-[#4B3BD4] hover:bg-[#F8F7FF]"
          >
            Update
          </button>
        </div>

        <div className="px-8 pt-6">
          <h3 className="text-[17px] font-medium text-[#24242A]">Invoices</h3>
        </div>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[680px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[#E0E2E8]">
                <th className="px-8 py-4 text-[16px] font-medium text-[#24242A]">
                  Date
                </th>
                <th className="px-8 py-4 text-[16px] font-medium text-[#24242A]">
                  Total
                </th>
                <th className="px-8 py-4 text-[16px] font-medium text-[#24242A]">
                  Status
                </th>
                <th className="px-8 py-4 text-[16px] font-medium text-[#24242A]">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => (
                <tr key={invoice.id} className="border-b border-[#E0E2E8] last:border-b-0">
                  <td className="px-8 py-5 text-[15px] text-[#24242A]">
                    {invoice.date}
                  </td>
                  <td className="px-8 py-5 text-[15px] text-[#24242A]">
                    {invoice.total}
                  </td>
                  <td className="px-8 py-5 text-[15px] text-[#24242A]">
                    {invoice.status}
                  </td>
                  <td className="px-8 py-5">
                    <button
                      type="button"
                      className="text-[15px] font-medium text-[#4B3BD4] hover:underline"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function formatSearchAge(searchedAt: string, now = Date.now()) {
  const elapsedMs = Math.max(0, now - new Date(searchedAt).getTime())
  const hours = Math.max(1, Math.floor(elapsedMs / 3_600_000))

  if (elapsedMs < 86_400_000) {
    return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`
  }

  const days = Math.floor(elapsedMs / 86_400_000)
  if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'} ago`

  const weeks = Math.floor(days / 7)
  if (days < 30) return `${weeks} ${weeks === 1 ? 'week' : 'weeks'} ago`

  const months = Math.floor(days / 30)
  if (days < 365) {
    return `${months} ${months === 1 ? 'month' : 'months'} ago`
  }

  const years = Math.floor(days / 365)
  return `${years} ${years === 1 ? 'year' : 'years'} ago`
}

function SearchSettings() {
  const [items, setItems] = useState<SearchHistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [saveHistory, setSaveHistory] = useState(true)
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdating, setIsUpdating] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    const loadHistory = async () => {
      const supabase = getSupabaseClient()
      const { data: sessionData } = await supabase.auth.getSession()
      if (!sessionData.session) {
        if (active) {
          setError('Your session has expired. Please sign in again.')
          setIsLoading(false)
        }
        return
      }

      const { data, error: historyError } = await supabase.functions.invoke(
        'search-history',
        { body: { action: 'list' } },
      )

      if (!active) return
      if (historyError) {
        setError(historyError.message)
      } else {
        setItems((data?.items ?? []) as SearchHistoryItem[])
        setTotal(Number(data?.total ?? 0))
        setSaveHistory(data?.saveHistory !== false)
      }
      setIsLoading(false)
    }

    void loadHistory()
    return () => {
      active = false
    }
  }, [])

  const toggleHistory = async () => {
    const nextValue = !saveHistory
    setIsUpdating(true)
    setError('')

    const { error: toggleError } = await getSupabaseClient().functions.invoke(
      'search-history',
      { body: { action: 'toggle', enabled: nextValue } },
    )

    if (toggleError) {
      setError(toggleError.message)
    } else {
      setSaveHistory(nextValue)
    }
    setIsUpdating(false)
  }

  const clearHistory = async () => {
    setIsUpdating(true)
    setError('')

    const { error: clearError } = await getSupabaseClient().functions.invoke(
      'search-history',
      { body: { action: 'clear' } },
    )

    if (clearError) {
      setError(clearError.message)
    } else {
      setItems([])
      setTotal(0)
    }
    setIsUpdating(false)
  }

  const downloadHistory = async () => {
    setIsDownloading(true)
    setError('')

    const { data, error: downloadError } =
      await getSupabaseClient().functions.invoke('search-history', {
        body: { action: 'download' },
      })

    if (downloadError || !data) {
      setError(downloadError?.message ?? 'Unable to download search history.')
      setIsDownloading(false)
      return
    }

    const file = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = url
    link.download = `locus-search-history-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(url)
    setIsDownloading(false)
  }

  return (
    <div className="w-full max-w-[780px]">
      <h1 className="text-[28px] font-bold leading-tight text-[#17171D]">
        Search
      </h1>
      <p className="mt-1 text-[15px] text-[#7B8393]">
        Review and manage your search history.
      </p>

      <section className="mt-6 rounded-[12px] border border-[#E1E3E9] bg-white px-7 py-5">
        <div className="flex items-start justify-between gap-6">
          <div>
            <h2 className="text-[15px] font-semibold text-[#24242A]">
              Save search history
            </h2>
            <p className="mt-2 max-w-[610px] text-[14px] leading-5 text-[#7A8292]">
              Store your searches so you can revisit and download your history.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-label="Save search history"
            aria-checked={saveHistory}
            disabled={isLoading || isUpdating}
            onClick={() => void toggleHistory()}
            className={`relative mt-0.5 h-7 w-12 shrink-0 rounded-full border transition-colors disabled:cursor-wait disabled:opacity-60 ${
              saveHistory
                ? 'border-[#4B3BD4] bg-[#4B3BD4]'
                : 'border-[#8A93A3] bg-white'
            }`}
          >
            <span
              className={`absolute top-[3px] h-5 w-5 rounded-full transition-transform ${
                saveHistory
                  ? 'left-[3px] translate-x-5 bg-white'
                  : 'left-[3px] translate-x-0 bg-[#7B8494]'
              }`}
            />
          </button>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-[13px] font-semibold tracking-[0.08em] text-[#777F8E] uppercase">
          Recent Searches
        </h2>

        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[14px] text-[#7A8292]">
            Showing{' '}
            <span className="font-semibold text-[#4B3BD4]">
              {Math.min(total, 20)}
            </span>{' '}
            Recent {total === 1 ? 'Query' : 'Queries'}
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={isLoading || isDownloading || total === 0}
              onClick={() => void downloadHistory()}
              className="flex h-10 items-center gap-2 rounded-[8px] border border-[#DEE1E8] bg-white px-5 text-[14px] font-semibold text-[#4B3BD4] hover:bg-[#F8F7FF] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <DownloadIcon />
              {isDownloading ? 'Downloading...' : 'Download Log'}
            </button>
            <button
              type="button"
              disabled={isLoading || isUpdating || total === 0}
              onClick={() => void clearHistory()}
              className="flex h-10 items-center gap-2 rounded-[8px] border border-[#DEE1E8] bg-white px-5 text-[14px] font-semibold text-[#B4232C] hover:bg-[#FFF7F7] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <TrashIcon />
              Clear All
            </button>
          </div>
        </div>

        <div className="mt-4 overflow-hidden rounded-[12px] border border-[#E1E3E9] bg-white">
          <div className="grid grid-cols-[minmax(0,1fr)_130px] border-b border-[#E7E8ED] px-7 py-4 text-[14px] font-medium text-[#24242A]">
            <span>Query</span>
            <span>results</span>
          </div>

          {isLoading ? (
            <div className="px-7 py-12 text-center text-[14px] text-[#7A8292]">
              Loading search history...
            </div>
          ) : items.length === 0 ? (
            <div className="px-7 py-12 text-center text-[14px] text-[#7A8292]">
              No recent search history
            </div>
          ) : (
            items.slice(0, 20).map((item) => (
              <div
                key={item.id}
                className="grid grid-cols-[minmax(0,1fr)_130px] items-center border-b border-[#E7E8ED] px-7 py-4 last:border-b-0"
              >
                <div className="min-w-0 pr-5">
                  <p className="truncate text-[14px] text-[#24242A]">
                    {item.query}
                  </p>
                  <p className="mt-1 text-[12px] text-[#7A8292]">
                    {formatSearchAge(item.searched_at)}
                  </p>
                </div>
                <p className="text-[14px] text-[#7A8292]">
                  <span className="font-semibold text-[#24242A]">
                    {item.result_count}
                  </span>{' '}
                  {item.result_count === 1 ? 'result' : 'results'}
                </p>
              </div>
            ))
          )}
        </div>

        {error ? (
          <p role="alert" className="mt-3 text-[13px] text-[#B4232C]">
            {error}
          </p>
        ) : null}
      </section>
    </div>
  )
}

function AccountSettings() {
  const navigate = useNavigate()
  const [name, setName] = useState('Locus User')
  const [email, setEmail] = useState('No signed-in email')
  const [draftName, setDraftName] = useState(name)
  const [isEditing, setIsEditing] = useState(false)
  const [confirmation, setConfirmation] = useState<'logout' | 'delete' | null>(
    null,
  )
  const [isPlanPickerOpen, setIsPlanPickerOpen] = useState(false)
  const [isBillingOpen, setIsBillingOpen] = useState(false)
  const [isSigningOut, setIsSigningOut] = useState(false)
  const [isDeletingAccount, setIsDeletingAccount] = useState(false)
  const [accountActionError, setAccountActionError] = useState('')
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState('')

  useEffect(() => {
    const supabase = getSupabaseClient()

    const applyUser = (user: User | null) => {
      if (!user) {
        setName('Locus User')
        setEmail('No signed-in email')
        return
      }

      const userEmail = user.email ?? 'No signed-in email'
      const emailName =
        user.email
          ?.split('@')[0]
          .split(/[._-]+/)
          .filter(Boolean)
          .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
          .join(' ') || 'Locus User'
      const displayName =
        user.user_metadata.full_name ||
        user.user_metadata.name ||
        user.user_metadata.display_name ||
        emailName

      setName(String(displayName))
      setEmail(userEmail)
    }

    void supabase.auth.getSession().then(({ data }) => {
      applyUser(data.session?.user ?? null)
    })

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      applyUser(session?.user ?? null)
    })

    return () => data.subscription.unsubscribe()
  }, [])

  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')

  const openEditor = () => {
    setDraftName(name)
    setIsEditing(true)
  }

  const saveEditor = () => {
    const nextName = draftName.trim()
    if (!nextName) return
    setName(nextName)
    setIsEditing(false)
  }

  const logOut = async () => {
    setIsSigningOut(true)
    setAccountActionError('')

    const { error } = await getSupabaseClient().auth.signOut()
    if (error) {
      setAccountActionError(error.message)
      setIsSigningOut(false)
      return
    }

    navigate('/', { replace: true })
  }

  const deleteAccount = async () => {
    setIsDeletingAccount(true)
    setAccountActionError('')

    const supabase = getSupabaseClient()
    const { data } = await supabase.auth.getSession()
    if (!data.session) {
      setAccountActionError('Your session has expired. Please sign in again.')
      setIsDeletingAccount(false)
      return
    }

    const { error } = await supabase.functions.invoke('delete-account', {
      body: {},
    })

    if (error) {
      setAccountActionError(error.message)
      setIsDeletingAccount(false)
      return
    }

    await supabase.auth.signOut({ scope: 'local' })
    navigate('/', { replace: true })
  }

  const exportData = async () => {
    setIsExporting(true)
    setExportError('')

    const supabase = getSupabaseClient()
    const { data: sessionData } = await supabase.auth.getSession()
    if (!sessionData.session) {
      setExportError('Your session has expired. Please sign in again.')
      setIsExporting(false)
      return
    }

    const { data, error } = await supabase.functions.invoke(
      'export-account-data',
      { body: {} },
    )

    if (error || !data) {
      setExportError(error?.message ?? 'Unable to export account data.')
      setIsExporting(false)
      return
    }

    const file = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = url
    link.download = `locus-data-export-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(url)
    setIsExporting(false)
  }

  return (
    <>
      <h1 className="text-[28px] font-bold leading-tight text-[#17171D]">
        Account
      </h1>
      <p className="mt-1 text-[15px] text-[#7B8393]">
        Manage your account info.
      </p>

      <section className="mt-6 overflow-hidden rounded-[8px] border border-[#E1E3E9] bg-white">
        <div className="flex min-h-[100px] flex-col items-stretch justify-between gap-5 px-7 py-5 sm:flex-row sm:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-5">
            <div className="flex h-[60px] w-[60px] shrink-0 items-center justify-center rounded-full bg-[#F0EDFF] text-[17px] font-semibold text-[#5947DE]">
              {initials || 'LU'}
            </div>
            {isEditing ? (
              <div className="grid min-w-0 flex-1 grid-cols-[88px_minmax(0,360px)] items-center gap-x-3 gap-y-2.5">
                <label
                  htmlFor="account-name"
                  className="text-[15px] font-medium text-[#24242A]"
                >
                  Full Name
                </label>
                <input
                  id="account-name"
                  value={draftName}
                  placeholder="Please enter"
                  onChange={(event) => setDraftName(event.target.value)}
                  className="h-10 min-w-0 rounded-full border border-[#5947DE] px-4 text-[15px] text-[#25252B] outline-none focus:ring-2 focus:ring-[#5947DE]/15"
                  autoFocus
                />
                <span className="text-[15px] font-medium text-[#24242A]">
                  Email
                </span>
                <span className="min-w-0 truncate text-[15px] text-[#7A8292]">
                  {email}
                </span>
              </div>
            ) : (
              <div className="min-w-0">
                <h2 className="truncate text-[16px] font-semibold text-[#24242A]">
                  {name}
                </h2>
                <p className="mt-1 truncate text-[15px] text-[#7A8292]">
                  {email}
                </p>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={isEditing ? saveEditor : openEditor}
            disabled={isEditing && !draftName.trim()}
            className="h-11 w-full shrink-0 rounded-[8px] bg-[#4B3BD4] px-8 text-[15px] font-semibold text-white transition-colors hover:bg-[#3F30BC] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4B3BD4] sm:w-auto"
          >
            {isEditing ? 'Save Edit' : 'Edit Info'}
          </button>
        </div>

        <div className="flex min-h-[84px] flex-col items-stretch justify-between gap-3 border-t border-[#E7E8ED] px-7 py-4 sm:flex-row sm:items-center">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-[15px] font-semibold text-[#24242A]">
                Subscription
              </h2>
              <span className="rounded-full bg-[#E8E9ED] px-2.5 py-1 text-[13px] font-medium text-[#7B8290]">
                Free
              </span>
            </div>
            <p className="mt-1.5 text-[14px] text-[#7A8292]">Learn our plans.</p>
          </div>
          <button
            type="button"
            onClick={() => setIsPlanPickerOpen(true)}
            className="h-10 shrink-0 rounded-[8px] border border-[#DEE1E8] bg-white px-6 text-[14px] font-semibold text-[#4B3BD4] hover:bg-[#F8F7FF]"
          >
            Change Plan
          </button>
        </div>

        <div className="flex min-h-[84px] flex-col items-stretch justify-between gap-3 border-t border-[#E7E8ED] px-7 py-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-[15px] font-semibold text-[#24242A]">Billing</h2>
            <p className="mt-1.5 text-[14px] text-[#7A8292]">
              Manage your subscription and invoices.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsBillingOpen(true)}
            className="h-10 shrink-0 rounded-[8px] border border-[#DEE1E8] bg-white px-6 text-[14px] font-semibold text-[#4B3BD4] hover:bg-[#F8F7FF]"
          >
            Billing Information
          </button>
        </div>

        <div className="flex min-h-[84px] flex-col items-stretch justify-between gap-3 border-t border-[#E7E8ED] px-7 py-4 sm:flex-row sm:items-center">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-[#24242A]">
              Export Data
            </h2>
            <p className="mt-1.5 text-[14px] leading-5 text-[#7A8292]">
              Download all your captured decisions, action items, and blockers
              as JSON.
            </p>
            {exportError ? (
              <p role="alert" className="mt-1.5 text-[13px] text-[#B4232C]">
                {exportError}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            disabled={isExporting}
            onClick={() => void exportData()}
            className="h-10 shrink-0 rounded-[8px] border border-[#DEE1E8] bg-white px-6 text-[14px] font-semibold text-[#4B3BD4] hover:bg-[#F8F7FF] disabled:cursor-wait disabled:opacity-60"
          >
            {isExporting ? 'Exporting...' : 'Export'}
          </button>
        </div>

        <div className="flex min-h-[84px] flex-col items-stretch justify-between gap-3 border-t border-[#E7E8ED] px-7 py-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-[15px] font-semibold text-[#24242A]">Log Out</h2>
            <p className="mt-1.5 text-[14px] leading-5 text-[#7A8292]">
              Sign out of your account. You can log back in at any time.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setAccountActionError('')
              setConfirmation('logout')
            }}
            className="h-10 shrink-0 rounded-[8px] border border-[#DEE1E8] bg-white px-6 text-[14px] font-semibold text-[#4B3BD4] hover:bg-[#F8F7FF]"
          >
            Log Out
          </button>
        </div>

        <div className="flex min-h-[84px] flex-col items-stretch justify-between gap-3 border-t border-[#E7E8ED] px-7 py-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-[15px] font-semibold text-[#24242A]">
              Delete Account
            </h2>
            <p className="mt-1.5 text-[14px] leading-5 text-[#7A8292]">
              Permanently delete your account and all associated data. This
              cannot be undone.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setConfirmation('delete')}
            className="flex h-10 shrink-0 items-center gap-2 rounded-[8px] border border-[#DEE1E8] bg-white px-6 text-[14px] font-semibold text-[#B4232C] hover:bg-[#FFF7F7]"
          >
            <TrashIcon />
            Delete
          </button>
        </div>
      </section>

      {confirmation ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4"
          role="presentation"
          onMouseDown={(event) => {
            if (
              event.target === event.currentTarget &&
              !isSigningOut &&
              !isDeletingAccount
            ) {
              setConfirmation(null)
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="account-confirmation-title"
            className="relative w-full max-w-[500px] rounded-[8px] bg-white p-8 shadow-[0_20px_55px_rgba(17,24,39,0.22)]"
          >
            <button
              type="button"
              aria-label="Close dialog"
              disabled={isSigningOut || isDeletingAccount}
              onClick={() => setConfirmation(null)}
              className="absolute top-4 right-4 flex h-8 w-8 items-center justify-center text-[28px] font-light leading-none text-[#5042D7] hover:text-[#372AAE] disabled:opacity-50"
            >
              &times;
            </button>
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-full ${
                confirmation === 'delete'
                  ? 'bg-[#FFF1F1] text-[#D93636]'
                  : 'bg-[#F0F8FF] text-[#4B3BD4]'
              }`}
            >
              {confirmation === 'delete' ? (
                <TrashIcon />
              ) : (
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M8 3h8M7 5h10v14H7zM9.5 12l1.7 1.7L15 9.8"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </div>
            <h2
              id="account-confirmation-title"
              className="mt-5 text-[20px] font-semibold text-[#202027]"
            >
              {confirmation === 'delete'
                ? 'Delete account?'
                : 'Log out of Locus?'}
            </h2>
            <p className="mt-3 text-[15px] leading-6 text-[#7A8292]">
              {confirmation === 'delete'
                ? 'This will permanently delete your account and all associated decisions, action items, and data. This action cannot be undone.'
                : "You'll be signed out of your account on this device. Your data and settings will be saved."}
            </p>
            {accountActionError ? (
              <p role="alert" className="mt-3 text-[14px] text-[#B4232C]">
                {accountActionError}
              </p>
            ) : null}
            <div className="mt-6 grid grid-cols-2 gap-3">
              <button
                type="button"
                disabled={isSigningOut || isDeletingAccount}
                onClick={() => setConfirmation(null)}
                className="h-11 rounded-[7px] border border-[#DEE1E8] bg-white px-4 text-[15px] font-semibold text-[#4B3BD4] hover:bg-[#F8F7FF] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSigningOut || isDeletingAccount}
                onClick={
                  confirmation === 'logout'
                    ? () => void logOut()
                    : () => void deleteAccount()
                }
                className={`h-11 rounded-[7px] px-5 text-[15px] font-semibold text-white disabled:cursor-wait disabled:opacity-60 ${
                  confirmation === 'delete'
                    ? 'bg-[#9D2A26] hover:bg-[#84221F]'
                    : 'bg-[#4B3BD4] hover:bg-[#3F30BC]'
                }`}
              >
                {confirmation === 'delete'
                  ? isDeletingAccount
                    ? 'Deleting account...'
                    : 'Yes, delete my account'
                  : isSigningOut
                    ? 'Logging out...'
                    : 'Log out'}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {isPlanPickerOpen ? (
        <PlanPicker onClose={() => setIsPlanPickerOpen(false)} />
      ) : null}

      {isBillingOpen ? (
        <BillingInformation
          onClose={() => setIsBillingOpen(false)}
          onUpdate={() => {
            setIsBillingOpen(false)
            setIsPlanPickerOpen(true)
          }}
        />
      ) : null}
    </>
  )
}

export default function SettingsPage() {
  const [activeSection, setActiveSection] =
    useState<SettingsSection>('Account')
  const [pauseCapture, setPauseCapture] = useState(false)
  const [captureMode, setCaptureMode] =
    useState<CaptureMode>('decisions-actions')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('All')
  const [channels, setChannels] = useState(INITIAL_CHANNELS)

  const visibleChannels = useMemo(() => {
    if (sourceFilter === 'All') return channels
    return channels.filter((channel) => channel.app === sourceFilter)
  }, [channels, sourceFilter])

  const includedCount = channels.filter((channel) => channel.included).length
  const excludedCount = channels.length - includedCount

  const toggleChannel = (id: string) => {
    setChannels((current) =>
      current.map((channel) =>
        channel.id === id
          ? { ...channel, included: !channel.included }
          : channel,
      ),
    )
  }

  const usesFullSettingsLayout =
    activeSection === 'Account' || activeSection === 'Search'

  return (
    <div
      className={
        usesFullSettingsLayout
          ? 'flex min-h-[calc(100vh-56px)] flex-col md:flex-row'
          : 'mx-auto flex max-w-[1120px] gap-8 px-8 py-8'
      }
    >
        <aside
          className={
            usesFullSettingsLayout
              ? 'w-full shrink-0 border-b border-[#E6E7EC] bg-white px-6 py-8 md:w-[280px] md:border-r md:border-b-0 md:px-8'
              : 'w-[220px] shrink-0'
          }
        >
          <h2 className="mb-4 text-[18px] font-bold text-[#111827]">Settings</h2>
          <nav className="flex flex-col gap-1">
            {SIDEBAR_ITEMS.map((item) => {
              const isActive = activeSection === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveSection(item.id)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-3 text-left text-[15px] font-medium transition-colors ${
                    isActive
                      ? 'bg-[#EEEBFF] text-[#5A45FF]'
                      : 'text-[#4B5563] hover:bg-[#F3F4F6]'
                  }`}
                >
                  <span className={isActive ? 'text-[#5A45FF]' : 'text-[#6B7280]'}>
                    {SIDEBAR_ICONS[item.id]}
                  </span>
                  {item.label}
                </button>
              )
            })}
          </nav>
        </aside>

        <main
          className={
            usesFullSettingsLayout
              ? 'min-w-0 flex-1 px-5 py-8 sm:px-8 lg:px-10'
              : 'min-w-0 flex-1'
          }
        >
          {activeSection === 'Account' ? (
            <div className="w-full max-w-[1080px]">
              <AccountSettings />
            </div>
          ) : activeSection === 'Search' ? (
            <SearchSettings />
          ) : activeSection === 'Capture Controls' ? (
            <>
              <h1 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
                Capture Controls
              </h1>
              <p className="mt-1 text-[14px] text-[#6B7280]">
                Control what Locus reads, from where, and when.
              </p>

              <section className="mt-8">
                <h3 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
                  Capture Mode
                </h3>

                <div className="rounded-2xl border border-[#E8E8ED] bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[15px] font-semibold text-[#111827]">
                        Pause all capture
                      </p>
                      <p className="mt-1 max-w-[520px] text-[13px] leading-relaxed text-[#6B7280]">
                        Temporarily stop Locus from reading new messages. All
                        existing captures are preserved and search remains
                        available.
                      </p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={pauseCapture}
                      onClick={() => setPauseCapture((value) => !value)}
                      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                        pauseCapture ? 'bg-[#5A45FF]' : 'bg-[#D1D5DB]'
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                          pauseCapture ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setCaptureMode('decisions-actions')}
                    className={`rounded-2xl border bg-white p-4 text-left transition-colors ${
                      captureMode === 'decisions-actions'
                        ? 'border-[#5A45FF]'
                        : 'border-[#E8E8ED] hover:border-[#C7C7D1]'
                    }`}
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <span
                        className={`flex h-4 w-4 items-center justify-center rounded-full border-2 ${
                          captureMode === 'decisions-actions'
                            ? 'border-[#5A45FF]'
                            : 'border-[#D1D5DB]'
                        }`}
                      >
                        {captureMode === 'decisions-actions' ? (
                          <span className="h-2 w-2 rounded-full bg-[#5A45FF]" />
                        ) : null}
                      </span>
                      <span className="text-[14px] font-semibold text-[#111827]">
                        Decisions+ Actions
                      </span>
                    </div>
                    <p className="text-[13px] leading-relaxed text-[#6B7280]">
                      Also capture action items and blockers. Recommended for
                      full team visibility.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setCaptureMode('decisions-only')}
                    className={`rounded-2xl border bg-white p-4 text-left transition-colors ${
                      captureMode === 'decisions-only'
                        ? 'border-[#5A45FF]'
                        : 'border-[#E8E8ED] hover:border-[#C7C7D1]'
                    }`}
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <span
                        className={`flex h-4 w-4 items-center justify-center rounded-full border-2 ${
                          captureMode === 'decisions-only'
                            ? 'border-[#5A45FF]'
                            : 'border-[#D1D5DB]'
                        }`}
                      >
                        {captureMode === 'decisions-only' ? (
                          <span className="h-2 w-2 rounded-full bg-[#5A45FF]" />
                        ) : null}
                      </span>
                      <span className="text-[14px] font-semibold text-[#111827]">
                        Decisions only
                      </span>
                    </div>
                    <p className="text-[13px] leading-relaxed text-[#6B7280]">
                      Only capture explicit decisions and conclusions. Lower
                      volume, higher precision.
                    </p>
                  </button>
                </div>
              </section>

              <section className="mt-8">
                <h3 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
                  Channels & Source Rules
                </h3>

                <div className="mb-3 flex flex-wrap gap-2">
                  {SOURCE_FILTERS.map((filter) => {
                    const isActive = sourceFilter === filter
                    return (
                      <button
                        key={filter}
                        type="button"
                        onClick={() => setSourceFilter(filter)}
                        className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
                          isActive
                            ? 'bg-[#5A45FF] text-white'
                            : 'border border-[#E5E7EB] bg-white text-[#5A45FF] hover:bg-[#F8F7FF]'
                        }`}
                      >
                        {filter}
                      </button>
                    )
                  })}
                </div>

                <p className="mb-3 text-[13px]">
                  <span className="font-semibold text-[#5A45FF]">
                    {includedCount} Included
                  </span>
                  <span className="mx-2 text-[#9CA3AF]">{excludedCount} Excluded</span>
                </p>

                <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
                  <table className="w-full border-collapse text-left">
                    <thead>
                      <tr className="border-b border-[#F0F0F4]">
                        <th className="w-12 px-4 py-3" />
                        <th className="px-4 py-3 text-[12px] font-semibold text-[#9CA3AF]">
                          Channel/Page Name
                        </th>
                        <th className="px-4 py-3 text-[12px] font-semibold text-[#9CA3AF]">
                          Status
                        </th>
                        <th className="px-4 py-3 text-[12px] font-semibold text-[#9CA3AF]">
                          App
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleChannels.map((channel, index) => (
                        <tr
                          key={channel.id}
                          className={
                            index < visibleChannels.length - 1
                              ? 'border-b border-[#F0F0F4]'
                              : ''
                          }
                        >
                          <td className="px-4 py-3.5">
                            <button
                              type="button"
                              aria-label={
                                channel.included
                                  ? `Exclude ${channel.name}`
                                  : `Include ${channel.name}`
                              }
                              onClick={() => toggleChannel(channel.id)}
                              className={`flex h-4 w-4 items-center justify-center rounded-full border-2 ${
                                channel.included
                                  ? 'border-[#5A45FF]'
                                  : 'border-[#D1D5DB]'
                              }`}
                            >
                              {channel.included ? (
                                <span className="h-2 w-2 rounded-full bg-[#5A45FF]" />
                              ) : null}
                            </button>
                          </td>
                          <td className="px-4 py-3.5 text-[14px] font-medium text-[#111827]">
                            {channel.name}
                          </td>
                          <td className="px-4 py-3.5">
                            {channel.included ? (
                              <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#16A34A]">
                                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#DCFCE7] text-[10px]">
                                  ✓
                                </span>
                                Included
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#9CA3AF]">
                                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#F3F4F6] text-[10px]">
                                  ×
                                </span>
                                Excluded
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3.5 text-[14px] text-[#6B7280]">
                            {channel.app}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : (
            <div className="rounded-2xl border border-[#E8E8ED] bg-white p-8">
              <h1 className="text-[28px] font-bold text-[#111827]">
                {activeSection}
              </h1>
              <p className="mt-2 text-[14px] text-[#6B7280]">
                This settings section will be available soon.
              </p>
            </div>
          )}
        </main>
      </div>
  )
}
