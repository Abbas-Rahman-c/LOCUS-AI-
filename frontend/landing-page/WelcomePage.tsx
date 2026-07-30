import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAuthCallbackUrl } from '../src/lib/appUrl'
import { DEMO_EMAIL_KEY, WORKSPACES_DONE_KEY } from '../src/lib/sessionKeys'
import { getSupabaseClient, isSupabaseConfigured } from '../src/lib/supabase'
import { GoogleIcon } from './components/GoogleIcon'
import { LocusLogo } from './components/LocusLogo'

const BENEFITS = [
  'Ask anything your organization already knows.',
  'Learn continuously from everyday work.',
  'A weekly digest of everything that mattered.',
]

export default function WelcomePage() {
  const navigate = useNavigate()
  const [isSigningIn, setIsSigningIn] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    if (sessionStorage.getItem(DEMO_EMAIL_KEY)) {
      navigate('/connect-workspaces', { replace: true })
      return
    }

    if (!isSupabaseConfigured()) return

    void getSupabaseClient()
      .auth.getSession()
      .then(({ data }) => {
        if (data.session?.user.email) {
          navigate('/connect-workspaces', { replace: true })
        }
      })
  }, [navigate])

  const handleContinueWithGoogle = async () => {
    setAuthError(null)
    setIsSigningIn(true)

    if (!isSupabaseConfigured()) {
      setIsSigningIn(false)
      setAuthError(
        'Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to frontend/.env to enable Google sign-in.',
      )
      return
    }

    try {
      // Same-window redirect so Google always returns to the Vercel app,
      // then OAuthCallback sends the user to Connect Workspaces.
      const { data, error } = await getSupabaseClient().auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: getAuthCallbackUrl(),
          skipBrowserRedirect: false,
          queryParams: { prompt: 'select_account' },
        },
      })

      if (error) throw error
      if (!data.url) throw new Error('Google sign in could not be started.')
      // Browser navigates away via Supabase redirect.
    } catch (error) {
      setIsSigningIn(false)
      setAuthError(
        error instanceof Error ? error.message : 'Unable to start Google sign in.',
      )
    }
  }

  return (
    <div className="flex min-h-screen w-full flex-col md:flex-row">
      <section className="flex w-full flex-col justify-center bg-[#111827] px-10 py-16 md:w-1/2 md:px-16 lg:px-20">
        <h1 className="max-w-[520px] text-[40px] font-extrabold leading-[1.15] tracking-[-0.03em] text-white sm:text-[48px]">
          Run your projects like you{' '}
          <span className="text-[#C8E619]">remember everything.</span>
        </h1>

        <ul className="mt-10 space-y-4">
          {BENEFITS.map((item) => (
            <li key={item} className="flex items-start gap-3 text-[16px] text-white/90">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#5b52e8] text-[12px] font-bold text-white">
                ✓
              </span>
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex w-full flex-col items-center justify-center bg-white px-8 py-16 md:w-1/2">
        <LocusLogo size={36} />

        <div className="mt-16 w-full max-w-sm text-center">
          <h2 className="text-[32px] font-bold tracking-[-0.02em] text-[#111827]">
            Welcome to Locus
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-[#6b7280]">
            Connect your tools and turn everyday work into organizational memory.
          </p>

          <button
            type="button"
            onClick={handleContinueWithGoogle}
            disabled={isSigningIn}
            className="mt-10 flex w-full items-center justify-center gap-3 rounded-full bg-[#C8E619] px-6 py-3.5 text-[15px] font-semibold text-[#111827] transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-70"
          >
            <GoogleIcon />
            {isSigningIn ? 'Redirecting…' : 'Continue with Google'}
          </button>

          <button
            type="button"
            onClick={() => {
              sessionStorage.setItem(DEMO_EMAIL_KEY, 'youremail@gmail.com')
              sessionStorage.removeItem(WORKSPACES_DONE_KEY)
              navigate('/connect-workspaces', { replace: true })
            }}
            className="mt-3 w-full rounded-full border border-[#d1d5db] bg-white px-6 py-3 text-[14px] font-semibold text-[#111827] transition-colors hover:bg-[#f9fafb]"
          >
            Continue to Connect Workspaces (demo)
          </button>

          {authError && (
            <p role="alert" className="mt-3 text-[13px] text-red-600">
              {authError}
            </p>
          )}

          <p className="mt-4 text-[12px] leading-relaxed text-[#9ca3af]">
            By clicking continue, you agree to our terms of service and privacy policy.
          </p>
        </div>
      </section>
    </div>
  )
}
