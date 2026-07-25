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

type ConnectedSource = {
  id: string
  name: string
  sync: string
  status: 'Active' | 'Disconnected'
  icon: ReactNode
}

const INITIAL_SOURCES: ConnectedSource[] = [
  { id: 'slack', name: 'Slack', sync: 'Synced today 9:00 am', status: 'Active', icon: <SlackIcon /> },
  { id: 'notion', name: 'Notion', sync: 'Synced today 9:00 am', status: 'Active', icon: <NotionIcon /> },
  { id: 'gmail', name: 'Gmail', sync: 'Not connected', status: 'Disconnected', icon: <GmailIcon /> },
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

function SlackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 122.8 122.8" aria-hidden="true">
      <path fill="#E01E5A" d="M25.8 77.6c0 7.1-5.8 12.9-12.9 12.9S0 84.7 0 77.6s5.8-12.9 12.9-12.9h12.9v12.9z" />
      <path fill="#E01E5A" d="M32.3 77.6c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9v32.3c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V77.6z" />
      <path fill="#36C5F0" d="M45.2 25.8c-7.1 0-12.9-5.8-12.9-12.9S38.1 0 45.2 0s12.9 5.8 12.9 12.9v12.9H45.2z" />
      <path fill="#36C5F0" d="M45.2 32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H12.9C5.8 58.1 0 52.3 0 45.2s5.8-12.9 12.9-12.9h32.3z" />
      <path fill="#2EB67D" d="M97 45.2c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9-5.8 12.9-12.9 12.9H97V45.2z" />
      <path fill="#2EB67D" d="M90.5 45.2c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V12.9C64.7 5.8 70.5 0 77.6 0s12.9 5.8 12.9 12.9v32.3z" />
      <path fill="#ECB22E" d="M77.6 97c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9-12.9-5.8-12.9-12.9V97h12.9z" />
      <path fill="#ECB22E" d="M77.6 90.5c-7.1 0-12.9-5.8-12.9-12.9s5.8-12.9 12.9-12.9h32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H77.6z" />
    </svg>
  )
}

function NotionIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 100 100" aria-hidden="true">
      <path fill="#111827" d="M18 12h52c3 0 5.5 1 7.2 3.2L89 30.5c1.5 2 2.2 4.2 2.2 6.6V82c0 4.4-3.6 8-8 8H33c-2.8 0-5.4-1.2-7.2-3.3L10 70.5C8.4 68.6 7.5 66.2 7.5 63.6V20c0-4.4 3.6-8 10.5-8z" />
      <path fill="#fff" d="M34 28h8.5l18 42h-9l-3.6-9H35.2L31.5 70H23l11-42zm3.2 25H48L42.6 40 37.2 53z" />
    </svg>
  )
}

function GmailIcon() {
  return (
    <svg width="20" height="15" viewBox="0 0 48 36" aria-hidden="true">
      <path fill="#4285F4" d="M0 6v24l12-9V6z" />
      <path fill="#34A853" d="M48 6v24L36 21V6z" />
      <path fill="#FBBC04" d="M0 30l12-9 12 9 12-9 12 9H0z" />
      <path fill="#EA4335" d="M0 6l24 18L48 6H0z" />
      <rect x="1" y="1" width="46" height="34" rx="3" fill="none" stroke="#E8EAED" strokeWidth="2" />
      <path d="M3 5.5 24 21.5 45 5.5" fill="none" stroke="#EA4335" strokeWidth="3" strokeLinejoin="round" />
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
  const [sources, setSources] = useState(INITIAL_SOURCES)

const toggleSourceConnection = (id: string) => {
  setSources((current) =>
    current.map((source) =>
      source.id === id
        ? {
            ...source,
            status: source.status === 'Active' ? 'Disconnected' : 'Active',
            sync: source.status === 'Active' ? 'Not connected' : 'Synced just now',
          }
        : source,
    ),
  )
}

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
         ) : activeSection === 'Connected Sources' ? (
  <>
    <h1 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
      Connected Sources
    </h1>
    <p className="mt-1 text-[14px] text-[#6B7280]">
      Manage the tools Locus reads from to capture your team's decisions.
    </p>

    <section className="mt-8">
      <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        <ul>
          {sources.map((source, i) => (
            <li
              key={source.id}
              className={`flex items-center gap-3 px-4 py-3.5 ${
                i < sources.length - 1 ? 'border-b border-[#F0F0F4]' : ''
              }`}
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#F7F7FA]">
                {source.icon}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-semibold text-[#111827]">
                  {source.name}
                </p>
                <p className="text-[12px] text-[#9CA3AF]">{source.sync}</p>
              </div>
              <div className="mr-3 flex items-center gap-1.5">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    source.status === 'Active' ? 'bg-[#22C55E]' : 'bg-[#EF4444]'
                  }`}
                />
                <span
                  className={`text-[12px] font-medium ${
                    source.status === 'Active' ? 'text-[#16A34A]' : 'text-[#EF4444]'
                  }`}
                >
                  {source.status}
                </span>
              </div>
              <button
                type="button"
                onClick={() => toggleSourceConnection(source.id)}
                className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
                  source.status === 'Active'
                    ? 'border border-[#E5E7EB] bg-white text-[#EF4444] hover:bg-[#FEF2F2]'
                    : 'bg-[#5A45FF] text-white hover:bg-[#4936D9]'
                }`}
              >
                {source.status === 'Active' ? 'Disconnect' : 'Connect'}
              </button>
            </li>
          ))}
        </ul>
        <div className="border-t border-[#F0F0F4] p-3">
          <button
            type="button"
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-[#C7C7D1] py-2.5 text-[13px] font-semibold text-[#5A45FF] transition-colors hover:bg-[#F8F7FF]"
          >
            <span className="text-[16px] leading-none">+</span>
            Add New Source
          </button>
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