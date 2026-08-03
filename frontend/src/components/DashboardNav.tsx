import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { getSupabaseClient, isSupabaseConfigured } from '../lib/supabase'
import { DEMO_EMAIL_KEY, WORKSPACES_DONE_KEY } from '../lib/sessionKeys'

const NAV_LINKS = [
  { label: 'How it works', to: '/how-it-works' },
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Memory Explorer', to: '/decision-log' },
  { label: 'Team Pulse', to: '/team-pulse', badge: true },
  { label: 'Settings', to: '/settings' },
] as const

type ProfileUser = {
  name: string
  email: string
  initials: string
}

function clearLocalSession() {
  sessionStorage.removeItem(DEMO_EMAIL_KEY)
  sessionStorage.removeItem(WORKSPACES_DONE_KEY)
  sessionStorage.removeItem('locus:connected-tools')
}

function getInitials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function getNameFromEmail(email: string) {
  const emailName = email.split('@')[0]?.replace(/[._-]+/g, ' ').trim()
  if (!emailName) return 'Locus User'

  return emailName.replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function DashboardNav() {
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [profile, setProfile] = useState<ProfileUser>({
    name: 'Locus User',
    email: '',
    initials: 'LU',
  })
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const demoEmail = sessionStorage.getItem(DEMO_EMAIL_KEY)
    if (demoEmail) {
      setProfile({
        name: 'Locus User',
        email: demoEmail,
        initials: 'LU',
      })
      return
    }

    if (!isSupabaseConfigured()) return

    const supabase = getSupabaseClient()
    void supabase.auth.getSession().then(({ data }) => {
      const user = data.session?.user
      if (!user) return
      const email = user.email ?? ''
      const name =
        String(
          user.user_metadata.full_name ||
            user.user_metadata.name ||
            user.user_metadata.display_name ||
            getNameFromEmail(email),
        )
      setProfile({ name, email, initials: getInitials(name) || 'LU' })
    })
  }, [])

  useEffect(() => {
    if (!menuOpen) return

    const onPointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  const logOut = async () => {
    clearLocalSession()
    if (isSupabaseConfigured()) {
      await getSupabaseClient().auth.signOut()
    }
    setMenuOpen(false)
    navigate('/', { replace: true })
  }

  return (
    <header className="relative sticky top-0 z-20 border-b border-[#E8E8ED] bg-white">
      <div className="relative mx-auto flex min-h-[56px] w-full flex-wrap items-center justify-between px-4 py-3 md:h-[56px] md:flex-nowrap md:px-16 md:py-0">
        <NavLink
          to="/dashboard"
          className="flex items-center gap-2.5"
          aria-label="Locus AI dashboard"
        >
          <img src="/locus-mark.png" alt="" className="h-7 w-7 shrink-0 rounded-[5px]" />
          <span className="whitespace-nowrap text-[16px] font-bold text-[#111117]">
            LOCUS <span className="text-[#5b52e8]">AI</span>
          </span>
        </NavLink>

        <nav className="order-3 mt-2 flex h-10 w-full items-center gap-5 overflow-x-auto md:absolute md:left-1/2 md:top-0 md:order-none md:mt-0 md:h-full md:w-auto md:-translate-x-1/2 md:gap-4 md:overflow-visible lg:gap-8">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.label}
              to={link.to}
              className={({ isActive }) =>
                `relative flex h-full shrink-0 items-center whitespace-nowrap text-[13px] font-medium transition-colors md:text-[12px] lg:text-[13px] ${
                  isActive
                    ? 'text-[#5A45FF]'
                    : 'text-[#6B7280] hover:text-[#111827]'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className="relative">
                    {link.label}
                    {'badge' in link && link.badge ? (
                      <span className="absolute -right-2.5 top-0 h-[6px] w-[6px] rounded-full bg-[#5A45FF]" />
                    ) : null}
                  </span>
                  {isActive ? (
                    <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[#5A45FF]" />
                  ) : null}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="relative" ref={menuRef}>
          <button
            type="button"
            aria-label="User profile"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
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

          {menuOpen ? (
            <div
              role="menu"
              className="absolute right-0 z-50 mt-3 w-[280px] overflow-hidden rounded-[20px] border border-[#E8E8ED] bg-white shadow-[0_18px_50px_rgba(17,24,39,0.18)]"
            >
              <div className="flex flex-col items-center px-5 pt-6 pb-5">
                <div className="flex h-16 w-16 items-center justify-center rounded-full border border-[#E5E7EB] bg-[#F3F4F6]">
                  <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle cx="12" cy="8" r="3.5" fill="#9CA3AF" />
                    <path
                      d="M5 19.5c0-3.6 3.1-6 7-6s7 2.4 7 6"
                      stroke="#9CA3AF"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
                <p className="mt-3 text-[16px] font-bold text-[#111827]">{profile.name}</p>
                {profile.email ? (
                  <p className="mt-0.5 text-[13px] text-[#6B7280]">{profile.email}</p>
                ) : null}
              </div>

              <div className="border-t border-[#E8E8ED] p-4">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => void logOut()}
                  className="h-11 w-full rounded-xl bg-[#4338CA] text-[15px] font-semibold text-white transition-colors hover:bg-[#3730A3]"
                >
                  Log Out
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  )
}
