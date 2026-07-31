import { getSupabaseClient } from './supabase'
import { getTenantId } from './api'

/**
 * Shared real-backend wiring for Slack/Notion/Gmail connections, used by
 * both the onboarding ConnectWorkspaces screen and the dashboard's Sources
 * panel. Reads source_connections directly (RLS lets an authenticated
 * member read their own tenant's rows) and connects via the real
 * slack-oauth / notion-oauth / gmail-oauth Edge Functions' popup flow.
 */

export type SourceId = 'slack' | 'notion' | 'gmail'

export interface SourceConnectionRow {
  source: SourceId
  status: string
  last_synced_at: string | null
}

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? ''

interface OAuthMessage {
  type: 'locus:source-oauth'
  source: SourceId
  success: boolean
  error?: string
}

function isOAuthMessage(value: unknown): value is OAuthMessage {
  if (!value || typeof value !== 'object') return false
  const message = value as Partial<OAuthMessage>
  return (
    message.type === 'locus:source-oauth' &&
    (message.source === 'slack' || message.source === 'notion' || message.source === 'gmail') &&
    typeof message.success === 'boolean'
  )
}

export async function fetchSourceConnections(): Promise<SourceConnectionRow[]> {
  const tenantId = await getTenantId()
  const { data, error } = await getSupabaseClient()
    .from('source_connections')
    .select('source, status, last_synced_at')
    .eq('tenant_id', tenantId)

  if (error) throw error
  return (data ?? []) as SourceConnectionRow[]
}

/**
 * Opens the real OAuth popup for a source and resolves once the connection
 * completes.
 *
 * Supabase Edge Functions can't serve HTML on the default domain (the
 * platform rewrites any text/html response to text/plain), so the OAuth
 * callback redirects the popup to /oauth/source-callback on our own
 * frontend origin instead, which posts the completion message back here.
 * This also polls the real source_connections row directly as a fallback
 * signal (and to self-close the popup) — that only depends on the callback
 * having written to the database, not on postMessage succeeding.
 */
export async function connectSource(sourceId: SourceId): Promise<{ success: boolean; error?: string }> {
  if (!SUPABASE_URL) {
    return { success: false, error: 'Supabase is not configured.' }
  }

  const popup = window.open(
    'about:blank',
    `locus-${sourceId}-oauth`,
    'popup=yes,width=520,height=680,top=100,left=100',
  )
  if (!popup) {
    return { success: false, error: 'Please allow popups for this site and try again.' }
  }

  // Snapshot whether this source was already active *before* this attempt,
  // so a reconnect of an already-connected source doesn't false-positive
  // on the very first poll tick.
  let wasActive = false
  try {
    const rows = await fetchSourceConnections()
    wasActive = rows.some((row) => row.source === sourceId && row.status === 'active')
  } catch {
    // Unknown baseline — poll will just wait for an active row either way.
  }

  return new Promise((resolve) => {
    let settled = false
    let pollClosedId = 0
    let pollDbId = 0

    const cleanup = () => {
      window.removeEventListener('message', handleMessage)
      window.clearInterval(pollClosedId)
      window.clearInterval(pollDbId)
    }

    const settle = (result: { success: boolean; error?: string }) => {
      if (settled) return
      settled = true
      cleanup()
      if (!popup.closed) popup.close()
      resolve(result)
    }

    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return
      if (event.source !== popup) return
      if (!isOAuthMessage(event.data) || event.data.source !== sourceId) return
      settle({ success: event.data.success, error: event.data.error })
    }

    window.addEventListener('message', handleMessage)

    if (!wasActive) {
      pollDbId = window.setInterval(() => {
        void fetchSourceConnections()
          .then((rows) => {
            if (settled) return
            const nowActive = rows.some((row) => row.source === sourceId && row.status === 'active')
            if (nowActive) settle({ success: true })
          })
          .catch(() => {
            // Transient read failure — the next tick (or popup.closed) will resolve it.
          })
      }, 1500)
    }

    pollClosedId = window.setInterval(() => {
      if (settled || !popup.closed) return

      // One last real check before declaring failure — the callback may have
      // written the row moments before the user (or the page itself) closed
      // the popup, ahead of the next 1.5s DB poll tick.
      if (wasActive) {
        settle({ success: false, error: 'Connection window was closed before finishing.' })
        return
      }
      void fetchSourceConnections()
        .then((rows) => {
          const nowActive = rows.some((row) => row.source === sourceId && row.status === 'active')
          settle(
            nowActive
              ? { success: true }
              : { success: false, error: 'Connection window was closed before finishing.' },
          )
        })
        .catch(() => {
          settle({ success: false, error: 'Connection window was closed before finishing.' })
        })
    }, 500)

    void (async () => {
      try {
        const [tenantId, sessionResult] = await Promise.all([
          getTenantId(),
          getSupabaseClient().auth.getSession(),
        ])
        const accessToken = sessionResult.data.session?.access_token
        if (!accessToken) throw new Error('Not signed in.')

        const authorizeUrl = new URL(`${SUPABASE_URL}/functions/v1/${sourceId}-oauth/authorize`)
        authorizeUrl.searchParams.set('tenant_id', tenantId)
        authorizeUrl.searchParams.set('access_token', accessToken)
        authorizeUrl.searchParams.set('redirect_origin', window.location.origin)
        popup.location.href = authorizeUrl.toString()
      } catch (error) {
        settle({ success: false, error: error instanceof Error ? error.message : 'Unable to start connection.' })
      }
    })()
  })
}
