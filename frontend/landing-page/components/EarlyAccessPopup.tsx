import { useEffect, useState } from 'react'
import { EARLY_ACCESS_WAITLIST_FORM_URL } from '../../src/lib/appUrl'
import { EARLY_ACCESS_POPUP_SEEN_KEY } from '../../src/lib/sessionKeys'

function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Close"
      className="absolute right-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    </button>
  )
}

/**
 * Shown once per browser, a couple seconds after a first-time visitor
 * lands on the marketing site - not on every page load, and not to
 * someone who already dismissed or joined it once. Same house style as
 * TermsAndConditionsModal (white rounded-2xl card, lime CTA) so the two
 * don't look like they belong to different products.
 */
export function EarlyAccessPopup() {
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    if (localStorage.getItem(EARLY_ACCESS_POPUP_SEEN_KEY)) return
    const timer = setTimeout(() => setIsOpen(true), 2500)
    return () => clearTimeout(timer)
  }, [])

  const dismiss = () => {
    localStorage.setItem(EARLY_ACCESS_POPUP_SEEN_KEY, '1')
    setIsOpen(false)
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="early-access-popup-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) dismiss()
      }}
    >
      <div className="relative w-full max-w-[420px] rounded-2xl bg-white p-8 text-center shadow-2xl">
        <CloseButton onClick={dismiss} />
        <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#5b52e8]">
          Now in early access
        </p>
        <h2 id="early-access-popup-title" className="mt-3 text-[22px] font-bold leading-tight text-[#18181b]">
          Locus AI is invite-only for now
        </h2>
        <p className="mt-3 text-[14px] leading-relaxed text-[#6b7280]">
          We're opening access to a small group first, so early feedback actually shapes the
          product. Join the waitlist and we'll let you know the moment a spot opens up.
        </p>
        <a
          href={EARLY_ACCESS_WAITLIST_FORM_URL}
          target="_blank"
          rel="noreferrer"
          onClick={dismiss}
          className="mt-6 block w-full rounded-full bg-[#aadf2e] px-6 py-3 text-[14px] font-semibold text-[#18181b] transition-opacity hover:opacity-90"
        >
          Join the Early Access Waitlist
        </a>
        <button
          type="button"
          onClick={dismiss}
          className="mt-3 text-[13px] font-medium text-[#6b7280] hover:text-[#18181b]"
        >
          Maybe later
        </button>
      </div>
    </div>
  )
}
