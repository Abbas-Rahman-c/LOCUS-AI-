import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const isLocalhostAlias =
  import.meta.env.DEV &&
  (window.location.hostname === 'localhost' ||
    window.location.hostname === '[::1]')

if (isLocalhostAlias) {
  const canonicalUrl = new URL(window.location.href)
  canonicalUrl.hostname = '127.0.0.1'
  canonicalUrl.port = '5173'
  window.location.replace(canonicalUrl)
} else {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
