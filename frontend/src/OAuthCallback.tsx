import { useEffect, useState } from 'react'
import { getSupabaseClient } from './lib/supabase'

const AUTH_MESSAGE_TYPE = 'locus:google-auth'

export default function OAuthCallback() {
  const [message, setMessage] = useState('Completing your Google sign in...')

  useEffect(() => {
    const completeSignIn = async () => {
      try {
        const code = new URLSearchParams(window.location.search).get('code')
        if (!code) throw new Error('Google did not return an authorization code.')

        const { error } = await getSupabaseClient().auth.exchangeCodeForSession(code)
        if (error) throw error

        window.opener?.postMessage(
          { type: AUTH_MESSAGE_TYPE, success: true },
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
