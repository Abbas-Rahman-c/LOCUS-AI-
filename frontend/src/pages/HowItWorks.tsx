import { useState } from 'react'
import { LocusLogo } from '../components/LocusLogo'

type StepId = 1 | 2 | 3

const STEPS: { id: StepId; label: string }[] = [
  { id: 1, label: '1. Connect tools' },
  { id: 2, label: '2. Capture what matters' },
  { id: 3, label: '3. Find any decisions' },
]

function CheckIcon() {
  return (
    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#e8f9c8]">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
        <path
          d="M2.5 6.2L4.8 8.5L9.5 3.5"
          stroke="#5a9e1a"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}

function SlackIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5.5 15.1a1.8 1.8 0 1 1-1.8-1.8h1.8v1.8Z" fill="#E01E5A" />
      <path d="M6.4 15.1a1.8 1.8 0 1 1 3.6 0v4.5a1.8 1.8 0 1 1-3.6 0v-4.5Z" fill="#E01E5A" />
      <path d="M8.9 5.5a1.8 1.8 0 1 1 1.8-1.8v1.8H8.9Z" fill="#36C5F0" />
      <path d="M8.9 6.4a1.8 1.8 0 1 1 0 3.6H4.4a1.8 1.8 0 1 1 0-3.6h4.5Z" fill="#36C5F0" />
      <path d="M18.5 8.9a1.8 1.8 0 1 1 1.8 1.8h-1.8V8.9Z" fill="#2EB67D" />
      <path d="M17.6 8.9a1.8 1.8 0 1 1-3.6 0V4.4a1.8 1.8 0 1 1 3.6 0v4.5Z" fill="#2EB67D" />
      <path d="M15.1 18.5a1.8 1.8 0 1 1-1.8 1.8v-1.8h1.8Z" fill="#ECB22E" />
      <path d="M15.1 17.6a1.8 1.8 0 1 1 0-3.6h4.5a1.8 1.8 0 1 1 0 3.6h-4.5Z" fill="#ECB22E" />
    </svg>
  )
}

function NotionIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4.5 3.8h12.2c.4 0 .8.2 1 .5l2.3 3.2c.2.3.3.6.3 1v11.2c0 .7-.6 1.3-1.3 1.3H6.8c-.4 0-.8-.2-1-.5L3.5 17.3c-.2-.3-.3-.6-.3-1V5.1c0-.7.6-1.3 1.3-1.3Z"
        fill="#fff"
        stroke="#111"
        strokeWidth="1.2"
      />
      <path d="M8.2 7.2v9.2M11.5 7.2H15v9.2h-3.5" stroke="#111" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function EmailIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5.5" width="18" height="13" rx="2" stroke="#EA4335" strokeWidth="1.8" />
      <path
        d="M4.2 7.2 12 12.4l7.8-5.2"
        stroke="#EA4335"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Stepper({ active, onChange }: { active: StepId; onChange: (id: StepId) => void }) {
  return (
    <div className="mt-10 flex w-full max-w-[720px] items-center">
      {STEPS.map((step, index) => {
        const isActive = step.id === active
        const isPast = step.id < active
        return (
          <div key={step.id} className="flex flex-1 items-center last:flex-none">
            <button
              type="button"
              onClick={() => onChange(step.id)}
              className={`whitespace-nowrap rounded-full px-4 py-2 text-[13px] font-medium transition-colors ${
                isActive
                  ? 'bg-[#5b52e8] text-white shadow-sm'
                  : 'border border-[#d8d6f5] bg-white text-[#8b85d8] hover:border-[#5b52e8] hover:text-[#5b52e8]'
              }`}
            >
              {step.label}
            </button>
            {index < STEPS.length - 1 && (
              <div
                className={`mx-2 h-px flex-1 ${
                  isPast || isActive ? 'bg-[#5b52e8]' : 'bg-[#e5e7eb]'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

function ConnectToolsPanel() {
  const tools = [
    {
      name: 'Slack',
      detail: 'Threads, channels, DMs',
      icon: <SlackIcon />,
      cardClass: 'border-[#f0e8ff] bg-[#faf7ff]',
    },
    {
      name: 'Notion',
      detail: 'Docs, wikis, databases',
      icon: <NotionIcon />,
      cardClass: 'border-[#ebebeb] bg-[#fafafa]',
    },
    {
      name: 'Email',
      detail: 'Threads & replies',
      icon: <EmailIcon />,
      cardClass: 'border-[#fde8e8] bg-[#fff8f8]',
    },
  ]

  return (
    <div className="mt-12 grid items-start gap-12 lg:grid-cols-2">
      <div>
        <h2 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
          Connect your tools.
        </h2>
        <p className="mt-4 max-w-[420px] text-[15px] leading-[1.7] text-[#6b7280]">
          Authorize Locus to read from the tools your team already lives in. No
          exports, no copy-paste, no new workflows. Locus sits quietly in the
          background and starts listening from day one.
        </p>
        <ul className="mt-6 space-y-3">
          {[
            'One-click OAuth authorization',
            'Read-only access — we never post on your behalf',
            'Works alongside your existing tools with zero friction',
          ].map((item) => (
            <li key={item} className="flex items-start gap-3 text-[14.5px] text-[#374151]">
              <CheckIcon />
              {item}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col items-center">
        <div className="flex items-stretch gap-3">
          {tools.map((tool) => (
            <div
              key={tool.name}
              className={`flex w-[132px] flex-col items-center rounded-[18px] border px-4 py-7 text-center ${tool.cardClass}`}
            >
              <div className="mb-4 flex h-11 w-11 items-center justify-center">
                {tool.icon}
              </div>
              <p className="text-[15px] font-semibold text-[#111827]">{tool.name}</p>
              <p className="mt-1.5 text-[12px] leading-snug text-[#9ca3af]">{tool.detail}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 w-full max-w-[420px]">
          <div className="rounded-full bg-[#eee9ff] px-5 py-2.5 text-center text-[13px] font-medium text-[#5b52e8]">
            + Linear, GitHub, Google Docs coming soon
          </div>
        </div>
      </div>
    </div>
  )
}

function CapturePanel() {
  const feed = [
    {
      name: 'Maya Chen',
      initials: 'MC',
      channel: '#product-decisions',
      time: '2:14 PM',
      message: "We agreed — shipping v2 without the custom fields feature. That's the call.",
      tag: 'Decision',
      tagClass: 'bg-[#eee8ff] text-[#5b52e8]',
      avatarClass: 'bg-[#ddd6fe] text-[#5b52e8]',
    },
    {
      name: 'James Okafor',
      initials: 'JO',
      channel: '#eng-backend',
      time: '3:41 PM',
      message: 'Auth service will use JWT tokens. Refresh window is 24h. Non-negotiable for compliance.',
      tag: 'Decision',
      tagClass: 'bg-[#eee8ff] text-[#5b52e8]',
      avatarClass: 'bg-[#c7d2fe] text-[#4338ca]',
    },
    {
      name: 'Sara Li',
      initials: 'SL',
      channel: '#design-review',
      time: 'Yesterday',
      message: "Blocking: we can't finalize the onboarding flow until copy is signed off by legal.",
      tag: 'Blocker',
      tagClass: 'bg-[#fee2e2] text-[#dc2626]',
      avatarClass: 'bg-[#fecdd3] text-[#be123c]',
    },
  ]

  const highlights = [
    { label: 'Decisions', detail: 'Final calls and agreements extracted automatically', className: 'bg-[#eee8ff] text-[#5b52e8]' },
    { label: 'Action items', detail: 'Tasks assigned or implied in conversations', className: 'bg-[#ecfccb] text-[#65a30d]' },
    { label: 'Blockers', detail: 'Flagged dependencies and open risks', className: 'bg-[#fee2e2] text-[#dc2626]' },
  ]

  return (
    <div className="mt-12 grid items-start gap-12 lg:grid-cols-2">
      <div className="overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white shadow-[0_12px_40px_rgba(17,24,39,0.08)]">
        <div className="flex items-center justify-between border-b border-[#f3f4f6] px-4 py-3">
          <LocusLogo />
          <span className="flex items-center gap-1.5 text-[12px] font-medium text-[#16a34a]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#16a34a]" />
            Live
          </span>
        </div>
        <div className="divide-y divide-[#f3f4f6]">
          {feed.map((item) => (
            <div key={item.name} className="px-4 py-3.5">
              <div className="flex items-start gap-3">
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${item.avatarClass}`}
                >
                  {item.initials}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12px]">
                    <span className="font-semibold text-[#111827]">{item.name}</span>
                    <span className="text-[#9ca3af]">{item.channel}</span>
                    <span className="text-[#d1d5db]">·</span>
                    <span className="text-[#9ca3af]">{item.time}</span>
                  </div>
                  <p className="mt-1 text-[13px] leading-snug text-[#374151]">{item.message}</p>
                  <span className={`mt-2 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${item.tagClass}`}>
                    {item.tag}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between bg-[#f8f7ff] px-4 py-2.5 text-[12px]">
          <span className="text-[#6b7280]">3 items captured today</span>
          <button type="button" className="font-medium text-[#5b52e8]">
            View decision log →
          </button>
        </div>
      </div>

      <div>
        <h2 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
          Locus captures <span className="text-[#5b52e8]">what matters.</span>
        </h2>
        <p className="mt-4 max-w-[420px] text-[15px] leading-[1.7] text-[#6b7280]">
          As your team communicates normally, Locus reads the signal. It
          identifies decisions, action items, and blockers using context-aware
          AI — and logs each one with a source link, owner, and timestamp.
        </p>
        <div className="mt-6 space-y-3">
          {highlights.map((item) => (
            <div
              key={item.label}
              className="flex items-center gap-3 rounded-xl border border-[#e5e7eb] px-3.5 py-3"
            >
              <span className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${item.className}`}>
                {item.label}
              </span>
              <span className="text-[13px] text-[#6b7280]">{item.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function FindDecisionsPanel() {
  const results = [
    {
      title: 'Ship v2 without custom fields',
      meta: 'Jun 12 · Maya C. · #product-decisions',
      tag: 'Product',
      tagClass: 'bg-[#ede9fe] text-[#5b52e8]',
    },
    {
      title: 'Auth tokens: JWT, 24h refresh window',
      meta: 'Jun 11 · James O. · #eng-backend',
      tag: 'Engineering',
      tagClass: 'bg-[#ffedd5] text-[#c2410c]',
    },
    {
      title: 'Onboarding copy blocked on legal review',
      meta: 'Jun 10 · Sara L. · #design-review',
      tag: 'Design',
      tagClass: 'bg-[#fce7f3] text-[#be185d]',
    },
    {
      title: 'Q3 pricing: keep freemium, raise Pro to $49',
      meta: 'Jun 8 · Priya N. · #growth',
      tag: 'Business',
      tagClass: 'bg-[#dbeafe] text-[#1d4ed8]',
    },
  ]

  const filters = ['All', 'Product', 'Engineering', 'Design', 'Business']

  return (
    <div className="mt-12 grid items-start gap-12 lg:grid-cols-2">
      <div>
        <h2 className="text-[28px] font-bold tracking-[-0.02em] text-[#111827]">
          Find any decision <span className="text-[#5b52e8]">in seconds.</span>
        </h2>
        <p className="mt-4 max-w-[420px] text-[15px] leading-[1.7] text-[#6b7280]">
          Search across your full decision history with natural-language
          queries. Filter by owner, date, team, or tag. Every result links back
          to the original Slack thread or Notion page so you always have full
          context.
        </p>
        <ul className="mt-6 space-y-3">
          {[
            'Full-text semantic search across all decisions',
            'Filter by team, owner, date range, or tag',
            'One-click jump to the original source',
            'Export to CSV or Notion with a single click',
          ].map((item) => (
            <li key={item} className="flex items-start gap-3 text-[14.5px] text-[#374151]">
              <CheckIcon />
              {item}
            </li>
          ))}
        </ul>
      </div>

      <div className="overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white shadow-[0_12px_40px_rgba(17,24,39,0.08)]">
        <div className="border-b border-[#f3f4f6] p-4">
          <div className="flex items-center gap-2 rounded-xl border border-[#e5e7eb] bg-[#fafafa] px-3 py-2.5">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <circle cx="7" cy="7" r="4.5" stroke="#9ca3af" strokeWidth="1.5" />
              <path d="M10.5 10.5L13.5 13.5" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span className="text-[14px] text-[#111827]">auth token</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {filters.map((filter, index) => (
              <span
                key={filter}
                className={`rounded-full px-3 py-1 text-[12px] font-medium ${
                  index === 0
                    ? 'bg-[#5b52e8] text-white'
                    : 'border border-[#e5e7eb] bg-white text-[#6b7280]'
                }`}
              >
                {filter}
              </span>
            ))}
          </div>
        </div>
        <div className="divide-y divide-[#f3f4f6]">
          {results.map((result) => (
            <div key={result.title} className="flex items-start justify-between gap-3 px-4 py-3.5">
              <div className="min-w-0">
                <p className="text-[14px] font-semibold text-[#111827]">{result.title}</p>
                <p className="mt-1 text-[12px] text-[#9ca3af]">{result.meta}</p>
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${result.tagClass}`}>
                {result.tag}
              </span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between bg-[#f8f7ff] px-4 py-2.5 text-[12px]">
          <span className="text-[#6b7280]">Showing 4 of 284 decisions</span>
          <button type="button" className="font-medium text-[#5b52e8]">
            View all →
          </button>
        </div>
      </div>
    </div>
  )
}

export default function HowItWorks() {
  const [activeStep, setActiveStep] = useState<StepId>(1)

  return (
    <div className="bg-white px-6 py-16 sm:px-10 lg:px-16 lg:py-20">
      <div className="mx-auto max-w-[980px]">
        <p className="text-[12px] font-semibold tracking-[0.08em] text-[#5b52e8]">
          — HOW IT WORKS
        </p>
        <h1 className="mt-3 max-w-[720px] text-[36px] font-bold leading-[1.15] tracking-[-0.03em] text-[#111827] sm:text-[42px]">
          See how Locus turns your team&apos;s activity into{' '}
          <span className="text-[#5b52e8]">shared memory.</span>
        </h1>
        <p className="mt-4 max-w-[640px] text-[15px] leading-[1.7] text-[#6b7280]">
          Locus connects to Slack, Notion, and your other tools — automatically
          extracting decisions, surfacing patterns, and giving your whole team a
          searchable record of everything that was ever agreed upon.
        </p>

        <Stepper active={activeStep} onChange={setActiveStep} />

        {activeStep === 1 && <ConnectToolsPanel />}
        {activeStep === 2 && <CapturePanel />}
        {activeStep === 3 && <FindDecisionsPanel />}
      </div>
    </div>
  )
}
