import LandingPage from '../landing-page/LandingPage'
import OAuthCallback from './OAuthCallback'

function App() {
  if (new URLSearchParams(window.location.search).has('auth_callback')) {
    return <OAuthCallback />
  }

  return <LandingPage />
}

export default App
