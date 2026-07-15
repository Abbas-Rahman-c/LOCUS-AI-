import { LocusLogo } from './LocusLogo'

const NAV_LINKS = [
  { label: 'How it works', href: '#how-it-works', active: false },
  { label: 'Dashboard', href: '#dashboard', active: true },
  { label: 'Decision Log', href: '#decision-log', active: false },
  { label: 'Team Pulse', href: '#team-pulse', active: false, badge: true },
  { label: 'Settings', href: '#settings', active: false },
] as const

export function DashboardNav() {
  return (
    <header className="relative sticky top-0 z-20 border-b border-[#E8E8ED] bg-white">
      <div className="relative mx-auto flex h-[64px] max-w-[1120px] items-center justify-between px-8">
        <LocusLogo />

        <nav className="absolute left-1/2 top-0 flex h-full -translate-x-1/2 items-center gap-8">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className={`relative flex h-full items-center text-[14px] font-medium transition-colors ${
                link.active
                  ? 'text-[#5A45FF]'
                  : 'text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              <span className="relative">
                {link.label}
                {'badge' in link && link.badge ? (
                  <span className="absolute -right-2.5 top-0 h-[6px] w-[6px] rounded-full bg-[#5A45FF]" />
                ) : null}
              </span>
              {link.active ? (
                <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[#5A45FF]" />
              ) : null}
            </a>
          ))}
        </nav>

        <button
          type="button"
          aria-label="User profile"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-[#EFEFF3]"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="12" cy="8" r="3.5" fill="#9CA3AF" />
            <path
              d="M5 19.5c0-3.6 3.1-6 7-6s7 2.4 7 6"
              stroke="#9CA3AF"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
    </header>
  )
}
