import { useEffect, useState } from 'react'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useSearchParams,
} from 'react-router-dom'
import LandingPage from '../landing-page/LandingPage'
import HowItWorks from '../landing-page/HowItWorks'
import ConnectWorkspaces from './ConnectWorkspaces'
import OAuthCallback from './OAuthCallback'
import { getSupabaseClient } from './lib/supabase'
import DecisionReady from './DecisionReady'
import { DashboardShell } from './components/DashboardShell'
import MainDashboardEntry from './pages/MainDashboardEntry'
import DecisionLogPage from './pages/DecisionLogPage'
import TeamPulse from './pages/TeamPulse'
import SettingsPage from './pages/SettingsPage'

function AuthRoutes() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [workspacesConnected, setWorkspacesConnected] = useState(false)
  const [authReady, setAuthReady] = useState(false)

  const isOAuthCallback =
    searchParams.has('auth_callback') ||
    searchParams.has('code') ||
    searchParams.has('error')

  useEffect(() => {
    const supabase = getSupabaseClient()

    void supabase.auth.getSession().then(({ data }) => {
      setUserEmail(data.session?.user.email ?? null)
      setAuthReady(true)
    })

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user.email ?? null)
      setAuthReady(true)
    })

    return () => data.subscription.unsubscribe()
  }, [])

  if (isOAuthCallback) {
    return <OAuthCallback />
  }

  if (!authReady) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white text-sm text-[#6B7280]">
        Loading…
      </main>
    )
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
        onGoToDashboard={() => navigate('/dashboard')}
        onOpenSettings={() => navigate('/settings')}
      />
    )
  }

  return <LandingPage onAuthenticated={setUserEmail} />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AuthRoutes />} />

        {/* One app shell — same localhost, client-side nav between pages */}
        <Route element={<DashboardShell />}>
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/dashboard" element={<MainDashboardEntry />} />
          <Route path="/decision-log" element={<DecisionLogPage />} />
          <Route path="/team-pulse" element={<TeamPulse />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
