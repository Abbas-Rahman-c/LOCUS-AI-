/** Canonical production origin for OAuth redirects. */
const PRODUCTION_APP_ORIGIN = 'https://locus-ai-frontend.vercel.app'

/**
 * Origin used for Supabase Google OAuth redirectTo.
 * Prefer VITE_APP_URL, then the current origin — but never the GoDaddy-hosted
 * locusaiapp.com site (DNS still points at Website Builder, not Vercel).
 */
export function getAppOrigin() {
  const configured = (import.meta.env.VITE_APP_URL as string | undefined)?.replace(/\/$/, '')
  if (configured) return configured

  if (typeof window === 'undefined') return PRODUCTION_APP_ORIGIN

  const origin = window.location.origin
  const host = window.location.hostname

  // Custom domain is registered in Vercel but still served by GoDaddy DPS.
  if (host === 'locusaiapp.com' || host === 'www.locusaiapp.com') {
    return PRODUCTION_APP_ORIGIN
  }

  if (host.endsWith('.vercel.app') || host === 'localhost' || host === '127.0.0.1') {
    return origin
  }

  return PRODUCTION_APP_ORIGIN
}

export function getAuthCallbackUrl() {
  return `${getAppOrigin()}/?auth_callback=1`
}
