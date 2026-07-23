import { useEffect } from 'react'
import GetStarted from './GetStarted'
import HowItWorks from './HowItWorks'
import WhyLocus from './WhyLocus'

export default function LandingPage({
  onAuthenticated,
  initialSection,
}: {
  onAuthenticated: (email: string) => void
  initialSection?: 'get-started' | 'how-it-works' | 'why-locus'
}) {
  useEffect(() => {
    if (!initialSection) return
    const section = document.getElementById(initialSection)
    section?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [initialSection])

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
