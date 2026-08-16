import { LocusLogo } from './LocusLogo'
import { useNavigate } from 'react-router-dom'

function BookIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 6.5c-1.4-1.4-3.4-2.2-5.5-2.2H3.5v14.2h3.2c2.1 0 4 0.8 5.3 2.2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 6.5c1.4-1.4 3.4-2.2 5.5-2.2h3v14.2h-3.2c-2.1 0-4 0.8-5.3 2.2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12 6.5v14.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

export function Header() {
  const navigate = useNavigate()

  return (
    <header className="flex items-center justify-between px-8 pt-6 pb-2 lg:px-10">
      <LocusLogo />

      <div className="flex items-center gap-8">
        <nav className="hidden items-center gap-8 sm:flex">
          <a
            href="#how-it-works"
            className="text-[14px] font-medium text-[#6b7280] transition-colors hover:text-[#111827]"
          >
            How it works
          </a>
          <a
            href="#why-locus"
            className="text-[14px] font-medium text-[#6b7280] transition-colors hover:text-[#111827]"
          >
            Why Locus AI
          </a>
          <a
            href="/userguide.html"
            className="inline-flex items-center gap-1.5 text-[14px] font-medium text-[#6b7280] transition-colors hover:text-[#111827]"
          >
            <BookIcon />
            User Guide
          </a>
        </nav>

        <button
          type="button"
          onClick={() => navigate('/welcome')}
          className="rounded-full border border-[#d1d5db] bg-white px-5 py-1.5 text-[14px] font-medium text-[#374151] transition-colors hover:bg-gray-50"
        >
          Log in
        </button>
      </div>
    </header>
  )
}
