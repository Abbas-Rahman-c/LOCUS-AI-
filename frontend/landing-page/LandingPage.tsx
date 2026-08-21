import { useEffect } from 'react'
import GetStarted from './GetStarted'
import HowItWorks from './HowItWorks'
import WhyLocus from './WhyLocus'
import { EarlyAccessPopup } from './components/EarlyAccessPopup'

export default function LandingPage({
  initialSection,
}: {
  initialSection?: 'get-started' | 'how-it-works' | 'why-locus'
} = {}) {
  useEffect(() => {
    if (!initialSection) {
      // No specific section requested (plain load or refresh) - start at
      // the top rather than wherever the browser last left off.
      window.scrollTo(0, 0)
      return
    }
    const section = document.getElementById(initialSection)
    section?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [initialSection])

  return (
    <div className="w-full">
      <EarlyAccessPopup />
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
