// supabase/functions/discord-poller/index.ts
//
// Different shape from every other poller here in two real ways:
//
// 1. One global DISCORD_BOT_TOKEN (see discord-oauth/index.ts's header
//    comment for why), not a per-connection decrypted token - no refresh
//    logic needed at all, bot tokens don't expire.
// 2. Discord's own pagination is message-ID (snowflake) based, not
//    timestamp-based - there's no "updated since X" the way Jira/
//    Confluence/Notion have. cursor_state tracks the last-seen message id
//    PER CHANNEL (channel_cursors: {channelId: messageId}), and each
//    channel is paged with `after=<that id>` - first poll for a channel
//    has no cursor yet, bounded to the most recent 50 messages rather
//    than pulling a channel's entire history.
//
// permission_scope is deliberately left empty (workspace-wide visible,
// same convention as an unscoped decision already gets) rather than
// per-channel - Discord channel ids are numeric snowflakes, which
// isUnmappedScope's existing SLACK_CHANNEL_RE pattern doesn't recognize,
// and there's no Discord membership-sync equivalent to isMemoryAccessible
// built yet. Scoping per-channel with no real membership backing it would
// risk making every Discord-sourced decision invisible to everyone
// (falls through past isUnmappedScope, then needs a real permissionScopes
// match nobody has) - a real, disclosed simplification for v1, not an
// oversight.

import { withAdmin, withTenant } from "../_shared/db.ts";
import { enqueueEvent, IngestionEnvelope } from "../_shared/queue.ts";

console.log("Discord poller started!");

const BOT_TOKEN = Deno.env.get("DISCORD_BOT_TOKEN");
const MAX_MESSAGES_PER_CHANNEL = 50;
// Discord channel type 0 = GUILD_TEXT. Threads/announcements/voice/
// category channels are skipped for v1 - real content, but a real second
// pass, not folded in here.
const GUILD_TEXT_CHANNEL_TYPE = 0;

interface DiscordChannel {
  id: string;
  type: number;
  name?: string;
}

interface DiscordMessage {
  id: string;
  content: string;
  author: { id: string; username: string; global_name?: string | null; bot?: boolean };
  timestamp: string;
}

Deno.serve(async (_req) => {
  if (!BOT_TOKEN) {
    return new Response(JSON.stringify({ message: "DISCORD_BOT_TOKEN not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const sources = await withAdmin(async (sql) => {
    return await sql`
      select *
      from public.source_connections
      where source = 'discord'
        and status = 'active'
        and ingestion_mode = 'polling'
    `;
  });

  const results = [];

  for (const source of sources) {
    try {
      const guildId = source.external_workspace_id as string;
      const channelsResp = await fetch(`https://discord.com/api/v10/guilds/${guildId}/channels`, {
        headers: { Authorization: `Bot ${BOT_TOKEN}` },
      });
      if (!channelsResp.ok) {
        const bodyText = await channelsResp.text();
        console.error(`Discord channels fetch failed for ${source.id}:`, bodyText);
        results.push({ source_id: source.id, error: `channels failed: ${channelsResp.status} ${bodyText}` });
        continue;
      }
      const channels: DiscordChannel[] = await channelsResp.json();
      const textChannels = channels.filter((c) => c.type === GUILD_TEXT_CHANNEL_TYPE);

      const channelCursors: Record<string, string> = source.cursor_state?.channel_cursors ?? {};
      let totalMessages = 0;

      for (const channel of textChannels) {
        const afterId = channelCursors[channel.id];
        const messagesUrl = new URL(`https://discord.com/api/v10/channels/${channel.id}/messages`);
        messagesUrl.searchParams.set("limit", String(MAX_MESSAGES_PER_CHANNEL));
        if (afterId) messagesUrl.searchParams.set("after", afterId);

        const messagesResp = await fetch(messagesUrl, {
          headers: { Authorization: `Bot ${BOT_TOKEN}` },
        });
        if (!messagesResp.ok) {
          // A single channel the bot can't see (permissions not granted
          // for that specific channel, despite the guild-level invite)
          // shouldn't abort the whole connection's poll - log and move
          // on to the next channel.
          console.error(`Discord messages fetch failed for channel ${channel.id}:`, await messagesResp.text());
          continue;
        }
        // Discord returns newest-first; oldest-first is what every other
        // poller here already assumes when advancing a cursor to "the
        // last item processed".
        const messages: DiscordMessage[] = (await messagesResp.json()).reverse();
        if (messages.length === 0) continue;

        for (const message of messages) {
          if (message.author.bot) continue; // never ingest our own/other bots' messages
          if (!message.content.trim()) continue; // embed-only/attachment-only messages have nothing to extract

          const envelope: IngestionEnvelope = {
            tenant_id: source.tenant_id,
            connection_id: source.id,
            source: "discord",
            source_id: message.id,
            actor: message.author.id,
            actor_display_name: message.author.global_name || message.author.username,
            thread_ref: channel.id,
            permission_scope: [],
            raw_content: {
              subject: channel.name ? `#${channel.name}` : "",
              body: message.content,
            },
            source_permalink: `https://discord.com/channels/${guildId}/${channel.id}/${message.id}`,
            received_at: new Date().toISOString(),
          };
          await enqueueEvent(envelope);
          totalMessages++;
        }

        channelCursors[channel.id] = messages[messages.length - 1].id;
      }

      await withTenant(String(source.tenant_id), async (sql) => {
        await sql`
          update public.source_connections
          set cursor_state = ${sql.json({ ...source.cursor_state, channel_cursors: channelCursors })},
              last_synced_at = now()
          where id = ${source.id}
        `;
      });

      results.push({ source_id: source.id, channels_polled: textChannels.length, new_messages: totalMessages });
    } catch (err) {
      console.error(`Error polling Discord source ${source.id}:`, err);
      results.push({ source_id: source.id, error: err instanceof Error ? err.message : String(err) });
    }
  }

  return new Response(JSON.stringify({ message: "Poll completed", results }), {
    headers: { "Content-Type": "application/json" },
  });
});
