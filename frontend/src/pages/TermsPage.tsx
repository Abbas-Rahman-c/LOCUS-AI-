import { Link } from 'react-router-dom'
import { TermsDocument } from '../lib/termsContent'

/** Standalone, publicly accessible /terms page - linked from the marketing
 * pages and from the sign-in gate's "read the full terms" link. */
export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white px-6 py-14">
      <div className="mx-auto max-w-[720px]">
        <Link to="/" className="text-[13px] font-medium text-[#4B3BD4] hover:underline">
          ← Back to Locus AI
        </Link>
        <div className="mt-4">
          <TermsDocument />
        </div>
      </div>
    </main>
  )
}
