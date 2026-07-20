type CaptureType = 'Decision' | 'Blocker' | 'Action Item'

const TAG_STYLES: Record<CaptureType, string> = {
  Decision: 'bg-[#EEEBFF] text-[#5A45FF]',
  Blocker: 'bg-[#FEE2E2] text-[#DC2626]',
  'Action Item': 'bg-[#ECFCCB] text-[#4D7C0F]',
}

const CAPTURES: { type: CaptureType; title: string; meta: string }[] = [
  {
    type: 'Decision',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  },
  {
    type: 'Blocker',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  },
  {
    type: 'Action Item',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  },
  {
    type: 'Decision',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  },
  {
    type: 'Decision',
    title: 'Adopt PostgreSQL for the context layer',
    meta: 'Slack · 3h ago',
  },
]

export function DashboardCaptures() {
  return (
    <section>
      <h2 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
        Recent Captures
      </h2>
      <div className="overflow-hidden rounded-2xl border border-[#E8E8ED] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        <ul>
          {CAPTURES.map((capture, i) => (
            <li
              key={`${capture.type}-${i}`}
              className={`flex items-center gap-3 px-4 py-3.5 ${
                i < CAPTURES.length - 1 ? 'border-b border-[#F0F0F4]' : ''
              }`}
            >
              <span
                className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${TAG_STYLES[capture.type]}`}
              >
                {capture.type}
              </span>
              <p className="min-w-0 flex-1 truncate text-[14px] text-[#111827]">
                {capture.title}
              </p>
              <span className="shrink-0 text-[12px] text-[#9CA3AF]">
                {capture.meta}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
