import { useEffect, useState } from 'react'
import LandingPage from '../landing-page/LandingPage'
import ConnectWorkspaces from './ConnectWorkspaces'
import OAuthCallback from './OAuthCallback'
import { getSupabaseClient } from './lib/supabase'
import DecisionReady from "./DecisionReady";
import MainDashboardEntry from './pages/MainDashboardEntry'

function App() {
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [workspacesConnected, setWorkspacesConnected] = useState(false);
  const searchParams = new URLSearchParams(window.location.search)
  const isDashboardRoute = window.location.pathname === '/dashboard'
  const isHowItWorksRoute = window.location.pathname === '/how-it-works';
  const isOAuthCallback =
    searchParams.has('auth_callback') ||
    searchParams.has('code') ||
    searchParams.has('error')

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
  return <OAuthCallback />;
}

if (isDashboardRoute) {
  return <MainDashboardEntry />;
}

if (isHowItWorksRoute) {
  return <LandingPage onAuthenticated={setUserEmail} />;
}

if (userEmail && !workspacesConnected) {
  return <ConnectWorkspaces email={userEmail} onContinue={() => setWorkspacesConnected(true)} />;
}

if (userEmail && workspacesConnected) {
  return (
    <DecisionReady
      userEmail={userEmail}
      onGoToDashboard={() => {
        window.location.href = "/dashboard";
      }}
    />
  );
}

return <LandingPage onAuthenticated={setUserEmail} />;
}

export default App