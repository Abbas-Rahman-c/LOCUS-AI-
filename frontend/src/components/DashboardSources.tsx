function SlackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 122.8 122.8" aria-hidden="true">
      <path
        fill="#E01E5A"
        d="M25.8 77.6c0 7.1-5.8 12.9-12.9 12.9S0 84.7 0 77.6s5.8-12.9 12.9-12.9h12.9v12.9z"
      />
      <path
        fill="#E01E5A"
        d="M32.3 77.6c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9v32.3c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V77.6z"
      />
      <path
        fill="#36C5F0"
        d="M45.2 25.8c-7.1 0-12.9-5.8-12.9-12.9S38.1 0 45.2 0s12.9 5.8 12.9 12.9v12.9H45.2z"
      />
      <path
        fill="#36C5F0"
        d="M45.2 32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H12.9C5.8 58.1 0 52.3 0 45.2s5.8-12.9 12.9-12.9h32.3z"
      />
      <path
        fill="#2EB67D"
        d="M97 45.2c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9-5.8 12.9-12.9 12.9H97V45.2z"
      />
      <path
        fill="#2EB67D"
        d="M90.5 45.2c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V12.9C64.7 5.8 70.5 0 77.6 0s12.9 5.8 12.9 12.9v32.3z"
      />
      <path
        fill="#ECB22E"
        d="M77.6 97c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9-12.9-5.8-12.9-12.9V97h12.9z"
      />
      <path
        fill="#ECB22E"
        d="M77.6 90.5c-7.1 0-12.9-5.8-12.9-12.9s5.8-12.9 12.9-12.9h32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H77.6z"
      />
    </svg>
  )
}

function NotionIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 100 100" aria-hidden="true">
      <path
        fill="#111827"
        d="M18 12h52c3 0 5.5 1 7.2 3.2L89 30.5c1.5 2 2.2 4.2 2.2 6.6V82c0 4.4-3.6 8-8 8H33c-2.8 0-5.4-1.2-7.2-3.3L10 70.5C8.4 68.6 7.5 66.2 7.5 63.6V20c0-4.4 3.6-8 10.5-8z"
      />
      <path
        fill="#fff"
        d="M34 28h8.5l18 42h-9l-3.6-9H35.2L31.5 70H23l11-42zm3.2 25H48L42.6 40 37.2 53z"
      />
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
      <path fill="#C5221F" d="M12 21V6h24v15L24 30 12 21z" opacity=".15" />
      <path
        fill="#EA4335"
        d="M4 4h40c1.1 0 2 .9 2 2v24c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"
        opacity="0"
      />
      <rect
        x="1"
        y="1"
        width="46"
        height="34"
        rx="3"
        fill="none"
        stroke="#E8EAED"
        strokeWidth="2"
      />
      <path
        d="M3 5.5 24 21.5 45 5.5"
        fill="none"
        stroke="#EA4335"
        strokeWidth="3"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const SOURCES = [
  {
    name: 'Slack',
    sync: 'Synced today 9:00 am',
    status: 'Active' as const,
    icon: <SlackIcon />,
  },
  {
    name: 'Notion',
    sync: 'Synced today 9:00 am',
    status: 'Active' as const,
    icon: <NotionIcon />,
  },
  {
    name: 'Gmail',
    sync: 'Synced today 9:00 am',
    status: 'Disconnected' as const,
    icon: <GmailIcon />,
  },
]

export function DashboardSources() {
  return (
    <section>
      <h2 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
        Memory Sources
      </h2>
      <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        <ul>
          {SOURCES.map((source, i) => (
            <li
              key={source.name}
              className={`flex items-center gap-3 px-4 py-3.5 ${
                i < SOURCES.length - 1 ? 'border-b border-[#F0F0F4]' : ''
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
              <div className="flex items-center gap-1.5">
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
            </li>
          ))}
        </ul>
        <div className="border-t border-[#F0F0F4] p-3">
          <button
            type="button"
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-[#C7C7D1] py-2.5 text-[13px] font-semibold text-[#5A45FF] transition-colors hover:bg-[#F8F7FF]"
          >
            <span className="text-[16px] leading-none">+</span>
            Add Memory Source
          </button>
        </div>
      </div>
    </section>
  )
}
