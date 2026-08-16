import { Link } from 'react-router-dom'
import { TERMS_LAST_UPDATED, TermsSections } from '../lib/termsContent'

/** Standalone, publicly accessible /terms page - linked from the marketing
 * pages and from the sign-in gate's "read the full terms" link. */
export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white px-6 py-14">
      <div className="mx-auto max-w-[600px]">
        <Link to="/" className="text-[13px] font-medium text-[#4B3BD4] hover:underline">
          ← Back to Locus AI
        </Link>
        <h1 className="mt-4 text-[26px] font-bold text-[#202027]">Terms and Conditions</h1>
        <p className="mt-1 text-[13px] text-[#7A8292]">Last updated {TERMS_LAST_UPDATED}</p>
        <p className="mt-4 text-[14px] leading-6 text-[#7A8292]">
          By using Locus AI, you agree to these terms. The short version of each section is
          below - if anything's unclear, reach out and we'll walk through it.
        </p>
        <div className="mt-8 border-t border-[#E0E2E8] pt-6">
          <TermsSections />
        </div>
      </div>
    </main>
  )
}
