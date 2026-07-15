import { useEffect, useState } from 'react'
import LandingPage from '../landing-page/LandingPage'
import ConnectWorkspaces from './ConnectWorkspaces'
import OAuthCallback from './OAuthCallback'
import { getSupabaseClient } from './lib/supabase'

function App() {
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const isOAuthCallback = new URLSearchParams(window.location.search).has(
    'auth_callback',
  )

  useEffect(() => {
    const supabase = getSupabaseClient()

    void supabase.auth.getSession().then(({ data }) => {
      setUserEmail(data.session?.user.email ?? null)
    })

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user.email ?? null)
    })

    return () => data.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (userEmail && !isOAuthCallback) {
      window.history.replaceState(
        {},
        '',
        `${window.location.pathname}?connect_workspaces=1`,
      )
    }
  }, [isOAuthCallback, userEmail])

  if (isOAuthCallback) {
    return <OAuthCallback />
  }

  if (userEmail) {
    return <ConnectWorkspaces email={userEmail} />
  }

  return <LandingPage onAuthenticated={setUserEmail} />
}

export default App
