interface TermsAndConditionsModalProps {
  isOpen: boolean
  onClose: () => void
  onAgree: () => void
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
      <div className="mx-4 max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-8 shadow-2xl">
        <h2
          id="terms-title"
          className="mb-6 text-2xl font-bold text-gray-900"
        >
          Terms and Conditions
        </h2>

        <div className="space-y-4 text-sm text-gray-700">
          <p>
            Please read these Terms and Conditions carefully before using the Locus AI application (App) owned and operated by us.
          </p>
          <p>
            Your access to and use of the App is conditioned on your acceptance of and compliance with these Terms. These Terms apply to all visitors, users, and others who access or use the App.
          </p>
          <p>
            By accessing or using the App, you agree to be bound by these Terms. If you disagree with any part of the terms, then you may not access the App.
          </p>

          <h3 className="mt-6 text-base font-semibold text-gray-900">
            User Accounts & Responsibilities
          </h3>
          <p>
            When you create an account and use the App, you must provide information that is accurate, complete, and current at all times. Failure to do so constitutes a breach of the Terms, which may result in immediate termination of your account.
          </p>
          <p>
            You are responsible for safeguarding the credentials that you use to access the App and for any activities or actions conducted under your account.
          </p>

          <h3 className="mt-6 text-base font-semibold text-gray-900">
            Intellectual Property
          </h3>
          <p>
            The App and its original content, features, and functionality are and will remain the exclusive property of the company and its licensors. The App is protected by copyright, trademark, and other applicable laws.
          </p>

          <h3 className="mt-6 text-base font-semibold text-gray-900">
            Termination
          </h3>
          <p>
            We may terminate or suspend your access immediately, without prior notice or liability, for any reason whatsoever, including without limitation if you breach the Terms. Upon termination, your right to use the App will immediately cease.
          </p>

          <h3 className="mt-6 text-base font-semibold text-gray-900">
            Limitation of Liability
          </h3>
          <p>
            In no event shall the company, nor its directors, employees, partners, agents, suppliers, or affiliates, be liable for any indirect, incidental, special, consequential, or punitive damages, including without limitation, loss of profits, data, use, goodwill, or other intangible losses, resulting from your access to or use of or inability to access or use the App.
          </p>

          <h3 className="mt-6 text-base font-semibold text-gray-900">
            Data Privacy
          </h3>
          <p>
            As the operator and owner of Locus AI, we are committed to protecting your privacy and workspace data through the following standards:
          </p>
          <ul className="ml-6 list-disc space-y-2">
            <li>
              <strong>Raw Message Retention:</strong> Raw messages are retained for a maximum of 30 days. Locus AI reads messages to build structured memory and permanently deletes the raw content within 30 days. Only the extracted context summary is stored, never the full message thread. Raw messages are strictly deleted within 30 days of ingestion.
            </li>
            <li>
              <strong>Read-Only Access:</strong> All integrations operate on a read-only OAuth basis. Locus AI never writes, posts, or modifies data in Slack, Notion, or Gmail.
            </li>
            <li>
              <strong>No AI Training on Workspace Data:</strong> We never train AI models on your workspace data or personal content.
            </li>
            <li>
              <strong>Sensitive Information Filtering:</strong> Sensitive and private information is automatically filtered out. The app scans and filters financial identifiers before processing and again before saving any decisions, including dashed social security numbers, credit/debit cards, international bank account numbers, routing and account numbers, etc.
            </li>
          </ul>

          <h3 className="mt-6 text-base font-semibold text-gray-900">
            Changes
          </h3>
          <p>
            We reserve the right, at our sole discretion, to modify or replace these Terms at any time. If a revision is material, we will try to provide notice prior to any new terms taking effect. What constitutes a material change will be determined at our sole discretion.
          </p>

          <p className="mt-6">
            If you have any questions about these Terms, please contact us at{' '}
            <a
              href="mailto:shubhamshrivastava@locusaiapp.com"
              className="text-blue-600 underline"
            >
              shubhamshrivastava@locusaiapp.com
            </a>{' '}
            or use the chat assistance in the App for more information.
          </p>

          <p className="mt-4 text-xs text-gray-500">
            Last Updated: August 15, 2026
          </p>
        </div>

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
  )
}
