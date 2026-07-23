import { useMemo, useState, type ReactNode } from 'react'

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

export default function SettingsPage() {
  const [activeSection, setActiveSection] =
    useState<SettingsSection>('Capture Controls')
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
          {activeSection === 'Capture Controls' ? (
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
