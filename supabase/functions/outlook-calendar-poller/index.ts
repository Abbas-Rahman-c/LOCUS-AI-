// supabase/functions/outlook-calendar-poller/index.ts
//
// Every run refreshes the access token first via _shared/microsoftAuth.ts,
// same reasoning as jira-poller: a poll cycle could outlast the ~1h token
// lifetime, so refresh-then-use beats "react to a 401 after the fact".
//
// GET /me/events with $filter=lastModifiedDateTime ge {cursor} - real,
// server-side incremental filtering (unlike Monday's client-side
// filtering), verified against Microsoft's own Graph docs before writing
// this. $orderby is deliberately NOT combined with this $filter - Graph
// has a documented quirk where $orderby often needs to match the
// $filter property exactly or the query fails outright, and this
// doesn't need a specific order: latestSeen is computed by scanning
// every returned event's lastModifiedDateTime, not by assuming the
// last array element is newest.
//
// Real, disclosed content-model note: a calendar event is logistics by
// nature (when/where/who), not a conversation - unlike every other
// connector here, there's no comment thread on an event, so real
// decision content can only ever come from the event's own body text
// (an organizer who actually wrote real content into the description).
// Lower expected extraction yield here is a property of what a calendar
// event fundamentally is, not a poller bug.
//
// source_id includes lastModifiedDateTime from the start, applying the
// same real lesson learned live on monday-poller and built into
// clickup-poller from day one: a rescheduled or re-described meeting is
// exactly the same "mutable item whose state changes over its lifetime"
// shape a task-tracker item is - capturing it once, on first sight,
// would silently miss every later edit. thread_ref stays event-scoped
// (not timestamped) so every snapshot of the same event groups into one
// conversation.
//
// permission_scope is the connecting user's own account id (email/UPN) -
// a personal calendar is inherently private to its owner, unlike a
// public Discord channel, so scoping to the owner (same convention
// gmail-manual-sync already uses for a personal inbox) is the right
// default here, not an empty/workspace-wide scope.

import { withAdmin, withTenant } from "../_shared/db.ts";
import { enqueueEvent, IngestionEnvelope } from "../_shared/queue.ts";
import { refreshMicrosoftAccess, type MicrosoftConnection } from "../_shared/microsoftAuth.ts";
import { cleanDisplayText } from "../_shared/htmlText.ts";

console.log("Outlook Calendar poller started!");

const GRAPH_API = "https://graph.microsoft.com/v1.0";
const MAX_EVENTS_PER_POLL = 50;

interface GraphAttendee {
  emailAddress?: { name?: string; address?: string };
}
interface GraphEvent {
  id: string;
  subject?: string;
  bodyPreview?: string;
  body?: { content?: string; contentType?: string };
  webLink?: string;
  lastModifiedDateTime?: string;
  organizer?: { emailAddress?: { name?: string; address?: string } };
  attendees?: GraphAttendee[];
}

function knownActorsFor(attendees: GraphAttendee[] | undefined): { name: string; source_actor_id: string }[] {
  const map = new Map<string, string>();
  for (const a of attendees ?? []) {
    const email = a.emailAddress?.address;
    const name = a.emailAddress?.name;
    if (email && name) map.set(email, name);
  }
  return Array.from(map, ([source_actor_id, name]) => ({ name, source_actor_id }));
}

Deno.serve(async (_req) => {
  const sources = await withAdmin(async (sql) => {
    return await sql`
      select *
      from public.source_connections
      where source = 'outlook_calendar'
        and status = 'active'
        and ingestion_mode = 'polling'
    `;
  });

  const results = [];

  for (const source of sources) {
    try {
      const refreshed = await refreshMicrosoftAccess(source as unknown as MicrosoftConnection);
      if (!refreshed) {
        results.push({ source_id: source.id, error: "token refresh failed" });
        continue;
      }
      const { accessToken } = refreshed;

      // Explicit .toISOString() regardless of whether postgres.js handed
      // back a Date object or a string for last_synced_at - a Date
      // object interpolated directly into the URL would stringify via
      // its own default (non-ISO) format, which Graph's OData $filter
      // doesn't accept.
      const lastSyncedAt = new Date(source.last_synced_at ? (source.last_synced_at as string) : 0).toISOString();

      const eventsUrl = new URL(`${GRAPH_API}/me/events`);
      eventsUrl.searchParams.set("$filter", `lastModifiedDateTime ge ${lastSyncedAt}`);
      eventsUrl.searchParams.set(
        "$select",
        "id,subject,bodyPreview,body,webLink,lastModifiedDateTime,organizer,attendees",
      );
      eventsUrl.searchParams.set("$top", String(MAX_EVENTS_PER_POLL));

      const response = await fetch(eventsUrl, {
        headers: { Authorization: `Bearer ${accessToken}`, Prefer: 'outlook.body-content-type="text"' },
      });
      if (!response.ok) {
        console.error(`Outlook Calendar API error for ${source.id}:`, await response.text());
        results.push({ source_id: source.id, error: `events fetch failed: ${response.status}` });
        continue;
      }

      const data = await response.json();
      const events: GraphEvent[] = data.value ?? [];

      let latestSeen = lastSyncedAt;
      for (const event of events) {
        const bodyText = cleanDisplayText(event.body?.content ?? event.bodyPreview ?? "");
        const organizerEmail = event.organizer?.emailAddress?.address;
        const organizerName = event.organizer?.emailAddress?.name;

        const envelope: IngestionEnvelope = {
          tenant_id: source.tenant_id,
          connection_id: source.id,
          source: "outlook_calendar",
          source_id: `event-${event.id}-${event.lastModifiedDateTime ?? ""}`,
          actor: organizerEmail || "unknown",
          actor_display_name: organizerName,
          thread_ref: `event-${event.id}`,
          permission_scope: source.external_workspace_id ? [String(source.external_workspace_id)] : [],
          known_actors: knownActorsFor(event.attendees),
          raw_content: {
            subject: event.subject ?? "",
            body: bodyText,
          },
          source_permalink: event.webLink,
          received_at: new Date().toISOString(),
        };
        await enqueueEvent(envelope);

        if (event.lastModifiedDateTime && event.lastModifiedDateTime > latestSeen) {
          latestSeen = event.lastModifiedDateTime;
        }
      }

      if (latestSeen !== lastSyncedAt) {
        await withTenant(String(source.tenant_id), async (sql) => {
          await sql`
            update public.source_connections
            set last_synced_at = ${latestSeen}
            where id = ${source.id}
          `;
        });
      }

      results.push({ source_id: source.id, events: events.length });
    } catch (err) {
      console.error(`Error polling Outlook Calendar source ${source.id}:`, err);
      results.push({ source_id: source.id, error: err instanceof Error ? err.message : String(err) });
    }
  }

  return new Response(JSON.stringify({ message: "Poll completed", results }), {
    headers: { "Content-Type": "application/json" },
  });
});
