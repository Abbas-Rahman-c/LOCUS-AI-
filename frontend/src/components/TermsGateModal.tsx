import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getSupabaseClient, isSupabaseConfigured } from '../lib/supabase'
import { DEMO_EMAIL_KEY, WORKSPACES_DONE_KEY } from '../lib/sessionKeys'
import { TermsSections, TERMS_VERSION } from '../lib/termsContent'

/**
 * Blocking dialog shown once, right after a real user's first sign-in -
 * before they reach /connect-workspaces or the dashboard, since that's the
 * point where we start reading their Slack/Gmail/Notion data. Gated on
 * user_metadata.terms_version (see useAuthEmail() in App.tsx) so it never
 * shows again for that account unless TERMS_VERSION changes. Styled to
 * match the confirmation dialogs already used in AccountSettings.tsx
 * (rounded-[8px] white card, icon badge, #4B3BD4 primary button) rather
 * than as a one-off design.
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4 py-8"
      role="presentation"
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-gate-title"
        className="flex max-h-[88vh] w-full max-w-[520px] flex-col rounded-[8px] bg-white shadow-[0_20px_55px_rgba(17,24,39,0.22)]"
      >
        <div className="shrink-0 px-8 pt-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#F0F8FF] text-[#4B3BD4]">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 3l7 3.2v5c0 4.6-3 8.9-7 10-4-1.1-7-5.4-7-10v-5L12 3z"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path
                d="M9.3 12.2l1.8 1.8 3.6-3.8"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h1 id="terms-gate-title" className="mt-5 text-[20px] font-semibold text-[#202027]">
            Before you continue
          </h1>
          <p className="mt-2 text-[14px] leading-6 text-[#7A8292]">
            Locus AI reads data from the tools you connect, so we need you to agree to our terms
            first. Here's the short version:
          </p>
        </div>

        <div className="mt-5 flex-1 overflow-y-auto px-8">
          <TermsSections compact />
          <Link
            to="/terms"
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-block text-[13px] font-medium text-[#4B3BD4] hover:underline"
          >
            Read the full Terms and Conditions ↗
          </Link>
        </div>

        <div className="mt-6 shrink-0 px-8 pb-8">
          {error && (
            <p role="alert" className="mb-3 text-[14px] text-[#B4232C]">
              {error}
            </p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={handleDecline}
              disabled={submitting}
              className="h-11 rounded-[7px] border border-[#DEE1E8] bg-white px-4 text-[15px] font-semibold text-[#4B3BD4] hover:bg-[#F8F7FF] disabled:opacity-50"
            >
              Decline &amp; log out
            </button>
            <button
              type="button"
              onClick={handleAccept}
              disabled={submitting}
              className="h-11 rounded-[7px] bg-[#4B3BD4] px-4 text-[15px] font-semibold text-white hover:bg-[#3F30BC] disabled:cursor-wait disabled:opacity-60"
            >
              {submitting ? 'Saving…' : 'I Agree, Continue'}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
