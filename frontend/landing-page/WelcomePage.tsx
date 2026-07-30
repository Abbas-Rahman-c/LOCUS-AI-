import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAuthCallbackUrl, getAppOrigin } from '../src/lib/appUrl'
import { getSupabaseClient, isSupabaseConfigured } from '../src/lib/supabase'
import { GoogleIcon } from './components/GoogleIcon'
import { LocusLogo } from './components/LocusLogo'

const BENEFITS = [
  'Ask anything about your project history.',
  'Automatically captures memory.',
  'A weekly digest of everything that mattered.',
]

export default function WelcomePage() {
  const navigate = useNavigate()
  const [isSigningIn, setIsSigningIn] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    if (!isSupabaseConfigured()) return

    void getSupabaseClient()
      .auth.getSession()
      .then(({ data }) => {
        if (data.session?.user.email) {
          navigate('/connect-workspaces', { replace: true })
        }
      })
  }, [navigate])

  useEffect(() => {
    const handleAuthMessage = async (event: MessageEvent) => {
      const allowedOrigins = new Set([window.location.origin, getAppOrigin()])
      if (
        !allowedOrigins.has(event.origin) ||
        event.data?.type !== 'locus:google-auth'
      ) {
        return
      }

      if (!event.data.success) {
        setIsSigningIn(false)
        setAuthError(event.data.error ?? 'Unable to complete Google sign in.')
        return
      }

      try {
        if (event.data.access_token && event.data.refresh_token) {
          const { error } = await getSupabaseClient().auth.setSession({
            access_token: event.data.access_token,
            refresh_token: event.data.refresh_token,
          })
          if (error) throw error
        }
        navigate('/connect-workspaces', { replace: true })
      } catch (error) {
        setIsSigningIn(false)
        setAuthError(
          error instanceof Error ? error.message : 'Unable to complete Google sign in.',
        )
      }
    }

    window.addEventListener('message', handleAuthMessage)
    return () => window.removeEventListener('message', handleAuthMessage)
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

    const popup = window.open(
      'about:blank',
      'locus-google-oauth',
      'popup=yes,width=520,height=680,top=100,left=100',
    )

    if (!popup) {
      setIsSigningIn(false)
      setAuthError('Please allow popups for this site and try again.')
      return
    }

    try {
      const { data, error } = await getSupabaseClient().auth.signInWithOAuth({
        provider: 'google',
        options: {
          // Always return to the Vercel app — locusaiapp.com still serves GoDaddy.
          redirectTo: getAuthCallbackUrl(),
          skipBrowserRedirect: true,
          queryParams: { prompt: 'select_account' },
        },
      })

      if (error || !data.url) {
        throw error ?? new Error('Google sign in could not be started.')
      }

      popup.location.href = data.url
    } catch (error) {
      popup.close()
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
            Connect your tools and never lose a decision again.
          </p>

          <button
            type="button"
            onClick={handleContinueWithGoogle}
            disabled={isSigningIn}
            className="mt-10 flex w-full items-center justify-center gap-3 rounded-full bg-[#C8E619] px-6 py-3.5 text-[15px] font-semibold text-[#111827] transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-70"
          >
            <GoogleIcon />
            {isSigningIn ? 'Opening…' : 'Continue with Google'}
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
