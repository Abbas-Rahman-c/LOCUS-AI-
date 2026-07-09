import React from "react";
import logoSrc from "../assets/locuslogo.png";
/**
 * GetStarted — Locus AI landing/signup split-screen page
 *
 * Left panel: dark promotional panel with headline, value props, and a
 *             preview of the Dashboard.
 * Right panel: white signup panel with Google OAuth CTA and the
 *              3-step "how it works" indicator.
 *
 * Notes:
 * - Swap the placeholder hex values below for the exact tokens from
 *   Figma Dev Mode (Inspect panel) once you have them.
 * - handleGoogleSignUp() is stubbed — wire it to your actual OAuth flow
 *   (e.g. Firebase Auth, Auth0, or your own /auth/google endpoint).
 * - Route to /onboarding/connect-workspaces after a successful sign-up,
 *   based on the next screen in the Figma flow.
 */

interface GetStartedProps {
  onGoogleSignUp?: () => void;
}

const LocusLogo: React.FC<{ variant?: "light" | "dark" }> = ({ variant = "dark" }) => (
  <div className="flex items-center gap-2">
    <img src={logoSrc} alt="Locus AI" className="h-8 w-8 rounded-lg" />
    <span className={`text-lg font-bold ${variant === "light" ? "text-white" : "text-gray-900"}`}>
      LOCUS <span className="text-indigo-500">AI</span>
    </span>
  </div>
);

const GoogleIcon: React.FC = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5">
    <path
      fill="#4285F4"
      d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47c-.28 1.5-1.13 2.77-2.4 3.62v3h3.88c2.27-2.09 3.57-5.17 3.57-8.81z"
    />
    <path
      fill="#34A853"
      d="M12 24c3.24 0 5.96-1.07 7.95-2.92l-3.88-3c-1.08.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.26v3.09C3.24 21.3 7.28 24 12 24z"
    />
    <path
      fill="#FBBC05"
      d="M5.27 14.27a7.2 7.2 0 0 1 0-4.54V6.64H1.26a12 12 0 0 0 0 10.72l4.01-3.09z"
    />
    <path
      fill="#EA4335"
      d="M12 4.77c1.76 0 3.34.6 4.58 1.79l3.44-3.44C17.95 1.19 15.24 0 12 0 7.28 0 3.24 2.7 1.26 6.64l4.01 3.09C6.22 6.88 8.87 4.77 12 4.77z"
    />
  </svg>
);

interface StepProps {
  index: number;
  title: string;
  subtitle: string;
  isLast?: boolean;
}

const Step: React.FC<StepProps> = ({ index, title, subtitle, isLast }) => (
  <div className="relative flex flex-1 flex-col items-center text-center">
    {!isLast && (
      <div className="absolute left-1/2 top-3 h-px w-full bg-gray-300" />
    )}
    <div className="relative z-10 flex h-6 w-6 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
      {index}
    </div>
    <div className="mt-3">
      <p className="text-sm font-semibold text-gray-900">{title}</p>
      <p className="mt-1 text-xs text-gray-500">{subtitle}</p>
    </div>
  </div>
);
const DashboardPreview: React.FC = () => (
  <div className="overflow-hidden rounded-xl border border-white/10 bg-white shadow-2xl">
    <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
      <LocusLogo />
      <div className="hidden gap-4 text-xs text-gray-400 sm:flex">
        <span>How it works</span>
        <span className="font-medium text-indigo-600">Dashboard</span>
        <span>Decision Log</span>
        <span>Pulse</span>
      </div>
    </div>
    <div className="p-4">
      <p className="text-sm font-semibold text-gray-900">Good morning, Jun</p>
      <div className="mt-3 rounded-lg border border-gray-200 px-3 py-2 text-xs text-gray-400">
        Ask about a decision, blocker, or thread...
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {["Decisions", "Action Items", "Blockers"].map((label) => (
          <div key={label} className="rounded-lg border border-gray-100 p-3">
            <p className="text-[10px] uppercase tracking-wide text-gray-400">{label}</p>
            <p className="mt-1 text-xl font-bold text-gray-900">7</p>
          </div>
        ))}
      </div>
    </div>
  </div>
);

const GetStarted: React.FC<GetStartedProps> = ({ onGoogleSignUp }) => {
  const handleGoogleSignUp = () => {
    if (onGoogleSignUp) {
      onGoogleSignUp();
      return;
    }
    // TODO: replace with real OAuth trigger
    console.log("Sign up with Google clicked");
  };

  return (
    <div className="flex min-h-screen w-full flex-col md:flex-row">
      {/* Left: promotional panel */}
      <div className="flex w-full flex-col justify-center bg-gray-950 px-10 py-16 md:w-1/2 md:px-16">
        <h1 className="text-4xl font-extrabold leading-tight text-white sm:text-5xl">
          Run your projects like you{" "}
          <span className="text-lime-400">remember everything.</span>
        </h1>

        <ul className="mt-8 space-y-3">
          {[
            "Ask anything about your project history.",
            "Automatically captures decisions.",
            "A weekly digest of everything that mattered.",
          ].map((item) => (
            <li key={item} className="flex items-start gap-3 text-gray-200">
              <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs">
                ✓
              </span>
              {item}
            </li>
          ))}
        </ul>

        <div className="mt-12 hidden md:block">
          <DashboardPreview />
        </div>
      </div>

      {/* Right: signup panel */}
      <div className="flex w-full flex-col items-center justify-center bg-white px-8 py-16 md:w-1/2">
        <LocusLogo />

        <div className="mt-16 max-w-sm text-center">
          <h2 className="text-3xl font-bold text-gray-900">Get started now.</h2>
          <p className="mt-2 text-sm text-gray-500">
            Start your 14 days free trial. Cancel anytime.
          </p>

          <button
            type="button"
            onClick={handleGoogleSignUp}
            className="mt-10 flex w-full items-center justify-center gap-3 rounded-full bg-lime-400 px-6 py-3 font-semibold text-gray-900 transition hover:bg-lime-300 focus:outline-none focus:ring-2 focus:ring-lime-500 focus:ring-offset-2"
          >
            <GoogleIcon />
            Sign up with Google
          </button>

          <p className="mt-4 text-xs text-gray-400">
            By clicking sign up, you agree to our terms of service and privacy policy.
          </p>

          <div className="mt-16 flex items-start gap-2">
            <Step index={1} title="Connect Tools" subtitle="Slack, Notion, Gmail" />
            <Step index={2} title="Locus captures decisions" subtitle="Runs quietly in the background" />
            <Step index={3} title="Search with citations" subtitle="Answers with links to sources" isLast />
          </div>
        </div>
      </div>
    </div>
  );
};

export default GetStarted;
