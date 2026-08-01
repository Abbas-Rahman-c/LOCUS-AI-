import { SourceLogo, type SourceName } from './SourceLogo'

const SOURCES = [
  {
    name: 'Slack',
    sync: 'Synced today 9:00 am',
    status: 'Active' as const,
    source: 'Slack' as SourceName,
  },
  {
    name: 'Notion',
    sync: 'Synced today 9:00 am',
    status: 'Active' as const,
    source: 'Notion' as SourceName,
  },
  {
    name: 'Gmail',
    sync: 'Synced today 9:00 am',
    status: 'Disconnected' as const,
    source: 'Gmail' as SourceName,
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
                <SourceLogo source={source.source} className="h-6 w-6" />
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
