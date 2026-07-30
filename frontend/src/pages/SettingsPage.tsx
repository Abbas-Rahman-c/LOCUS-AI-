import { useMemo, useState, type ReactNode } from 'react'
import AccountSettings from './AccountSettings'

type SettingsSection =
  | 'Account'
  | 'Connected Sources'
  | 'Capture Controls'
  | 'Privacy'
  | 'Search'
  | 'Notifications'

type CaptureMode = 'decisions-actions' | 'decisions-only'
type SourceFilter = 'All' | 'Gmail' | 'Notion' | 'Slack'
type SourceStatus = 'active' | 'expiring' | 'disconnected'

type ChannelRow = {
  id: string
  name: string
  included: boolean
  app: SourceFilter
}

type ConnectedSource = {
  id: 'slack' | 'notion' | 'gmail'
  name: string
  icon: string
  status: SourceStatus
}

type RecentSearch = {
  id: string
  query: string
  time: string
  count: number
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

const INITIAL_SOURCES: ConnectedSource[] = [
  { id: 'slack', name: 'Slack', icon: '/slack-logo.png', status: 'active' },
  { id: 'notion', name: 'Notion', icon: '/notion-logo.png', status: 'expiring' },
  { id: 'gmail', name: 'Gmail', icon: '/gmail-logo.png', status: 'disconnected' },
]

const INITIAL_SEARCHES: RecentSearch[] = Array.from({ length: 12 }, (_, index) => ({
  id: String(index + 1),
  query: 'What did we decide about the Q3 timeline?',
  time: '2h ago',
  count: 9,
}))

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

function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M20 12a8 8 0 1 1-2.3-5.6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M20 4v5h-5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function TrashIcon({ color = 'currentColor' }: { color?: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 7h16M9 7V5h6v2M8 7l1 12h6l1-12"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function WarningIcon({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3.5 2.8 19.5h18.4L12 3.5Z"
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M12 9v5" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="12" cy="16.5" r="1" fill={color} />
    </svg>
  )
}

function ClockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="8" stroke="#5A45FF" strokeWidth="1.8" />
      <path d="M12 8v4.5l3 2" stroke="#5A45FF" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 4v10M8 10l4 4 4-4M5 18h14"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: () => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
        checked ? 'bg-[#5A45FF]' : 'bg-[#D1D5DB]'
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

function statusMeta(status: SourceStatus) {
  if (status === 'active') {
    return { label: 'Active', color: '#16A34A', dot: '#22C55E' }
  }
  if (status === 'expiring') {
    return { label: 'Token Expiring', color: '#EA580C', dot: '#F97316' }
  }
  return { label: 'Disconnected', color: '#DC2626', dot: '#EF4444' }
}

const SIDEBAR_ICONS: Record<SettingsSection, ReactNode> = {
  Account: <AccountIcon />,
  'Connected Sources': <LightningIcon />,
  'Capture Controls': <HashIcon />,
  Privacy: <ShieldIcon />,
  Search: <SearchIcon />,
  Notifications: <BellIcon />,
}

export default function SettingsPage() {
  const [activeSection, setActiveSection] =
    useState<SettingsSection>('Connected Sources')
  const [pauseCapture, setPauseCapture] = useState(false)
  const [captureMode, setCaptureMode] =
    useState<CaptureMode>('decisions-actions')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('All')
  const [channels, setChannels] = useState(INITIAL_CHANNELS)
  const [sources, setSources] = useState(INITIAL_SOURCES)
  const [blockCookies, setBlockCookies] = useState(false)
  const [excludePrivate, setExcludePrivate] = useState(false)
  const [excludeDms, setExcludeDms] = useState(false)
  const [saveSearchHistory, setSaveSearchHistory] = useState(false)
  const [recentSearches, setRecentSearches] = useState(INITIAL_SEARCHES)
  const [weeklyPulse, setWeeklyPulse] = useState(true)
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [inAppNotifications, setInAppNotifications] = useState(true)

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

  const reconnectSource = (id: ConnectedSource['id']) => {
    setSources((current) =>
      current.map((source) =>
        source.id === id ? { ...source, status: 'active' } : source,
      ),
    )
  }

  const disconnectSource = (id: ConnectedSource['id']) => {
    setSources((current) =>
      current.map((source) =>
        source.id === id ? { ...source, status: 'disconnected' } : source,
      ),
    )
  }

  const clearCookies = () => {
    setBlockCookies(false)
    window.alert('Cookies cleared. You will need to sign in again on next visit.')
  }

  const downloadSearchLog = () => {
    const rows = [
      'query,time,results',
      ...recentSearches.map(
        (item) => `"${item.query}",${item.time},${item.count}`,
      ),
    ]
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'locus-search-history.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-auto flex max-w-[1120px] gap-8 px-8 py-8">
      <aside className="w-[220px] shrink-0">
        <h2 className="mb-4 text-[18px] font-bold text-[#111827]">Settings</h2>
        <nav className="flex flex-col gap-1">
          {SIDEBAR_ITEMS.map((item) => {
            const isActive = activeSection === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveSection(item.id)}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-[14px] font-medium transition-colors ${
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

      <main className="min-w-0 flex-1">
        {activeSection === 'Account' ? (
          <AccountSettings />
        ) : activeSection === 'Connected Sources' ? (
          <>
            <h1 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
              Connected Sources
            </h1>
            <p className="mt-1 text-[14px] text-[#6B7280]">
              Manage the tools Locus reads to capture decisions and actions.
            </p>

            <div className="mt-8 overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
              {sources.map((source, index) => {
                const status = statusMeta(source.status)
                return (
                  <div
                    key={source.id}
                    className={`flex flex-col gap-4 px-5 py-5 md:flex-row md:items-start md:justify-between ${
                      index < sources.length - 1 ? 'border-b border-[#F0F0F4]' : ''
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start gap-3">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[#E5E7EB] bg-white">
                          <img
                            src={source.icon}
                            alt=""
                            className="h-7 w-7 object-contain"
                          />
                        </div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-[15px] font-semibold text-[#111827]">
                              {source.name}
                            </h3>
                            <span
                              className="inline-flex items-center gap-1.5 text-[13px] font-medium"
                              style={{ color: status.color }}
                            >
                              <span
                                className="h-1.5 w-1.5 rounded-full"
                                style={{ backgroundColor: status.dot }}
                              />
                              {status.label}
                            </span>
                          </div>
                          <p className="mt-1 text-[13px] text-[#9CA3AF]">
                            Synced today 9:00 am
                          </p>
                          <p className="mt-2 text-[13px] font-semibold text-[#4F46E5]">
                            142 captures
                            <span className="mx-2 font-normal text-[#C7C7D1]">·</span>
                            12 channels monitored
                          </p>
                          {source.status === 'expiring' ? (
                            <p className="mt-2 inline-flex items-start gap-1.5 text-[13px] text-[#EA580C]">
                              <WarningIcon color="#EA580C" />
                              OAuth token expires in ~2 days. Reconnect to avoid
                              interruption.
                            </p>
                          ) : null}
                          {source.status === 'disconnected' ? (
                            <p className="mt-2 inline-flex items-start gap-1.5 text-[13px] text-[#DC2626]">
                              <WarningIcon color="#DC2626" />
                              Reconnect to keep the source active.
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2 md:pt-1">
                      <button
                        type="button"
                        onClick={() => reconnectSource(source.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[#C4B5FD] bg-white px-3 py-1.5 text-[13px] font-semibold text-[#5A45FF] transition-colors hover:bg-[#F8F7FF]"
                      >
                        <RefreshIcon />
                        Reconnect
                      </button>
                      <button
                        type="button"
                        onClick={() => disconnectSource(source.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[#FECACA] bg-white px-3 py-1.5 text-[13px] font-semibold text-[#DC2626] transition-colors hover:bg-[#FEF2F2]"
                      >
                        <TrashIcon color="#DC2626" />
                        Disconnect
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
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
                  <Toggle
                    checked={pauseCapture}
                    onChange={() => setPauseCapture((value) => !value)}
                    label="Pause all capture"
                  />
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
        ) : activeSection === 'Privacy' ? (
          <>
            <h1 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
              Privacy
            </h1>
            <p className="mt-1 text-[14px] text-[#6B7280]">
              Control what Locus can read and how long data is kept.
            </p>

            <div className="mt-8 rounded-2xl border border-[#E8E8ED] bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
              <div className="flex items-start gap-3">
                <ClockIcon />
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-semibold text-[#111827]">
                    Raw message retention: 24 hours
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-[#6B7280]">
                    Locus reads messages to extract structured captures, then
                    permanently deletes the raw content within 24 hours. Only the
                    extracted decision, action item, or blocker is stored — never
                    the full message thread.
                  </p>
                  <div className="mt-5">
                    <div className="h-1.5 overflow-hidden rounded-full bg-[#EDE9FE]">
                      <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-[#5A45FF] to-[#C4B5FD]" />
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[12px] font-medium text-[#6B7280]">
                      <span>Ingested</span>
                      <span className="text-[#C7C7D1]">→</span>
                      <span>Extracted</span>
                      <span className="text-[#C7C7D1]">→</span>
                      <span>Deleted</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <section className="mt-8">
              <h3 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
                Cookie Controls
              </h3>
              <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
                <div className="flex items-start justify-between gap-4 border-b border-[#F0F0F4] px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold text-[#111827]">
                      Block non-essential cookies
                    </p>
                    <p className="mt-1 max-w-[560px] text-[13px] leading-relaxed text-[#6B7280]">
                      Only keeps the cookies strictly required for Locus to
                      function, such as your login session and security tokens.
                      Turning this on may mean your preferences and filter
                      settings won&apos;t be remembered between visits.
                    </p>
                  </div>
                  <Toggle
                    checked={blockCookies}
                    onChange={() => setBlockCookies((value) => !value)}
                    label="Block non-essential cookies"
                  />
                </div>
                <div className="flex items-start justify-between gap-4 px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold text-[#111827]">
                      Clear cookies
                    </p>
                    <p className="mt-1 max-w-[560px] text-[13px] leading-relaxed text-[#6B7280]">
                      Clears all stored cookies and session data from your
                      browser. You&apos;ll be logged out immediately and will
                      need to sign in again.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={clearCookies}
                    className="shrink-0 rounded-lg border border-[#E5E7EB] bg-white px-3.5 py-2 text-[13px] font-semibold text-[#5A45FF] transition-colors hover:bg-[#F8F7FF]"
                  >
                    Clear Cookies
                  </button>
                </div>
              </div>
            </section>

            <section className="mt-8">
              <h3 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
                Message Scope
              </h3>
              <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
                <div className="flex items-start justify-between gap-4 border-b border-[#F0F0F4] px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold text-[#111827]">
                      Exclude private channels
                    </p>
                    <p className="mt-1 max-w-[560px] text-[13px] leading-relaxed text-[#6B7280]">
                      Locus will skip private Slack channels entirely, even if
                      you&apos;re a member and have granted access.
                    </p>
                  </div>
                  <Toggle
                    checked={excludePrivate}
                    onChange={() => setExcludePrivate((value) => !value)}
                    label="Exclude private channels"
                  />
                </div>
                <div className="flex items-start justify-between gap-4 px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold text-[#111827]">
                      Exclude direct messages
                    </p>
                    <p className="mt-1 max-w-[560px] text-[13px] leading-relaxed text-[#6B7280]">
                      DMs and group DMs are never read or captured, regardless of
                      content.
                    </p>
                  </div>
                  <Toggle
                    checked={excludeDms}
                    onChange={() => setExcludeDms((value) => !value)}
                    label="Exclude direct messages"
                  />
                </div>
              </div>
            </section>

            <div className="mt-8 rounded-2xl border border-[#E8E8ED] bg-white px-5 py-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[15px] font-semibold text-[#111827]">
                  Data processing region
                </p>
                <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#16A34A]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E]" />
                  EU · Frankfurt
                </span>
              </div>
              <p className="mt-1 text-[13px] text-[#6B7280]">
                Your data is processed and stored in EU-West (Frankfurt,
                Germany).
              </p>
            </div>

            <section className="mt-8">
              <h3 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
                Our Commitments
              </h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  {
                    id: 'readonly-oauth',
                    icon: <ShieldIcon />,
                    text: 'Read-only OAuth — Locus never writes to Slack, Notion, or Gmail.',
                  },
                  {
                    id: 'raw-deleted',
                    icon: <ClockIcon />,
                    text: 'Raw messages deleted within 24 hours of ingestion.',
                  },
                  {
                    id: 'no-training',
                    icon: (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <circle cx="12" cy="12" r="8" stroke="#5A45FF" strokeWidth="1.8" />
                        <path d="M9 9l6 6M15 9l-6 6" stroke="#5A45FF" strokeWidth="1.8" strokeLinecap="round" />
                      </svg>
                    ),
                    text: 'We never train AI models on your workspace data.',
                  },
                  {
                    id: 'readonly-oauth-check',
                    icon: (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z"
                          stroke="#5A45FF"
                          strokeWidth="1.8"
                          strokeLinejoin="round"
                        />
                        <path d="M9 12l2 2 4-4" stroke="#5A45FF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    ),
                    text: 'Read-only OAuth — Locus never writes to Slack, Notion, or Gmail.',
                  },
                ].map((item) => (
                  <div
                    key={item.id}
                    className="flex items-start gap-3 rounded-2xl border border-[#E8E8ED] bg-white p-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]"
                  >
                    <span className="mt-0.5 text-[#5A45FF]">{item.icon}</span>
                    <p className="text-[13px] leading-relaxed text-[#4B5563]">
                      {item.text}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          </>
        ) : activeSection === 'Search' ? (
          <>
            <h1 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
              Search
            </h1>
            <p className="mt-1 text-[14px] text-[#6B7280]">
              Review and manage your search history
            </p>

            <div className="mt-8 rounded-2xl border border-[#E8E8ED] bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[15px] font-semibold text-[#111827]">
                    Save search history
                  </p>
                  <p className="mt-1 max-w-[560px] text-[13px] leading-relaxed text-[#6B7280]">
                    Temporarily stop Locus from reading new messages. All
                    existing captures are preserved and search remains
                    available.
                  </p>
                </div>
                <Toggle
                  checked={saveSearchHistory}
                  onChange={() => setSaveSearchHistory((value) => !value)}
                  label="Save search history"
                />
              </div>
            </div>

            <section className="mt-8">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h3 className="text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
                    Recent Searches
                  </h3>
                  <p className="mt-1 text-[13px] font-semibold text-[#5A45FF]">
                    Showing {recentSearches.length} Recent Queries
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={downloadSearchLog}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#C4B5FD] bg-white px-3 py-1.5 text-[13px] font-semibold text-[#5A45FF] transition-colors hover:bg-[#F8F7FF]"
                  >
                    <DownloadIcon />
                    Download Log
                  </button>
                  <button
                    type="button"
                    onClick={() => setRecentSearches([])}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#FECACA] bg-white px-3 py-1.5 text-[13px] font-semibold text-[#DC2626] transition-colors hover:bg-[#FEF2F2]"
                  >
                    <TrashIcon color="#DC2626" />
                    Clear All
                  </button>
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
                <div className="grid grid-cols-[1fr_auto] gap-4 border-b border-[#F0F0F4] px-5 py-3">
                  <p className="text-[12px] font-semibold text-[#9CA3AF]">Query</p>
                  <p className="text-[12px] font-semibold text-[#9CA3AF]">results</p>
                </div>
                {recentSearches.length === 0 ? (
                  <p className="px-5 py-8 text-[14px] text-[#6B7280]">
                    No recent searches.
                  </p>
                ) : (
                  recentSearches.map((item, index) => (
                    <div
                      key={item.id}
                      className={`grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-4 ${
                        index < recentSearches.length - 1
                          ? 'border-b border-[#F0F0F4]'
                          : ''
                      }`}
                    >
                      <div>
                        <p className="text-[14px] font-semibold text-[#111827]">
                          {item.query}
                        </p>
                        <p className="mt-1 text-[12px] text-[#9CA3AF]">{item.time}</p>
                      </div>
                      <p className="text-[14px] text-[#111827]">
                        <span className="font-bold">{item.count}</span> results
                      </p>
                    </div>
                  ))
                )}
              </div>
            </section>
          </>
        ) : activeSection === 'Notifications' ? (
          <>
            <h1 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
              Notifications
            </h1>
            <p className="mt-1 text-[14px] text-[#6B7280]">
              Control how and when Locus reaches you.
            </p>

            <div className="mt-8 rounded-2xl border border-[#E8E8ED] bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[15px] font-semibold text-[#111827]">
                    Send Weekly Pulse
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-[#6B7280]">
                    Receive your Pulse summary on a recurring schedule.
                  </p>
                </div>
                <Toggle
                  checked={weeklyPulse}
                  onChange={() => setWeeklyPulse((value) => !value)}
                  label="Send Weekly Pulse"
                />
              </div>
            </div>

            <section className="mt-8">
              <h3 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
                Delivery Channels
              </h3>
              <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
                <div className="flex items-start justify-between gap-4 border-b border-[#F0F0F4] px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold text-[#111827]">Email</p>
                    <p className="mt-1 text-[13px] leading-relaxed text-[#6B7280]">
                      Send digest and system alerts to{' '}
                      <span className="text-[#6B7280]">jordan@acme.com</span>.
                    </p>
                  </div>
                  <Toggle
                    checked={emailNotifications}
                    onChange={() => setEmailNotifications((value) => !value)}
                    label="Email notifications"
                  />
                </div>
                <div className="flex items-start justify-between gap-4 px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold text-[#111827]">In App</p>
                    <p className="mt-1 max-w-[560px] text-[13px] leading-relaxed text-[#6B7280]">
                      Show a notification badge in the Locus dashboard when new
                      captures arrive.
                    </p>
                  </div>
                  <Toggle
                    checked={inAppNotifications}
                    onChange={() => setInAppNotifications((value) => !value)}
                    label="In app notifications"
                  />
                </div>
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
