/**
 * Typed client for the backend's /retrieval routes
 * (backend/src/modules/retrieval/router.py). Base URL is configurable via
 * VITE_API_BASE_URL so this works against a local `uvicorn` process in dev
 * and a deployed API in production without a rebuild-time hardcode.
 */

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

export interface Citation {
  decision_id: string
  permalink: string | null
}

export interface QueryDecisionsResponse {
  answer: string
  citations: Citation[]
  grounded_in: string[]
}

export interface PerExampleScore {
  example_id: string
  category: string
  question: string
  recall_at_5: number | null
  recall_at_10: number | null
  hit_at_5: boolean | null
  hit_at_10: boolean | null
  reciprocal_rank: number | null
  negative_false_positive: boolean | null
  groundedness: number | null
  correctness: number | null
  citation_precision: number | null
  citation_recall: number | null
  retrieval_latency_ms: number | null
  retrieved_decision_ids: string[]
  cited_decision_ids: string[]
  answer_text: string
  judge_rationale: string | null
  error: string | null
  judge_error: string | null
}

export interface EvalReport {
  pipeline_name: string
  top_k: number
  n_examples: number
  recall_at_5: number | null
  recall_at_10: number | null
  hit_rate_at_5: number | null
  hit_rate_at_10: number | null
  mrr: number | null
  negative_hit_rate: number | null
  groundedness: number | null
  correctness: number | null
  citation_precision: number | null
  citation_recall: number | null
  mean_retrieval_latency_ms: number | null
  p95_retrieval_latency_ms: number | null
  category_coverage: Record<string, number>
  n_errors: number
  generated_at: string
}

export interface EvalReportPayload {
  report: EvalReport
  examples: PerExampleScore[]
}

export interface RetrievalStatus {
  database: 'ok' | string
  last_eval_report: EvalReportPayload | null
}

class RagApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'RagApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new RagApiError(`${init?.method ?? 'GET'} ${path} failed: ${response.status} ${body}`, response.status)
  }
  return (await response.json()) as T
}

export async function queryDecisions(
  question: string,
  tenantId: string,
  topK = 10,
): Promise<QueryDecisionsResponse> {
  return request<QueryDecisionsResponse>('/retrieval/query', {
    method: 'POST',
    body: JSON.stringify({ question, tenant_id: tenantId, top_k: topK }),
  })
}

export async function getRetrievalStatus(): Promise<RetrievalStatus> {
  return request<RetrievalStatus>('/retrieval/status')
}

export { RagApiError, API_BASE_URL }
