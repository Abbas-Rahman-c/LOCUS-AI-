import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { GoogleIcon } from '../landing-page/components/GoogleIcon'
import { LocusLogo } from '../landing-page/components/LocusLogo'
import { isSupabaseConfigured } from './lib/supabase'

type ToolId = 'slack' | 'notion' | 'gmail'

type Tool = {
  id: ToolId
  name: string
  description: string
  iconSrc: string
  oauthPath: string
}

const tools: Tool[] = [
  {
    id: 'slack',
    name: 'Slack',
    description:
      "Capture decisions from channels and threads you're already in. Locus listens — you stay focused.",
    iconSrc: '/slack-logo.png',
    oauthPath: 'slack-oauth/authorize',
  },
  {
    id: 'notion',
    name: 'Notion',
    description:
      "Capture decisions from channels and threads you're already in. Locus listens — you stay focused.",
    iconSrc: '/notion-logo.png',
    oauthPath: 'notion-oauth/authorize',
  },
  {
    id: 'gmail',
    name: 'Gmail',
    description:
      "Capture decisions from channels and threads you're already in. Locus listens — you stay focused.",
    iconSrc: '/gmail-logo.png',
    oauthPath: 'gmail-oauth/authorize',
  },
]

const STORAGE_KEY = 'locus:connected-tools'

function loadConnected(): Set<ToolId> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw) as ToolId[]
    return new Set(parsed.filter((id) => tools.some((t) => t.id === id)))
  } catch {
    return new Set()
  }
}

function saveConnected(toolsSet: Set<ToolId>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...toolsSet]))
}

function oauthAuthorizeUrl(oauthPath: string) {
  const base = import.meta.env.VITE_SUPABASE_URL as string | undefined
  if (!base) return null
  return `${base.replace(/\/$/, '')}/functions/v1/${oauthPath}`
}

export default function ConnectWorkspaces({
  email,
  onContinue,
}: {
  email: string
  onContinue: () => void
}) {
  const [connectedTools, setConnectedTools] = useState<Set<ToolId>>(loadConnected)
  const [connectingTool, setConnectingTool] = useState<ToolId | null>(null)
  const [connectError, setConnectError] = useState<string | null>(null)
  const canContinue = connectedTools.size > 0

  useEffect(() => {
    saveConnected(connectedTools)
  }, [connectedTools])

  const markConnected = useCallback((toolId: ToolId) => {
    setConnectedTools((current) => {
      const next = new Set(current)
      next.add(toolId)
      return next
    })
  }, [])

  const disconnectTool = useCallback((toolId: ToolId) => {
    setConnectedTools((current) => {
      const next = new Set(current)
      next.delete(toolId)
      return next
    })
  }, [])

  const connectTool = async (tool: Tool) => {
    setConnectError(null)

    if (connectedTools.has(tool.id)) {
      disconnectTool(tool.id)
      return
    }

    const authorizeUrl =
      isSupabaseConfigured() ? oauthAuthorizeUrl(tool.oauthPath) : null

    // When OAuth edge functions are available, open the real provider flow.
    if (authorizeUrl) {
      setConnectingTool(tool.id)
      const popup = window.open(
        authorizeUrl,
        `locus-connect-${tool.id}`,
        'popup=yes,width=560,height=720,top=80,left=120',
      )

      if (!popup) {
        setConnectingTool(null)
        setConnectError('Please allow popups to connect this tool.')
        return
      }

      await new Promise<void>((resolve) => {
        const timer = window.setInterval(() => {
          if (popup.closed) {
            window.clearInterval(timer)
            resolve()
          }
        }, 400)
      })

      setConnectingTool(null)
      markConnected(tool.id)
      return
    }

    // Local / demo path when Supabase functions aren't configured.
    markConnected(tool.id)
  }

  return (
    <main className="min-h-screen bg-[#f8f8fc] px-5 py-6 text-[#17171b] sm:px-8 sm:py-8 lg:px-10">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-[1360px] flex-col items-center">
        <LocusLogo size={40} className="gap-3 [&_span]:text-[22px]" />

        <section className="mt-8 text-center">
          <h1 className="text-[28px] font-bold leading-tight sm:text-[32px]">
            Connect your workspaces
          </h1>
          <p className="mx-auto mt-3 max-w-[660px] text-[15px] leading-[1.45] text-[#7a8190] sm:text-[17px]">
            Your Locus account is ready. Next: connect Slack, Notion, and
            <br className="hidden sm:block" /> Gmail so we can start capturing decisions.
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-2 text-[14px] text-[#7a8190]">
            <GoogleIcon />
            <span>Signed in as</span>
            <strong className="font-semibold text-[#25252b]">{email}</strong>
          </div>
        </section>

        <section aria-label="Workspace tools" className="mt-8 grid w-full gap-5 md:grid-cols-3">
          {tools.map((tool) => {
            const isConnected = connectedTools.has(tool.id)
            const isConnecting = connectingTool === tool.id
            return (
              <article
                key={tool.id}
                className="flex min-h-[238px] flex-col rounded-[8px] border border-[#dfe1e8] bg-white p-5 shadow-[0_1px_2px_rgba(17,24,39,0.02)]"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-[9px] border border-[#bfc4cf] bg-white">
                    <img
                      src={tool.iconSrc}
                      alt=""
                      className="h-9 w-9 bg-white object-contain"
                    />
                  </div>
                  <div>
                    <h2 className="text-[18px] font-bold leading-tight">{tool.name}</h2>
                    <p
                      className={`mt-1 text-[14px] ${
                        isConnected ? 'font-medium text-[#16835d]' : 'text-[#a2a8b5]'
                      }`}
                    >
                      {isConnected ? 'Connected' : 'Not Connected'}
                    </p>
                  </div>
                </div>

                <p className="mt-4 flex-1 text-[15px] leading-[1.45] text-[#737b8c]">
                  {tool.description}
                </p>

                <button
                  type="button"
                  aria-pressed={isConnected}
                  disabled={isConnecting}
                  onClick={() => void connectTool(tool)}
                  className={`mt-4 min-h-11 w-full rounded-full px-5 text-[15px] font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4b38d1] disabled:cursor-wait disabled:opacity-80 ${
                    isConnected
                      ? 'bg-[#16835d] hover:bg-[#126e4f]'
                      : 'bg-[#4b38d1] hover:bg-[#3f2dbd]'
                  }`}
                >
                  {isConnecting
                    ? `Connecting ${tool.name}…`
                    : isConnected
                      ? `${tool.name} Connected`
                      : `Connect ${tool.name}`}
                </button>
              </article>
            )
          })}
        </section>

        {connectError && (
          <p role="alert" className="mt-4 text-center text-[13px] text-red-600">
            {connectError}
          </p>
        )}

        <div className="mt-8 flex flex-col items-center pb-1">
          <button
            type="button"
            disabled={!canContinue}
            onClick={onContinue}
            className="min-h-[50px] w-full min-w-0 rounded-full bg-[#4b38d1] px-10 text-[16px] font-semibold text-white transition-colors hover:bg-[#3f2dbd] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4b38d1] disabled:cursor-not-allowed disabled:bg-[#aaa7e7] sm:w-[380px]"
          >
            Connect A Tool to Continue
          </button>
          <p className="mt-3 text-center text-[13px] text-[#7a8190]">
            You can connect or disconnect tools anytime from{' '}
            <Link to="/settings" className="font-medium text-[#4b38d1] hover:underline">
              Settings
            </Link>
          </p>
        </div>
      </div>
    </main>
  )
}
