import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Browsers restore scroll position on refresh by default - fine for long
// feeds, disorienting on a one-page marketing site where a refresh should
// read as a fresh visit. Each route now owns its own scroll position
// explicitly instead (see LandingPage.tsx).
if ('scrollRestoration' in window.history) {
  window.history.scrollRestoration = 'manual'
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
