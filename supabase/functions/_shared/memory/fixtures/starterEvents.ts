// supabase/functions/_shared/memory/fixtures/starterEvents.ts
//
// Hand-written NormalizedEvent[] fixtures (spec Section 2's assumed
// upstream input contract) for Checkpoint A - deliberately spans ≥2
// source types (slack, gmail) so the "memory created from at least two
// NormalizedEvent source types" acceptance criterion has a fixture set
// backing it independent of whatever the real historical replay finds.

import type { NormalizedEvent } from "../historicalReplay.ts";

export const STARTER_EVENTS: Omit<NormalizedEvent, "tenant_id">[] = [
  {
    source: "slack",
    source_id: "fixture-slack-001",
    actor: { id: "", display_name: "Priya Sharma" },
    thread_ref: "fixture-thread-launch",
    permission_scope: [],
    raw_content: "Decided: we're launching the public beta on September 1st. Going with the phased rollout plan Priya proposed instead of the big-bang launch, since it lets us catch issues with a smaller group first.",
    occurred_at: "2026-08-01T14:00:00.000Z",
  },
  {
    source: "gmail",
    source_id: "fixture-gmail-001",
    actor: { id: "", display_name: "Marcus Chen" },
    thread_ref: null,
    permission_scope: [],
    raw_content: "Subject: Re: Launch timeline\nActually we need to push the public launch to September 15th, not September 1st. QA found a blocking issue in the onboarding flow that needs another week to fix properly.",
    occurred_at: "2026-08-10T09:30:00.000Z",
  },
  {
    source: "slack",
    source_id: "fixture-slack-002",
    actor: { id: "", display_name: "Priya Sharma" },
    thread_ref: "fixture-thread-beta",
    permission_scope: [],
    raw_content: "Just to be clear, the beta program itself is still starting September 10th regardless of the public launch date - that's a separate, smaller audience.",
    occurred_at: "2026-08-11T11:00:00.000Z",
  },
  {
    source: "slack",
    source_id: "fixture-slack-003",
    actor: { id: "", display_name: "Marcus Chen" },
    thread_ref: "fixture-thread-commitment",
    permission_scope: [],
    raw_content: "I'll get the onboarding-flow QA fix shipped by August 20th. That's the blocker for the public launch date.",
    occurred_at: "2026-08-12T16:00:00.000Z",
  },
  {
    source: "gmail",
    source_id: "fixture-gmail-002",
    actor: { id: "", display_name: "Jordan Lee" },
    thread_ref: null,
    permission_scope: [],
    raw_content: "Subject: Onboarding flow blocker\nThe onboarding flow is currently blocking new signups from completing account setup - anyone who hits the workspace-invite step gets a blank screen. This needs to be fixed before we can launch anything publicly.",
    occurred_at: "2026-08-05T08:15:00.000Z",
  },
  {
    source: "slack",
    source_id: "fixture-slack-004",
    actor: { id: "", display_name: "Jordan Lee" },
    thread_ref: "fixture-thread-commitment",
    permission_scope: [],
    raw_content: "Fixed - the onboarding blank-screen bug is resolved, deployed to staging this morning.",
    occurred_at: "2026-08-19T10:00:00.000Z",
  },
];
