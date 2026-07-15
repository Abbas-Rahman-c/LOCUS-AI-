import { useState } from 'react'
import { GoogleIcon } from '../landing-page/components/GoogleIcon'

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
    description: "Capture decisions from channels and threads you're already in. Locus listens - you stay focused.",
    iconSrc: '/slack-logo.png',
  },
  {
    id: 'notion',
    name: 'Notion',
    description: "Capture decisions from channels and threads you're already in. Locus listens - you stay focused.",
    iconSrc: '/notion-logo.png',
  },
  {
    id: 'gmail',
    name: 'Gmail',
    description: 'Email-based decisions are next. Slack and Notion are more than enough to get started today.',
    iconSrc: '/gmail-logo.png',
  },
]

export default function ConnectWorkspaces({ email }: { email: string }) {
  const [connectedTools, setConnectedTools] = useState<Set<ToolId>>(new Set())
  const canContinue = connectedTools.size > 0

  const toggleTool = (toolId: ToolId) => {
    setConnectedTools((current) => {
      const next = new Set(current)
      if (next.has(toolId)) next.delete(toolId)
      else next.add(toolId)
      return next
    })
  }

  return (
    <main className="min-h-screen bg-[#f8f8fc] px-5 py-10 text-[#17171b] sm:px-8 sm:py-14 lg:px-12 lg:py-16">
      <div className="mx-auto flex min-h-[calc(100vh-8rem)] w-full max-w-[1360px] flex-col items-center">
        <div className="flex items-center gap-3" aria-label="Locus AI">
          <img src="/locus-mark.png" alt="" className="h-12 w-12 rounded-[7px]" />
          <span className="text-[25px] font-bold leading-none">
            LOCUS <span className="text-[#4b38d1]">AI</span>
          </span>
        </div>

        <section className="mt-16 text-center">
          <h1 className="text-[32px] font-bold leading-tight sm:text-[38px]">Connect your workspaces</h1>
          <p className="mx-auto mt-6 max-w-[680px] text-[17px] leading-[1.5] text-[#7a8190] sm:text-[20px]">
            Your Locus account is ready. Next: connect Slack, Notion, and
            <br className="hidden sm:block" /> Gmail so we can start capturing decisions.
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-[16px] text-[#7a8190]">
            <GoogleIcon />
            <span>Signed in as</span>
            <strong className="font-semibold text-[#25252b]">{email}</strong>
          </div>
        </section>

        <section aria-label="Workspace tools" className="mt-16 grid w-full gap-6 md:grid-cols-3">
          {tools.map((tool) => {
            const isConnected = connectedTools.has(tool.id)
            return (
              <article key={tool.id} className="flex min-h-[292px] flex-col rounded-[8px] border border-[#dfe1e8] bg-white p-6 shadow-[0_1px_2px_rgba(17,24,39,0.02)]">
                <div className="flex items-center gap-4">
                  <div className="flex h-[68px] w-[68px] shrink-0 items-center justify-center rounded-[10px] border border-[#bfc4cf] bg-white">
                    <img
                      src={tool.iconSrc}
                      alt=""
                      className="h-10 w-10 object-contain"
                    />
                  </div>
                  <div>
                    <h2 className="text-[20px] font-bold leading-tight">{tool.name}</h2>
                    <p className={`mt-1 text-[16px] ${isConnected ? 'font-medium text-[#16835d]' : 'text-[#a2a8b5]'}`}>
                      {isConnected ? 'Connected' : 'Not connected'}
                    </p>
                  </div>
                </div>

                <p className="mt-6 flex-1 text-[17px] leading-[1.55] text-[#737b8c]">{tool.description}</p>

                <button
                  type="button"
                  aria-pressed={isConnected}
                  onClick={() => toggleTool(tool.id)}
                  className={`mt-6 min-h-12 w-full rounded-full px-5 text-[17px] font-semibold text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4b38d1] ${
                    isConnected
                      ? 'bg-[#16835d] hover:bg-[#126e4f]'
                      : 'bg-[#4b38d1] hover:bg-[#3f2dbd]'
                  }`}
                >
                  {isConnected ? `${tool.name} Connected` : `Connect ${tool.name}`}
                </button>
              </article>
            )
          })}
        </section>

        <div className="mt-16 flex flex-col items-center pb-2">
          <button
            type="button"
            disabled={!canContinue}
            className="min-h-[62px] w-full min-w-0 rounded-full bg-[#4b38d1] px-10 text-[18px] font-semibold text-white transition-colors hover:bg-[#3f2dbd] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4b38d1] disabled:cursor-not-allowed disabled:bg-[#aaa7e7] sm:w-[410px]"
          >
            Connect A Tool to Continue
          </button>
          <p className="mt-4 text-center text-[14px] text-[#7a8190]">
            You can connect or disconnect tools anytime from{' '}
            <span className="font-medium text-[#4b38d1]">Settings</span>
          </p>
        </div>
      </div>
    </main>
  )
}
