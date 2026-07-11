import { useEffect, useState } from 'react'
import { getSupabaseClient } from '../src/lib/supabase'
import { Header } from './components/Header'
import { GoogleIcon } from './components/GoogleIcon'
import { ProcessStepper } from './components/ProcessStepper'
import { DashboardPreview } from './components/DashboardPreview'

export default function GetStarted() {
  const [isSigningIn, setIsSigningIn] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    const handleAuthMessage = (event: MessageEvent) => {
      if (
        event.origin !== window.location.origin ||
        event.data?.type !== 'locus:google-auth'
      ) return

      setIsSigningIn(false)
      setAuthError(event.data.success ? null : event.data.error)
    }

    window.addEventListener('message', handleAuthMessage)
    return () => window.removeEventListener('message', handleAuthMessage)
  }, [])

  const handleGoogleSignUp = async () => {
    setAuthError(null)
    setIsSigningIn(true)

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
          redirectTo: `${window.location.origin}/?auth_callback=1`,
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
    <div className="relative w-full bg-white">
      <div className="mx-auto min-h-screen w-full max-w-[1100px]">
        <Header />

        <main className="flex min-h-[calc(100vh-72px)] flex-col gap-10 px-8 pb-10 pt-2 lg:flex-row lg:items-stretch lg:gap-8 lg:px-10">
          <section className="flex w-full shrink-0 flex-col pt-4 lg:w-[42%]">
            <h1 className="text-[40px] font-bold leading-[1.15] tracking-[-0.025em] text-[#111827]">
              Never lose a{' '}
              <span className="bg-gradient-to-r from-[#5b52e8] to-[#6366f1] bg-clip-text text-transparent">
                team decision
              </span>{' '}
              again.
            </h1>

            <p className="mt-4 max-w-[390px] text-[14.5px] leading-[1.65] text-[#6b7280]">
              Locus automatically captures decisions from your Slack and Notion
              workspaces so you can find them in seconds—with links back to the
              original messages.
            </p>

            <button
              type="button"
              onClick={handleGoogleSignUp}
              disabled={isSigningIn}
              className="mt-6 flex w-fit items-center gap-2.5 rounded-full bg-[#c8e619] px-5 py-3 text-[14.5px] font-semibold text-[#111827] transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-70"
            >
              <GoogleIcon />
              {isSigningIn ? 'Opening Google...' : 'Sign up with Google'}
            </button>

            {authError && (
              <p role="alert" className="mt-2 max-w-[370px] text-[12.5px] text-red-600">
                {authError}
              </p>
            )}

            <p className="mt-2.5 max-w-[370px] text-[12.5px] leading-[1.55] text-[#9ca3af]">
              We&apos;ll connect Slack and Notion next so Locus can start
              capturing decisions.
            </p>

            <ProcessStepper />
          </section>

          <DashboardPreview />
        </main>
      </div>
    </div>
  )
}
