import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { GoogleIcon } from '../landing-page/components/GoogleIcon'
import { LocusLogo } from '../landing-page/components/LocusLogo'

type ToolId = 'slack' | 'notion' | 'gmail'

type Tool = {
  id: ToolId
  name: string
  description: string
  iconSrc: string
}

const tools: Tool[] = [
  {
    id: 'slack',
    name: 'Slack',
    description:
      "Build memory from channels and threads you're already in. Locus learns — you stay focused.",
    iconSrc: '/slack-logo.png',
  },
  {
    id: 'notion',
    name: 'Notion',
    description:
      "Build memory from channels and threads you're already in. Locus learns — you stay focused.",
    iconSrc: '/notion-logo.png',
  },
  {
    id: 'gmail',
    name: 'Gmail',
    description:
      "Build memory from channels and threads you're already in. Locus learns — you stay focused.",
    iconSrc: '/gmail-logo.png',
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

export default function ConnectWorkspaces({
  email,
  onContinue,
}: {
  email: string
  onContinue: () => void
}) {
  const [connectedTools, setConnectedTools] = useState<Set<ToolId>>(loadConnected)
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

  const toggleTool = (tool: Tool) => {
    if (connectedTools.has(tool.id)) {
      disconnectTool(tool.id)
      return
    }

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
            <br className="hidden sm:block" /> Gmail so we can start building organizational memory.
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
            return (
              <article
                key={tool.id}
                className={`flex min-h-[238px] flex-col rounded-[10px] border bg-white p-5 shadow-[0_1px_2px_rgba(17,24,39,0.02)] ${
                  isConnected ? 'border-[#8177d2]' : 'border-[#dfe1e8]'
                }`}
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
                    {isConnected ? (
                      <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-[#e4f7b8] px-2 py-0.5 text-[12px] font-medium text-[#5f8422]">
                        <span className="h-1.5 w-1.5 rounded-full bg-[#80aa3b]" />
                        Connected
                      </p>
                    ) : (
                      <p className="mt-1 text-[14px] text-[#a2a8b5]">Not Connected</p>
                    )}
                  </div>
                </div>

                <p className="mt-4 flex-1 text-[15px] leading-[1.45] text-[#737b8c]">
                  {tool.description}
                </p>

                <button
                  type="button"
                  aria-pressed={isConnected}
                  onClick={() => toggleTool(tool)}
                  className={`mt-4 min-h-11 w-full rounded-full border px-5 text-[15px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4b38d1] ${
                    isConnected
                      ? 'border-[#e0a3a8] bg-[#fee5e6] text-[#b75058] hover:bg-[#fbd9db]'
                      : 'border-[#4b38d1] bg-[#4b38d1] text-white hover:bg-[#3f2dbd]'
                  }`}
                >
                  {isConnected ? 'Disconnect' : `Connect ${tool.name}`}
                </button>
              </article>
            )
          })}
        </section>

        <div className="mt-8 flex flex-col items-center pb-1">
          <button
            type="button"
            disabled={!canContinue}
            onClick={onContinue}
            className="min-h-[50px] w-full min-w-0 rounded-full bg-[#4b38d1] px-10 text-[16px] font-semibold text-white transition-colors hover:bg-[#3f2dbd] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4b38d1] disabled:cursor-not-allowed disabled:bg-[#aaa7e7] sm:w-[380px]"
          >
            Continue
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
