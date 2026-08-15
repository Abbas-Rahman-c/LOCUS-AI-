import { useState } from 'react'
import { getSupabaseClient, isSupabaseConfigured } from '../lib/supabase'
import { DEMO_EMAIL_KEY, WORKSPACES_DONE_KEY } from '../lib/sessionKeys'
import { TermsBody, TERMS_VERSION } from '../lib/termsContent'

/**
 * Blocking modal shown once, right after a real user's first sign-in -
 * before they reach /connect-workspaces or the dashboard, since that's the
 * point where we start reading their Slack/Gmail/Notion data. Gated on
 * user_metadata.terms_version (see useAuthEmail() in App.tsx) so it never
 * shows again for that account unless TERMS_VERSION changes.
 */
export function TermsGateModal({ onAccepted }: { onAccepted: () => void }) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAccept = async () => {
    setSubmitting(true)
    setError(null)
    try {
      if (isSupabaseConfigured()) {
        const { error: updateError } = await getSupabaseClient().auth.updateUser({
          data: { terms_version: TERMS_VERSION, terms_accepted_at: new Date().toISOString() },
        })
        if (updateError) throw updateError
      }
      onAccepted()
    } catch {
      setError("Couldn't save your acceptance - please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  const handleDecline = () => {
    sessionStorage.removeItem(DEMO_EMAIL_KEY)
    sessionStorage.removeItem(WORKSPACES_DONE_KEY)
    if (isSupabaseConfigured()) {
      void getSupabaseClient().auth.signOut()
    }
    window.location.href = '/'
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-8">
      <div className="flex max-h-[85vh] w-full max-w-[560px] flex-col rounded-[12px] bg-white shadow-xl">
        <div className="border-b border-[#E5E7EB] px-6 py-5">
          <h1 className="text-[18px] font-bold text-[#111827]">Terms and Conditions</h1>
          <p className="mt-1 text-[13px] text-[#6B7280]">
            Since Locus AI reads data from the tools you connect, we need you to review and
            accept these terms before continuing.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <TermsBody />
        </div>

        <div className="border-t border-[#E5E7EB] px-6 py-4">
          {error && <p className="mb-3 text-[13px] text-[#DC2626]">{error}</p>}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={handleDecline}
              disabled={submitting}
              className="h-10 rounded-[8px] border border-[#DEE1E8] bg-white px-5 text-[14px] font-medium text-[#374151] hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Decline &amp; log out
            </button>
            <button
              type="button"
              onClick={handleAccept}
              disabled={submitting}
              className="h-10 rounded-[8px] bg-[#4B3BD4] px-5 text-[14px] font-semibold text-white hover:bg-[#3F30BC] disabled:cursor-wait disabled:opacity-70"
            >
              {submitting ? 'Saving…' : 'I Agree, Continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
