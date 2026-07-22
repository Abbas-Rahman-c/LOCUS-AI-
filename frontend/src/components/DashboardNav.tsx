const NAV_LINKS = [
  { label: 'How it works', href: '/how-it-works' },
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Decision Log', href: '/decision-log' },
  { label: 'Team Pulse', href: '/team-pulse', badge: true },
  { label: 'Settings', href: '/settings' },
] as const

export function DashboardNav() {
  const pathname = window.location.pathname

  return (
    <header className="relative sticky top-0 z-20 border-b border-[#E8E8ED] bg-white">
      <div className="relative mx-auto flex min-h-[56px] w-full flex-wrap items-center justify-between px-4 py-3 md:h-[56px] md:flex-nowrap md:px-16 md:py-0">
        <a href="/dashboard" className="flex items-center gap-2.5" aria-label="Locus AI dashboard">
          <img
            src="/locus-mark.png"
            alt=""
            className="h-7 w-7 shrink-0"
          />
          <span className="whitespace-nowrap text-[16px] font-bold text-[#111117]">
            LOCUS <span className="text-[#4B3FD1]">AI</span>
          </span>
        </a>

        <nav className="order-3 mt-2 flex h-10 w-full items-center gap-5 overflow-x-auto md:absolute md:left-1/2 md:top-0 md:order-none md:mt-0 md:h-full md:w-auto md:-translate-x-1/2 md:gap-4 md:overflow-visible lg:gap-8">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className={`relative flex h-full shrink-0 items-center whitespace-nowrap text-[13px] font-medium transition-colors md:text-[12px] lg:text-[13px] ${
                pathname === link.href
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
              {pathname === link.href ? (
                <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[#5A45FF]" />
              ) : null}
            </a>
          ))}
        </nav>

        <button
          type="button"
          aria-label="User profile"
          className="flex h-7 w-7 items-center justify-center rounded-full border border-[#B8BFCC] bg-white"
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
