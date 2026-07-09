import { Header } from './components/Header'
import { GoogleIcon } from './components/GoogleIcon'
import { ProcessStepper } from './components/ProcessStepper'
import { DashboardPreview } from './components/DashboardPreview'

export function SignUpPage() {
  return (
    <div className="relative mx-auto min-h-screen w-full max-w-[1024px] bg-white">
      <Header />

      <main className="flex min-h-[calc(100vh-64px)] px-10 pb-6">
        <section className="flex w-[44%] shrink-0 flex-col pt-4">
          <h1 className="text-[40px] font-bold leading-[1.15] tracking-[-0.025em] text-[#111827]">
            Never lose a{' '}
            <span className="text-[#5b52e8]">team decision</span>
            {' '}again.
          </h1>

          <p className="mt-4 max-w-[390px] text-[14.5px] leading-[1.65] text-[#6b7280]">
            Locus automatically captures decisions from your Slack and Notion
            workspaces so you can find them in seconds—with links back to the
            original messages.
          </p>

          <button
            type="button"
            className="mt-6 flex w-fit items-center gap-2.5 rounded-full bg-[#c8e619] px-5 py-3 text-[14.5px] font-semibold text-[#111827] transition-opacity hover:opacity-90"
          >
            <GoogleIcon />
            Sign up with Google
          </button>

          <p className="mt-2.5 max-w-[370px] text-[12.5px] leading-[1.55] text-[#9ca3af]">
            We&apos;ll connect Slack and Notion next so Locus can start
            capturing decisions.
          </p>

          <ProcessStepper />
        </section>

        <DashboardPreview />
      </main>
    </div>
  )
}
