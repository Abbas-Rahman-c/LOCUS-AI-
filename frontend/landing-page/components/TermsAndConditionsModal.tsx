import { TermsDocument } from '../../src/lib/termsContent'

interface TermsAndConditionsModalProps {
  isOpen: boolean
  onClose: () => void
  onAgree: () => void
}

function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Close"
      className="absolute right-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M4 4l8 8M12 4l-8 8"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    </button>
  )
}

export function TermsAndConditionsModal({
  isOpen,
  onClose,
  onAgree,
}: TermsAndConditionsModalProps) {
  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="terms-title"
    >
      <div className="relative mx-4 flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        <CloseButton onClick={onClose} />
        <div className="overflow-y-auto p-8 pt-12">
          <TermsDocument compact headingId="terms-title" />

          <div className="mt-8 flex justify-center gap-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-gray-300 bg-white px-8 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              DECLINE
            </button>
            <button
              type="button"
              onClick={onAgree}
              className="rounded-full bg-[#aadf2e] px-8 py-2.5 text-sm font-medium text-[#18181b] transition-colors hover:opacity-90"
            >
              I AGREE
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
