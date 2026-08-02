export type SourceName = 'Slack' | 'Notion' | 'Gmail'

const SOURCE_LOGOS: Record<SourceName, string> = {
  Slack: '/slack-logo.png',
  Notion: '/notion-logo.png',
  Gmail: '/gmail-logo.png',
}

export function SourceLogo({
  source,
  className = 'h-6 w-6',
}: {
  source: SourceName
  className?: string
}) {
  return (
    <img
      src={SOURCE_LOGOS[source]}
      alt=""
      aria-hidden="true"
      className={`bg-white object-contain ${className}`}
    />
  )
}
