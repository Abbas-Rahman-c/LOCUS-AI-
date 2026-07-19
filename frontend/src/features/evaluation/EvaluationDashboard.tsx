import { useEvalReport } from './useEvalReport'
import RetrievalStatusBadge from '../retrieval/RetrievalStatusBadge'
import type { PerExampleScore } from '../../lib/api/ragClient'

function fmt(value: number | null): string {
  return value === null ? '-' : value.toFixed(3)
}

function MetricCard({ label, value, invert = false }: { label: string; value: number | null; invert?: boolean }) {
  // invert=true means lower is better (negative_hit_rate) -- color reflects that.
  let colorClass = 'text-locus-text'
  if (value !== null) {
    const good = invert ? value <= 0.15 : value >= 0.7
    const bad = invert ? value >= 0.4 : value < 0.4
    colorClass = good ? 'text-locus-green' : bad ? 'text-red-500' : 'text-locus-text'
  }
  return (
    <div className="rounded-lg border border-locus-border p-4">
      <div className="text-sm text-locus-gray">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${colorClass}`}>{fmt(value)}</div>
    </div>
  )
}

function ExampleRow({ example }: { example: PerExampleScore }) {
  const errored = Boolean(example.error)
  return (
    <tr className={errored ? 'bg-red-50' : undefined}>
      <td className="whitespace-nowrap px-3 py-2 text-sm font-mono">{example.example_id}</td>
      <td className="whitespace-nowrap px-3 py-2 text-sm">{example.category}</td>
      <td className="max-w-md truncate px-3 py-2 text-sm" title={example.question}>
        {example.question}
      </td>
      <td className="px-3 py-2 text-sm">{fmt(example.recall_at_10)}</td>
      <td className="px-3 py-2 text-sm">{fmt(example.reciprocal_rank)}</td>
      <td className="px-3 py-2 text-sm">
        {example.negative_false_positive === null ? '-' : example.negative_false_positive ? 'YES' : 'no'}
      </td>
      <td className="px-3 py-2 text-sm">{fmt(example.groundedness)}</td>
      <td className="px-3 py-2 text-sm">{fmt(example.correctness)}</td>
      <td className="px-3 py-2 text-sm">{fmt(example.citation_precision)}</td>
      <td className="px-3 py-2 text-sm">{fmt(example.citation_recall)}</td>
      <td className="px-3 py-2 text-sm">{example.retrieval_latency_ms === null ? '-' : example.retrieval_latency_ms.toFixed(1)}</td>
      <td className="max-w-xs truncate px-3 py-2 text-sm text-red-600" title={example.error ?? example.judge_error ?? ''}>
        {example.error ?? example.judge_error ?? ''}
      </td>
    </tr>
  )
}

/**
 * Reads the last eval_report.json (written by
 * backend/scripts/run_rag_eval.py) via GET /retrieval/status and renders
 * it. This is a read-only view -- running the eval itself is a CLI/CI step,
 * not a browser action (see useEvalReport.ts).
 */
export default function EvaluationDashboard() {
  const { report, loading, error, refresh } = useEvalReport()

  return (
    <div className="mx-auto max-w-6xl p-6 text-locus-text">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">RAG Evaluation</h1>
        <div className="flex items-center gap-3">
          <RetrievalStatusBadge />
          <button
            onClick={refresh}
            className="rounded-md border border-locus-border px-3 py-1 text-sm hover:bg-gray-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading && !report && <p className="text-locus-gray">Loading eval report...</p>}
      {error && <p className="text-red-500">Failed to load status: {error}</p>}
      {!loading && !error && !report && (
        <p className="text-locus-gray">
          No eval_report.json found yet. Run{' '}
          <code className="rounded bg-gray-100 px-1">poetry run python scripts/run_rag_eval.py</code> from{' '}
          <code className="rounded bg-gray-100 px-1">backend/</code>, then refresh.
        </p>
      )}

      {report && (
        <>
          <div className="mb-2 text-sm text-locus-gray">
            Pipeline: <span className="font-mono">{report.report.pipeline_name}</span> &middot; top_k=
            {report.report.top_k} &middot; {report.report.n_examples} examples ({report.report.n_errors} errors)
            &middot; generated {new Date(report.report.generated_at).toLocaleString()}
          </div>

          <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <MetricCard label="Recall@5" value={report.report.recall_at_5} />
            <MetricCard label="Recall@10" value={report.report.recall_at_10} />
            <MetricCard label="Hit Rate@10 (accuracy)" value={report.report.hit_rate_at_10} />
            <MetricCard label="MRR" value={report.report.mrr} />
            <MetricCard label="Negative hit rate" value={report.report.negative_hit_rate} invert />
            <MetricCard label="Groundedness" value={report.report.groundedness} />
            <MetricCard label="Correctness" value={report.report.correctness} />
            <MetricCard label="Citation precision" value={report.report.citation_precision} />
            <MetricCard label="Citation recall" value={report.report.citation_recall} />
            <MetricCard label="Mean latency (ms)" value={report.report.mean_retrieval_latency_ms} />
            <MetricCard label="P95 latency (ms)" value={report.report.p95_retrieval_latency_ms} />
          </div>

          <h2 className="mb-2 text-lg font-semibold">Per-example detail</h2>
          <div className="overflow-x-auto rounded-lg border border-locus-border">
            <table className="min-w-full divide-y divide-locus-border">
              <thead className="bg-gray-50">
                <tr>
                  {['ID', 'Category', 'Question', 'Recall@10', 'RR', 'Neg. FP', 'Grounded', 'Correct', 'Cite P', 'Cite R', 'Latency (ms)', 'Error'].map(
                    (h) => (
                      <th key={h} className="px-3 py-2 text-left text-xs font-medium uppercase text-locus-gray">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-locus-border">
                {report.examples.map((example) => (
                  <ExampleRow key={example.example_id} example={example} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
