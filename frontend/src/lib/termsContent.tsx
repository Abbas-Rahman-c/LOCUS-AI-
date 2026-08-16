// Single source of truth for the Terms and Conditions text, shared by the
// standalone /terms page and the post-sign-in acceptance gate (App.tsx) so
// the two never drift out of sync.
//
// TERMS_VERSION is what actually gates access - see useAuthEmail() in
// App.tsx, which compares it against the signed-in user's
// user_metadata.terms_version. Bump this string (e.g. to a new date) any
// time the text below changes materially and existing users need to accept
// again; leave it alone for typo/formatting-only edits.
export const TERMS_VERSION = '2026-08-15'
export const TERMS_LAST_UPDATED = 'August 15, 2026'
export const SUPPORT_EMAIL = 'support@locusaiapp.com'

export type TermsSection = { title: string; points: string[] }

// Kept to one line per point on purpose - this is what both the /terms page
// and the sign-in gate render, and a wall of legal prose is what the gate
// was getting pushback on.
export const TERMS_SECTIONS: TermsSection[] = [
  {
    title: 'Accounts',
    points: [
      'Keep your account info accurate, complete, and current.',
      "You're responsible for your password and anything that happens under it.",
    ],
  },
  {
    title: 'Data access and use',
    points: [
      'We only read Slack, Gmail, and Notion data from sources you choose to connect - disconnect anytime in Settings.',
      'Raw content is kept for 30 days, processed in our US-West region, with financial identifiers auto-redacted.',
    ],
  },
  {
    title: 'Intellectual property',
    points: ['The App and its content are our property, protected by copyright and trademark law.'],
  },
  {
    title: 'Termination',
    points: ['We may suspend or terminate access at any time, for any reason, without notice.'],
  },
  {
    title: 'Limitation of liability',
    points: [
      "We aren't liable for indirect, incidental, or consequential damages from using (or being unable to use) the App.",
    ],
  },
  {
    title: 'Changes',
    points: [
      "We may update these Terms at any time. We'll try to give at least 30 days' notice before material changes take effect.",
    ],
  },
]

/** Rendered as its own row (not a TermsSection bullet) so the email can be
 * a real mailto: link. */
export function ContactRow() {
  return (
    <p className="text-[14px] leading-6 text-[#7A8292]">
      Questions about these Terms? Email{' '}
      <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-[#4B3BD4] hover:underline">
        {SUPPORT_EMAIL}
      </a>
      .
    </p>
  )
}

/** Shared list of numbered sections, each a short heading + one-line
 * bullets - used by both the standalone /terms page and the sign-in gate
 * so the copy never has to be kept in sync by hand. */
export function TermsSections({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? 'space-y-4' : 'space-y-5'}>
      {TERMS_SECTIONS.map((section, index) => (
        <div key={section.title}>
          <h3 className="text-[14px] font-semibold text-[#202027]">
            {index + 1}. {section.title}
          </h3>
          <ul className="mt-1.5 space-y-1">
            {section.points.map((point) => (
              <li
                key={point}
                className="flex gap-2 text-[14px] leading-6 text-[#7A8292]"
              >
                <span className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-[#B7BCC8]" aria-hidden="true" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <ContactRow />
    </div>
  )
}
