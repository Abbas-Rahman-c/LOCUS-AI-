import GetStarted from './GetStarted'
import HowItWorks from './HowItWorks'
import WhyLocus from './WhyLocus'

export default function LandingPage({
  onAuthenticated,
}: {
  onAuthenticated: (email: string) => void
}) {
  return (
    <div className="w-full">
      <section id="get-started" aria-label="Get started">
        <GetStarted onAuthenticated={onAuthenticated} />
      </section>
      <section id="how-it-works" aria-label="How it works">
        <HowItWorks />
      </section>
      <section id="why-locus" aria-label="Why Locus">
        <WhyLocus />
      </section>
    </div>
  )
}
