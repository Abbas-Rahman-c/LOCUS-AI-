import { useCallback, useEffect, useRef, useState } from 'react'
import { getRetrievalStatus, type RetrievalStatus } from '../../lib/api/ragClient'

export interface UseRetrievalStatusResult {
  status: RetrievalStatus | null
  loading: boolean
  error: string | null
  refresh: () => void
}

/**
 * Polls GET /retrieval/status -- DB pool health plus whatever eval_report.json
 * currently sits at the backend repo root. `intervalMs` defaults to 30s;
 * pass 0 to fetch once and never poll.
 */
export function useRetrievalStatus(intervalMs = 30_000): UseRetrievalStatusResult {
  const [status, setStatus] = useState<RetrievalStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const fetchStatus = useCallback(() => {
    setLoading(true)
    getRetrievalStatus()
      .then((result) => {
        if (mounted.current) {
          setStatus(result)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (mounted.current) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (mounted.current) setLoading(false)
      })
  }, [])

  useEffect(() => {
    mounted.current = true
    fetchStatus()
    if (intervalMs > 0) {
      const id = setInterval(fetchStatus, intervalMs)
      return () => {
        mounted.current = false
        clearInterval(id)
      }
    }
    return () => {
      mounted.current = false
    }
  }, [fetchStatus, intervalMs])

  return { status, loading, error, refresh: fetchStatus }
}
