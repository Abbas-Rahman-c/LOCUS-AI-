import GetStarted from './GetStarted'
import HowItWorks from './HowItWorks'
import WhyLocus from './WhyLocus'

export default function LandingPage() {
  return (
    <div className="w-full">
      <section id="get-started" aria-label="Get started">
        <GetStarted />
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
