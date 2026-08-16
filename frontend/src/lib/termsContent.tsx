// Single source of truth for the Terms of Service text, shared by the
// standalone /terms page, the landing-page acceptance modal, and the
// post-sign-in gate so the three never drift out of sync.
//
// TERMS_VERSION is what actually gates access - see useAuthEmail() in
// App.tsx, which compares it against the signed-in user's
// user_metadata.terms_version. Bump this string (e.g. to a new date) any
// time the text below changes materially and existing users need to accept
// again; leave it alone for typo/formatting-only edits.
export const TERMS_VERSION = '1.0-2026-08-16'
export const TERMS_TITLE = 'LOCUS AI Terms of Service'
export const TERMS_VERSION_LABEL = 'Version 1.0 - Effective Date: August 15, 2026'
export const TERMS_LAST_UPDATED = 'August 15, 2026'
export const CONTACT_EMAIL = 'shubhamshrivastava@locusaiapp.com'

export type TermsSection = {
  title: string
  paragraphs: string[]
  bullets?: string[]
  closingParagraphs?: string[]
}

export const TERMS_INTRO: string[] = [
  'These Terms of Service (“Terms”) govern your access to and use of the LOCUS AI application, website, software, integrations, APIs, and related services (collectively, the “Service”) operated by LOCUS AI (“LOCUS AI,” “we,” “us,” or “our”).',
  'Please read these Terms carefully before using the Service.',
  'By creating an account, connecting an integration, accessing, or using LOCUS AI, you acknowledge that you have read, understood, and agree to be bound by these Terms.',
  'If you do not agree with these Terms, you may not access or use the Service.',
]

export const TERMS_SECTIONS: TermsSection[] = [
  {
    title: 'Eligibility',
    paragraphs: [
      'You must be at least 18 years old, or the age of legal majority in your jurisdiction, to use LOCUS AI.',
      'If you access or use the Service on behalf of a company, organization, or other legal entity, you represent that you have the authority to accept these Terms on its behalf.',
    ],
  },
  {
    title: 'User Accounts and Responsibilities',
    paragraphs: [
      'Certain features of LOCUS AI require you to create an account.',
      'You agree to provide accurate, complete, and current account information and to update that information when necessary.',
      'You are responsible for maintaining the confidentiality and security of your login credentials and for activity conducted through your account.',
      'You must promptly notify LOCUS AI if you become aware of unauthorized access to or use of your account.',
      'We may suspend or terminate accounts where we reasonably believe there has been unauthorized activity, fraud, misuse, or a violation of these Terms.',
    ],
  },
  {
    title: 'LOCUS AI Service',
    paragraphs: [
      'LOCUS AI provides an organizational memory and contextual intelligence platform designed to help users connect, organize, retrieve, and understand workplace information across supported applications and data sources.',
      'The Service may include organizational memory, contextual search, AI-generated summaries, structured memory, decision and action-item extraction, Memory Explorer, Team Pulse, AI-assisted contextual retrieval, source citations, links to original content, and third-party integrations.',
      'The Service is continually evolving. Features may be added, modified, limited, or discontinued as the platform develops.',
    ],
  },
  {
    title: 'Third-Party Integrations',
    paragraphs: [
      'LOCUS AI may allow users to connect supported third-party services, including Slack, Gmail, and Notion.',
      'By connecting a third-party service, you authorize LOCUS AI to access and process the information permitted through that integration to the extent necessary to provide the Service.',
      'Your use of third-party platforms remains subject to the applicable terms, privacy policies, permissions, and availability of those providers.',
      'LOCUS AI is not responsible for changes, interruptions, restrictions, failures, or discontinuation of third-party services or APIs.',
    ],
  },
  {
    title: 'Read-Only Access',
    paragraphs: [
      'Where supported, LOCUS AI integrations operate using read-only authorization permissions.',
      'LOCUS AI does not use these integrations to send emails, post messages, edit documents, or otherwise modify source content unless such functionality is introduced in the future and is clearly disclosed and authorized by the user.',
      'Users are responsible for reviewing the permissions requested when connecting an integration.',
    ],
  },
  {
    title: 'Customer and Workspace Data',
    paragraphs: [
      'You retain ownership of the data, documents, communications, and other information that you or your organization make available to LOCUS AI (“Customer Data”).',
      'You grant LOCUS AI a limited right to access, process, store, transform, and use Customer Data only as reasonably necessary to provide and operate the Service.',
      'This may include generating structured organizational memory, performing contextual retrieval, maintaining security, preventing abuse, troubleshooting technical issues, providing customer support, and improving the reliability of the Service.',
      'This permission does not transfer ownership of Customer Data to LOCUS AI.',
    ],
  },
  {
    title: 'Raw Message Retention',
    paragraphs: [
      'LOCUS AI is designed to minimize the retention of original workspace content.',
      'Raw message content processed by LOCUS AI may be retained for a maximum period of 30 days, after which it is deleted in accordance with our applicable data-retention processes.',
      'After the applicable retention period, LOCUS AI may retain structured or derived memory records necessary to provide the Service rather than retaining the complete original message thread.',
      'Structured records may include contextual summaries, decisions, action items, owners, relevant entities, dates, supporting references, and source metadata.',
      'Additional information regarding data retention and deletion may be provided in the LOCUS AI Privacy Policy.',
    ],
  },
  {
    title: 'No AI Model Training on Workspace Data',
    paragraphs: [
      'LOCUS AI does not use private Customer Data or workspace content to train general-purpose artificial intelligence or foundation models.',
      'Customer Data is processed only as necessary to provide the functionality requested by the user, subject to these Terms and the LOCUS AI Privacy Policy.',
    ],
  },
  {
    title: 'Sensitive Information Protection',
    paragraphs: [
      'LOCUS AI uses automated safeguards designed to identify and filter certain categories of sensitive information before structured memory records are stored.',
      'These safeguards may include detection of Social Security numbers, credit and debit card numbers, bank account numbers, routing numbers, international bank account numbers, and other selected financial identifiers.',
      'Automated detection systems cannot guarantee the identification of every sensitive data element.',
      'Users should avoid intentionally submitting highly sensitive information unless it is necessary for an authorized use of the Service.',
    ],
  },
  {
    title: 'Data Security',
    paragraphs: [
      'LOCUS AI uses reasonable administrative, technical, and organizational safeguards designed to protect information processed through the Service.',
      'However, no internet-based service, software platform, or electronic storage system can guarantee absolute security.',
      'Users and organizations remain responsible for maintaining appropriate security practices relating to account access, permissions, devices, credentials, and connected third-party services.',
    ],
  },
  {
    title: 'Acceptable Use',
    paragraphs: [
      'You may not use LOCUS AI to violate applicable laws or regulations, access information without authorization, infringe intellectual property or privacy rights, distribute malicious software, compromise the security of the Service, circumvent authentication or authorization controls, conduct unauthorized security testing, scrape or exploit the Service in an unauthorized manner, or facilitate fraudulent, deceptive, abusive, or unlawful activity.',
      'You may not provide or process another person’s or organization’s data through LOCUS AI unless you have appropriate authorization to do so.',
      'We may investigate suspected violations and restrict or suspend access where reasonably necessary to protect LOCUS AI, our users, third parties, or the integrity of the Service.',
    ],
  },
  {
    title: 'Artificial Intelligence Features',
    paragraphs: [
      'LOCUS AI uses artificial intelligence, machine learning, retrieval systems, and large language models to provide certain features.',
      'AI-generated summaries, extracted context, classifications, recommendations, and other outputs may occasionally be incomplete, inaccurate, outdated, or incorrect.',
      'Users should independently verify important information before relying on AI-generated outputs for significant business, financial, legal, regulatory, employment, healthcare, security, or operational decisions.',
      'LOCUS AI does not guarantee that AI-generated outputs will always be accurate, complete, or suitable for a particular purpose.',
    ],
  },
  {
    title: 'Intellectual Property',
    paragraphs: [
      'The LOCUS AI Service, including its software, interfaces, features, workflows, branding, design, documentation, architecture, trademarks, logos, and original content, is owned by LOCUS AI or its licensors and is protected by applicable intellectual property laws.',
      'Except for the limited right to access and use the Service under these Terms, no intellectual property rights are transferred to you.',
      'You may not reproduce, distribute, sell, license, copy, modify, or create derivative works from proprietary LOCUS AI materials except where expressly authorized by LOCUS AI or permitted by applicable law.',
    ],
  },
  {
    title: 'Feedback',
    paragraphs: [
      'If you provide suggestions, recommendations, ideas, or product feedback regarding LOCUS AI, you permit us to use that feedback to develop, improve, and operate the Service.',
      'Providing feedback does not transfer ownership of your Customer Data to LOCUS AI.',
    ],
  },
  {
    title: 'Service Availability',
    paragraphs: [
      'We aim to provide a reliable Service but do not guarantee uninterrupted, continuous, or error-free availability.',
      'The Service may occasionally be unavailable due to maintenance, infrastructure issues, security events, third-party interruptions, API restrictions, system upgrades, or circumstances outside our reasonable control.',
      'LOCUS AI may modify, suspend, or discontinue portions of the Service when reasonably necessary.',
    ],
  },
  {
    title: 'Beta and Early Access Features',
    paragraphs: [
      'Certain LOCUS AI features may be offered as beta, preview, pilot, experimental, or early access functionality.',
      'These features may contain errors or limitations, change without notice, become temporarily unavailable, operate differently from future production versions, or be discontinued.',
      'Unless otherwise stated, beta and early access features are provided primarily for evaluation, testing, and feedback.',
    ],
  },
  {
    title: 'Pilot & Early Access Program',
    paragraphs: [
      'LOCUS AI may provide selected users with temporary access to the Service as part of a limited pilot, beta, or early-access program.',
      'For the current pilot:',
    ],
    bullets: [
      'Access is provided free of charge.',
      'Participation is limited to selected early-access users.',
      'Each pilot user receives access for 7 days, unless otherwise communicated.',
      'Each user may submit up to 250 prompts during the pilot period.',
      'Unused prompts expire at the end of the pilot period and have no monetary value.',
      'Pilot access is provided for product evaluation, testing, and feedback purposes.',
      'LOCUS AI may modify, restrict, pause, or discontinue pilot functionality during the evaluation period where reasonably necessary.',
      'Certain features may be experimental, incomplete, or subject to change before commercial release.',
      'Participation in the pilot does not guarantee continued, free, or future access to LOCUS AI.',
      'Any future paid plans, pricing, usage limits, or commercial terms will be communicated separately and will not apply retroactively to the free pilot.',
    ],
    closingParagraphs: [
      'Users are encouraged to provide feedback regarding functionality, usability, reliability, and potential improvements. LOCUS AI may use such feedback to improve and develop the Service in accordance with these Terms.',
      'Nothing in the pilot program transfers ownership of a user’s or organization’s Customer Data to LOCUS AI.',
    ],
  },
  {
    title: 'Suspension and Termination',
    paragraphs: [
      'You may stop using LOCUS AI at any time.',
      'LOCUS AI may suspend or terminate your access if you materially breach these Terms, create a security or legal risk, engage in fraudulent or abusive activity, or if suspension or termination is required by law.',
      'We may also restrict access where continued use could materially harm LOCUS AI, our infrastructure, other users, or third parties.',
      'Where reasonably practicable, we may provide notice before suspension or termination.',
      'Upon termination, your right to access and use the Service will cease.',
      'Provisions that by their nature should survive termination, including intellectual property protections, disclaimers, limitations of liability, and applicable legal obligations, will continue to apply.',
    ],
  },
  {
    title: 'Disconnecting Integrations and Data Deletion',
    paragraphs: [
      'Users may disconnect supported integrations through available account or integration controls.',
      'When an integration is disconnected, LOCUS AI will stop obtaining new information from that integration unless it is subsequently reauthorized.',
      'Requests relating to account deletion or stored data may be submitted through available account controls or by contacting LOCUS AI.',
      'Certain information may be retained for limited periods where reasonably necessary for security, fraud prevention, legal compliance, dispute resolution, backup, or recovery purposes, subject to applicable law and the LOCUS AI Privacy Policy.',
    ],
  },
  {
    title: 'Disclaimer of Warranties',
    paragraphs: [
      'To the maximum extent permitted by applicable law, the Service is provided “as is” and “as available.”',
      'LOCUS AI makes no express or implied warranty regarding uninterrupted availability, error-free operation, the accuracy or completeness of AI-generated outputs, fitness for a particular purpose, merchantability, non-infringement, or compatibility with every third-party platform or service.',
      'Your use of LOCUS AI is at your own risk.',
    ],
  },
  {
    title: 'Limitation of Liability',
    paragraphs: [
      'To the maximum extent permitted by applicable law, LOCUS AI and its founders, officers, directors, employees, contractors, affiliates, agents, licensors, and service providers will not be liable for any indirect, incidental, consequential, special, exemplary, or punitive damages arising from or relating to your use of the Service.',
      'This includes damages resulting from loss of profits, revenue, business opportunities, goodwill, data, service availability, unauthorized access, reliance on AI-generated information, or inability to access or use the Service.',
      'Nothing in these Terms excludes or limits liability that cannot legally be excluded or limited under applicable law.',
    ],
  },
  {
    title: 'Indemnification',
    paragraphs: [
      'To the extent permitted by applicable law, you agree to indemnify and hold harmless LOCUS AI and its affiliates, officers, directors, employees, contractors, and agents from claims, liabilities, damages, losses, and reasonable expenses arising from your unlawful use of the Service, material violation of these Terms, infringement of third-party rights, or submission of data that you were not authorized to provide or process.',
    ],
  },
  {
    title: 'Privacy',
    paragraphs: [
      'Your use of LOCUS AI is also subject to the LOCUS AI Privacy Policy, which describes how information is collected, processed, retained, protected, and deleted.',
      'Additional data-processing terms may be provided to enterprise customers where applicable.',
    ],
  },
  {
    title: 'Changes to These Terms',
    paragraphs: [
      'LOCUS AI may update these Terms from time to time to reflect changes to the Service, applicable laws, security requirements, business practices, or third-party integrations.',
      'If material changes are made, we will take reasonable steps to notify users before the updated Terms take effect where appropriate.',
      'The “Last Updated” date at the beginning of these Terms indicates the most recent revision.',
      'Your continued use of the Service after revised Terms become effective constitutes acceptance of the revised Terms.',
    ],
  },
  {
    title: 'Severability',
    paragraphs: [
      'If any provision of these Terms is found to be unlawful, invalid, or unenforceable, that provision will be modified or interpreted to the minimum extent necessary, and the remaining provisions will continue in full force and effect.',
    ],
  },
  {
    title: 'Entire Agreement',
    paragraphs: [
      'These Terms, together with the LOCUS AI Privacy Policy and any other agreements expressly incorporated by reference, constitute the agreement between you and LOCUS AI regarding your use of the Service.',
      'For enterprise customers, a separately executed agreement, Master Services Agreement, Data Processing Agreement, or similar contract may supersede specific provisions of these Terms.',
    ],
  },
  {
    title: 'Contact Us',
    paragraphs: [
      `If you have questions about these Terms, privacy practices, data handling, or the LOCUS AI Service, please contact Locus AI email at ${CONTACT_EMAIL}`,
    ],
  },
]

function TermsParagraph({ text, className }: { text: string; className: string }) {
  const emailIndex = text.indexOf(CONTACT_EMAIL)
  if (emailIndex === -1) {
    return <p className={className}>{text}</p>
  }

  return (
    <p className={className}>
      {text.slice(0, emailIndex)}
      <a href={`mailto:${CONTACT_EMAIL}`} className="font-medium text-[#4B3BD4] hover:underline">
        {CONTACT_EMAIL}
      </a>
      {text.slice(emailIndex + CONTACT_EMAIL.length)}
    </p>
  )
}

/** Shared Terms of Service document used by /terms, the landing-page modal,
 * and the sign-in gate so the legal copy never has to be kept in sync by hand. */
export function TermsDocument({
  compact = false,
  showTitle = true,
  headingId,
}: {
  compact?: boolean
  showTitle?: boolean
  headingId?: string
}) {
  const bodyClass = compact
    ? 'text-[13px] leading-6 text-[#7A8292]'
    : 'text-[14px] leading-7 text-[#7A8292]'
  const headingClass = compact
    ? 'text-[13px] font-semibold text-[#202027]'
    : 'text-[15px] font-semibold text-[#202027]'

  return (
    <div className={compact ? 'space-y-4' : 'space-y-5'}>
      {showTitle && (
        <div className="text-center">
          <h1 id={headingId} className={compact ? 'text-[18px] font-bold text-[#202027]' : 'text-[26px] font-bold text-[#202027]'}>
            {TERMS_TITLE}
          </h1>
          <p className="mt-1 text-[13px] text-[#7A8292]">({TERMS_VERSION_LABEL})</p>
        </div>
      )}
      {TERMS_INTRO.map((paragraph) => (
        <TermsParagraph key={paragraph} text={paragraph} className={bodyClass} />
      ))}
      {TERMS_SECTIONS.map((section, index) => (
        <section key={section.title} className={compact ? 'space-y-2' : 'space-y-2.5'}>
          <h2 className={headingClass}>
            {index + 1}. {section.title}
          </h2>
          {section.paragraphs.map((paragraph) => (
            <TermsParagraph key={paragraph} text={paragraph} className={bodyClass} />
          ))}
          {section.bullets && section.bullets.length > 0 && (
            <ul className={compact ? 'ml-5 list-disc space-y-1' : 'ml-5 list-disc space-y-1.5'}>
              {section.bullets.map((bullet) => (
                <li key={bullet} className={bodyClass}>
                  {bullet}
                </li>
              ))}
            </ul>
          )}
          {section.closingParagraphs?.map((paragraph) => (
            <TermsParagraph key={paragraph} text={paragraph} className={bodyClass} />
          ))}
        </section>
      ))}
    </div>
  )
}
