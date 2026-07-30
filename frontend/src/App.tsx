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
import WelcomePage from '../landing-page/WelcomePage'
import ConnectWorkspaces from './ConnectWorkspaces'
import OAuthCallback from './OAuthCallback'
import { getSupabaseClient, isSupabaseConfigured } from './lib/supabase'
import DecisionReady from './DecisionReady'
import { DashboardShell } from './components/DashboardShell'
import MainDashboardEntry from './pages/MainDashboardEntry'
import DecisionLogPage from './pages/DecisionLogPage'
import TeamPulse from './pages/TeamPulse'
import SettingsPage from './pages/SettingsPage'

const WORKSPACES_DONE_KEY = 'locus:workspaces-connected'

/** Full marketing page: Get Started → How it works → Why Locus (scrollable). */
function HowItWorksMarketing() {
  return <LandingPage initialSection="how-it-works" />
}

function useAuthEmail() {
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    if (!isSupabaseConfigured()) {
      setAuthReady(true)
      return
    }

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

  return { userEmail, authReady }
}

function useWorkspacesConnected() {
  const [workspacesConnected, setWorkspacesConnected] = useState(
    () => sessionStorage.getItem(WORKSPACES_DONE_KEY) === '1',
  )

  const markConnected = () => {
    sessionStorage.setItem(WORKSPACES_DONE_KEY, '1')
    setWorkspacesConnected(true)
  }

  return { workspacesConnected, markConnected }
}

function ConnectWorkspacesRoute() {
  const navigate = useNavigate()
  const { userEmail, authReady } = useAuthEmail()
  const { workspacesConnected, markConnected } = useWorkspacesConnected()

  if (!authReady) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white text-sm text-[#6B7280]">
        Loading…
      </main>
    )
  }

  if (!userEmail) {
    return <Navigate to="/welcome" replace />
  }

  if (workspacesConnected) {
    return (
      <DecisionReady
        userEmail={userEmail}
        onGoToDashboard={() => navigate('/dashboard')}
        onOpenSettings={() => navigate('/settings')}
      />
    )
  }

  return <ConnectWorkspaces email={userEmail} onContinue={markConnected} />
}

function AuthRoutes() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { userEmail, authReady } = useAuthEmail()
  const { workspacesConnected } = useWorkspacesConnected()

  const isOAuthCallback =
    searchParams.has('auth_callback') ||
    searchParams.has('code') ||
    searchParams.has('error')

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
    return <Navigate to="/connect-workspaces" replace />
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

  return <LandingPage />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AuthRoutes />} />
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/connect-workspaces" element={<ConnectWorkspacesRoute />} />

        {/* Full 3-section landing (Get Started + How it works + Why Locus) */}
        <Route path="/how-it-works" element={<HowItWorksMarketing />} />

        {/* Dashboard pages share one shell / one localhost */}
        <Route element={<DashboardShell />}>
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
