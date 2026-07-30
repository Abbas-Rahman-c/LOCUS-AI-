const SUGGESTIONS = [
  'What does our org already know about the Q3 timeline?',
  'What context do we have on the onboarding flow?',
]

const RECENT_SEARCHES = [
  { query: 'What do we know about the onboarding flow?', time: '2h ago' },
  { query: 'Who owns the legal sign-off blocker?', time: '1d ago' },
  { query: 'What context exists around pricing changes?', time: '1d ago' },
]

export function DashboardSearch() {
  return (
    <section className="mb-8">
      <h1 className="mb-5 text-[32px] font-bold leading-tight tracking-[-0.02em] text-[#111827]">
        Good morning, Jun
      </h1>

      <div className="relative mb-3.5">
        <div className="flex h-[52px] items-center rounded-xl border border-[#E5E7EB] bg-white px-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
          <svg
            className="mr-3 shrink-0 text-[#9CA3AF]"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path
              d="M20 20l-3.5-3.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <input
            type="text"
            placeholder="Ask anything your organization already knows."
            className="h-full w-full bg-transparent text-[15px] text-[#111827] outline-none placeholder:text-[#9CA3AF]"
          />
          <button
            type="button"
            className="ml-3 shrink-0 rounded-lg bg-[#5A45FF] px-5 py-2 text-[14px] font-semibold text-white transition-opacity hover:opacity-90"
          >
            Ask
          </button>
        </div>
      </div>

      <div className="mb-7 flex flex-wrap gap-2.5">
        {SUGGESTIONS.map((text, i) => (
          <button
            key={`${text}-${i}`}
            type="button"
            className="rounded-full border border-[#E5E7EB] bg-white px-4 py-2 text-[13px] font-medium text-[#374151] transition-colors hover:bg-[#F9FAFB]"
          >
            {text}
          </button>
        ))}
      </div>

      <div>
        <h2 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
          Recent Search
        </h2>
        <ul className="overflow-hidden rounded-xl border border-[#E8E8ED] bg-white">
          {RECENT_SEARCHES.map((item, i) => (
            <li
              key={`${item.query}-${i}`}
              className={`flex items-center justify-between px-4 py-3.5 ${
                i < RECENT_SEARCHES.length - 1 ? 'border-b border-[#F0F0F4]' : ''
              }`}
            >
              <span className="text-[14px] text-[#374151]">{item.query}</span>
              <span className="ml-4 shrink-0 text-[13px] text-[#9CA3AF]">
                {item.time}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
