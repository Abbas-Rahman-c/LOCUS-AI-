import { useRetrievalStatus } from './useRetrievalStatus'

/** Small "is retrieval up" indicator -- safe to drop into a header/nav. */
export default function RetrievalStatusBadge() {
  const { status, loading, error } = useRetrievalStatus()

  let label = 'Checking...'
  let dotClass = 'bg-locus-gray-light'

  if (error) {
    label = 'Status unavailable'
    dotClass = 'bg-red-500'
  } else if (!loading && status) {
    const ok = status.database === 'ok'
    label = ok ? 'Retrieval online' : 'Retrieval degraded'
    dotClass = ok ? 'bg-locus-green' : 'bg-yellow-500'
  }

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-locus-border px-3 py-1 text-sm text-locus-text">
      <span className={`h-2 w-2 rounded-full ${dotClass}`} aria-hidden="true" />
      {label}
    </span>
  )
}
