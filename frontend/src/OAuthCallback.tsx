import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAppOrigin } from './lib/appUrl'
import { getSupabaseClient } from './lib/supabase'

const AUTH_MESSAGE_TYPE = 'locus:google-auth'

export default function OAuthCallback() {
  const navigate = useNavigate()
  const [message, setMessage] = useState('Completing your Google sign in...')
  const hasStarted = useRef(false)

  useEffect(() => {
    if (hasStarted.current) return
    hasStarted.current = true

    const completeSignIn = async () => {
      try {
        const searchParams = new URLSearchParams(window.location.search)
        const oauthError =
          searchParams.get('error_description') ?? searchParams.get('error')

        if (oauthError) throw new Error(oauthError)

        const code = searchParams.get('code')
        if (!code) throw new Error('Google did not return an authorization code.')

        const { data, error } = await getSupabaseClient().auth.exchangeCodeForSession(code)
        if (error) throw error
        if (!data.session) throw new Error('No session returned from Google sign in.')

        const payload = {
          type: AUTH_MESSAGE_TYPE,
          success: true as const,
          email: data.session.user.email,
          access_token: data.session.access_token,
          refresh_token: data.session.refresh_token,
        }

        if (window.opener && !window.opener.closed) {
          const targetOrigin = getAppOrigin()
          try {
            window.opener.postMessage(payload, targetOrigin)
          } catch {
            window.opener.postMessage(payload, window.location.origin)
          }
          window.close()
          setMessage('Signed in successfully. You can close this window.')
          return
        }

        // Full-page OAuth (no popup): go straight to Connect Workspaces.
        navigate('/connect-workspaces', { replace: true })
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unable to complete Google sign in.'

        if (window.opener && !window.opener.closed) {
          window.opener.postMessage(
            { type: AUTH_MESSAGE_TYPE, success: false, error: errorMessage },
            getAppOrigin(),
          )
        }

        setMessage(errorMessage)
      }
    }

    void completeSignIn()
  }, [navigate])

  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-6 text-center text-[#111827]">
      <p className="text-sm">{message}</p>
    </main>
  )
}
