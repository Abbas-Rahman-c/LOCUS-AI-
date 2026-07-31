import type { DecisionOut, DecisionRecordType } from './api'
import type { MemoryRecord, MemoryRecordType } from '../components/MemoryRecordDetail'

const RECORD_TYPE_LABELS: Record<DecisionRecordType, MemoryRecordType> = {
  decision: 'Decision',
  action_item: 'Action Item',
  blocker: 'Blocker',
}

export const PLATFORM_LABELS: Record<string, string> = {
  gmail: 'Gmail',
  slack: 'Slack',
  notion: 'Notion',
}

export function timeAgo(iso: string, now = Date.now()): string {
  const elapsedMs = Math.max(0, now - new Date(iso).getTime())
  const hours = Math.floor(elapsedMs / 3_600_000)
  if (hours < 1) return 'just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/**
 * Adapts a real DecisionOut row into the MemoryRecordDetail panel's display
 * shape. All fields come from the actual decision - nothing here is
 * placeholder text.
 */
export function decisionToMemoryRecord(decision: DecisionOut): MemoryRecord {
  const type: MemoryRecordType =
    RECORD_TYPE_LABELS[decision.record_type as DecisionRecordType] ?? 'Decision'
  const platform = decision.source_platforms[0]
  const platformLabel = platform ? PLATFORM_LABELS[platform] ?? platform : 'Unknown source'

  return {
    id: decision.id,
    type,
    title: decision.decision_statement,
    meta: `${platformLabel} · ${timeAgo(decision.created_at)}`,
    summary: decision.rationale || decision.decision_statement,
    participants: decision.actors.length > 0 ? decision.actors.map((a) => a.role).join(', ') : 'Not recorded',
    source: platformLabel,
    confidence: `${decision.confidence.toFixed(2)} — ${decision.status}`,
    status: decision.superseded_by ? 'Superseded' : 'Current',
    listSource: platformLabel,
    date: formatDate(decision.created_at),
    sourceLink: decision.source_links[0],
  }
}
