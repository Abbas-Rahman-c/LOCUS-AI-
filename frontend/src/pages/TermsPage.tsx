import { Link } from 'react-router-dom'
import { TermsBody } from '../lib/termsContent'

/** Standalone, publicly accessible /terms page - linked from the marketing
 * pages and reused as the reading material inside the post-sign-in
 * acceptance gate (see TermsGateModal). */
export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white px-6 py-12">
      <div className="mx-auto max-w-[680px]">
        <Link to="/" className="text-[13px] font-medium text-[#4B3BD4] hover:underline">
          ← Back to Locus AI
        </Link>
        <h1 className="mt-4 text-[24px] font-bold text-[#111827]">Terms and Conditions</h1>
        <div className="mt-6">
          <TermsBody />
        </div>
      </div>
    </main>
  )
}
