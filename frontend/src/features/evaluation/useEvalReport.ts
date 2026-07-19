import { useCallback, useEffect, useRef, useState } from 'react'
import { getRetrievalStatus, type EvalReportPayload } from '../../lib/api/ragClient'

export interface UseEvalReportResult {
  report: EvalReportPayload | null
  loading: boolean
  error: string | null
  refresh: () => void
}

/**
 * Reads the most recent eval_report.json via GET /retrieval/status
 * (StatusResponse.last_eval_report) -- the same file scripts/run_rag_eval.py
 * writes after a run. There's no separate "run eval" endpoint by design:
 * evaluation runs are triggered from the CLI (or CI), not from the browser,
 * so this hook only ever reads the last completed run's result.
 */
export function useEvalReport(): UseEvalReportResult {
  const [report, setReport] = useState<EvalReportPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const fetchReport = useCallback(() => {
    setLoading(true)
    getRetrievalStatus()
      .then((status) => {
        if (mounted.current) {
          setReport(status.last_eval_report)
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
    fetchReport()
    return () => {
      mounted.current = false
    }
  }, [fetchReport])

  return { report, loading, error, refresh: fetchReport }
}
