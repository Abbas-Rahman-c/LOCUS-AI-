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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 first:mt-0">
      <h2 className="text-[15px] font-semibold text-[#111827]">{title}</h2>
      <div className="mt-2 space-y-2 text-[14px] leading-relaxed text-[#4B5563]">{children}</div>
    </section>
  )
}

/** Renders the terms body only - no page chrome, so it can be dropped into
 * both a full page (TermsPage) and a scrollable modal (TermsGateModal). */
export function TermsBody() {
  return (
    <div>
      <p className="text-[14px] text-[#6B7280]">Last Updated: {TERMS_LAST_UPDATED}</p>
      <p className="mt-4 text-[14px] leading-relaxed text-[#4B5563]">
        Please read these Terms and Conditions carefully before using the Locus AI application
        (&quot;App&quot;) owned and operated by us.
      </p>
      <p className="mt-2 text-[14px] leading-relaxed text-[#4B5563]">
        Your access to and use of the App is conditioned on your acceptance of and compliance
        with these Terms. These Terms apply to all visitors, users, and others who access or use
        the App.
      </p>
      <p className="mt-2 text-[14px] leading-relaxed text-[#4B5563]">
        By accessing or using the App, you agree to be bound by these Terms. If you disagree with
        any part of the terms, then you may not access the App.
      </p>

      <Section title="1. Accounts">
        <p>
          When you create an account with us, you must provide information that is accurate,
          complete, and current at all times. Failure to do so constitutes a breach of the Terms,
          which may result in immediate termination of your account on our App.
        </p>
        <p>
          You are responsible for safeguarding the password that you use to access the App and
          for any activities or actions under your password.
        </p>
      </Section>

      <Section title="2. Data Access and Use">
        <p>
          Locus AI connects to workspace tools you choose to link - currently Slack, Gmail, and
          Notion - to read messages, threads, and documents and extract decisions, action items,
          and blockers into a searchable memory layer. You control which sources are connected
          and can disconnect them at any time from Settings.
        </p>
        <p>
          Raw content pulled from connected sources is retained for a limited window (currently
          30 days) and processed in our US-West infrastructure region. Where content contains
          financial identifiers (e.g. card or account numbers), we apply automated redaction
          before it is stored or summarized. This section describes current practice and does
          not limit our Privacy Policy, which governs data handling in full.
        </p>
      </Section>

      <Section title="3. Intellectual Property">
        <p>
          The App and its original content, features, and functionality are and will remain the
          exclusive property of the company and its licensors. The App is protected by copyright,
          trademark, and other laws of both your home country and foreign countries.
        </p>
      </Section>

      <Section title="4. Termination">
        <p>
          We may terminate or suspend your access immediately, without prior notice or liability,
          for any reason whatsoever, including without limitation if you breach the Terms.
        </p>
        <p>Upon termination, your right to use the App will immediately cease.</p>
      </Section>

      <Section title="5. Limitation of Liability">
        <p>
          In no event shall the company, nor its directors, employees, partners, agents,
          suppliers, or affiliates, be liable for any indirect, incidental, special,
          consequential, or punitive damages, including without limitation, loss of profits,
          data, use, goodwill, or other intangible losses, resulting from your access to or use
          of or inability to access or use the App.
        </p>
      </Section>

      <Section title="6. Changes">
        <p>
          We reserve the right, at our sole discretion, to modify or replace these Terms at any
          time. If a revision is material, we will try to provide at least 30 days&apos; notice
          prior to any new terms taking effect. What constitutes a material change will be
          determined at our sole discretion.
        </p>
      </Section>

      <Section title="7. Contact Us">
        <p>
          If you have any questions about these Terms, please contact us at{' '}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-[#4B3BD4] underline">
            {SUPPORT_EMAIL}
          </a>
          .
        </p>
      </Section>
    </div>
  )
}
