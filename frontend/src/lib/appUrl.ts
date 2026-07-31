/** Demo/production app origin — Vercel only (custom domain deferred).
 * Fallback for non-browser contexts only; in the browser this always
 * defers to the actual origin the app is running on, so OAuth redirects
 * work correctly across the shared deployment, preview deployments, and
 * independent forks alike, not just the one canonical Vercel URL. */
export const APP_ORIGIN = 'https://locus-ai-frontend.vercel.app'

export function getAppOrigin() {
  if (typeof window !== 'undefined') {
    return window.location.origin
  }
  return APP_ORIGIN
}

export function getAuthCallbackUrl() {
  return `${getAppOrigin()}/?auth_callback=1`
}
