/** Demo/production app origin — Vercel only (custom domain deferred). */
export const APP_ORIGIN = 'https://locus-ai-frontend.vercel.app'

export function getAppOrigin() {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1') {
      return window.location.origin
    }
  }
  return APP_ORIGIN
}

export function getAuthCallbackUrl() {
  return `${getAppOrigin()}/?auth_callback=1`
}
