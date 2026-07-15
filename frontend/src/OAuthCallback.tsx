import { useEffect, useRef, useState } from 'react'
import { getSupabaseClient } from './lib/supabase'

const AUTH_MESSAGE_TYPE = 'locus:google-auth'

export default function OAuthCallback() {
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

        window.opener?.postMessage(
          {
            type: AUTH_MESSAGE_TYPE,
            success: true,
            email: data.session.user.email,
          },
          window.location.origin,
        )
        window.close()
        setMessage('Signed in successfully. You can close this window.')
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unable to complete Google sign in.'

        window.opener?.postMessage(
          { type: AUTH_MESSAGE_TYPE, success: false, error: errorMessage },
          window.location.origin,
        )
        setMessage(errorMessage)
      }
    }

    void completeSignIn()
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-6 text-center text-[#111827]">
      <p className="text-sm">{message}</p>
    </main>
  )
}
