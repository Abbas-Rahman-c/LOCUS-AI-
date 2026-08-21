/** Session keys shared across auth + onboarding screens. */
export const DEMO_EMAIL_KEY = 'locus:demo-email'
export const WORKSPACES_DONE_KEY = 'locus:workspaces-connected'

/**
 * localStorage (not sessionStorage - should survive a browser restart, same
 * as a real "seen" flag would) marking that the user has opened Team Pulse
 * at least once. TeamPulse sets it on mount and dispatches
 * TEAM_PULSE_SEEN_EVENT so DashboardNav's badge dot can clear immediately in
 * the same tab, without waiting for a 'storage' event (which only fires in
 * *other* tabs, never the one that made the change).
 */
export const TEAM_PULSE_SEEN_KEY = 'locus:team-pulse-seen'
export const TEAM_PULSE_SEEN_EVENT = 'locus:team-pulse-seen'

/** localStorage flag marking that a visitor has already seen (and
 * dismissed, or joined via) the early-access popup on the marketing site -
 * same "survive a browser restart" reasoning as TEAM_PULSE_SEEN_KEY, so it
 * only ever shows once per browser, not once per page load. */
export const EARLY_ACCESS_POPUP_SEEN_KEY = 'locus:early-access-popup-seen'
