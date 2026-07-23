import { useEffect, useState } from 'react'
import LandingPage from '../landing-page/LandingPage'
import ConnectWorkspaces from './ConnectWorkspaces'
import OAuthCallback from './OAuthCallback'
import { getSupabaseClient } from './lib/supabase'
import DecisionReady from './DecisionReady'
import MainDashboardEntry from './pages/MainDashboardEntry'
import DecisionLogPage from './pages/DecisionLogPage'
import TeamPulse from './pages/TeamPulse'
import SettingsPage from './pages/SettingsPage'

const DASHBOARD_ROUTES = new Set([
  '/dashboard',
  '/decision-log',
  '/team-pulse',
  '/settings',
  '/how-it-works',
])

function App() {
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [workspacesConnected, setWorkspacesConnected] = useState(false)
  const pathname = window.location.pathname
  const searchParams = new URLSearchParams(window.location.search)

  const isDashboardRoute = pathname === '/dashboard'
  const isDecisionLogRoute = pathname === '/decision-log'
  const isTeamPulseRoute = pathname === '/team-pulse'
  const isSettingsRoute = pathname === '/settings'
  const isHowItWorksRoute = pathname === '/how-it-works'
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
    if (!userEmail || isOAuthCallback) return
    if (DASHBOARD_ROUTES.has(pathname)) return

    window.history.replaceState(
      {},
      '',
      `${pathname}?connect_workspaces=1`,
    )
  }, [isOAuthCallback, pathname, userEmail])

  if (isOAuthCallback) {
    return <OAuthCallback />
  }

  if (isDashboardRoute) {
    return <MainDashboardEntry />
  }

  if (isDecisionLogRoute) {
    return <DecisionLogPage />
  }

  if (isTeamPulseRoute) {
    return <TeamPulse />
  }

  if (isSettingsRoute) {
    return <SettingsPage />
  }

  if (isHowItWorksRoute) {
    return <LandingPage onAuthenticated={setUserEmail} initialSection="how-it-works" />
  }

  if (userEmail && !workspacesConnected) {
    return (
      <ConnectWorkspaces
        email={userEmail}
        onContinue={() => setWorkspacesConnected(true)}
      />
    )
  }

  if (userEmail && workspacesConnected) {
    return (
      <DecisionReady
        userEmail={userEmail}
        onGoToDashboard={() => {
          window.location.href = '/dashboard'
        }}
        onOpenSettings={() => {
          window.location.href = '/settings'
        }}
      />
    )
  }

  return <LandingPage onAuthenticated={setUserEmail} />
}

export default App
