// supabase/functions/_shared/userLimits.ts
//
// Deno port of backend/src/modules/ratelimit/user_limits.py - the per-user
// weekly Claude prompt limit (250 prompts / 7-day rolling window) reviewed
// and merged in PR #14. That PR only wired it into the FastAPI backend,
// which Railway stopped serving back on 2026-08-11 (see api/index.ts's own
// header comment) - /search and /digest actually run through this edge
// function now, so this is what needs the check for it to do anything.
//
// public.user_limits has no tenant_id (limit_key is the caller's email) and
// is RLS-locked to the locus_app role only (021_user_prompt_limits.sql /
// 20260816000000_user_prompt_limits.sql) - withAdmin (postgres, RLS-bypass)
// reaches it regardless, same as the auth.users lookup below.

import { withAdmin } from "./db.ts";

const WEEKLY_PROMPT_LIMIT = 250;
const WINDOW_DAYS = 7;
const LIMIT_TYPE = "claude_weekly_prompts";

export type PromptLimitUsage = {
  promptCount: number;
  limit: number;
  windowEnd: Date;
};

export class PromptLimitExceededError extends Error {
  usage: PromptLimitUsage;
  constructor(usage: PromptLimitUsage) {
    super(`Weekly prompt limit exceeded (${usage.promptCount}/${usage.limit})`);
    this.name = "PromptLimitExceededError";
    this.usage = usage;
  }
}

async function getLimitKeyFromUserId(userId: string): Promise<string> {
  const email = await withAdmin(async (sql) => {
    const rows = await sql`SELECT email FROM auth.users WHERE id = ${userId}`;
    return rows[0]?.email as string | undefined;
  });
  if (!email) throw new Error(`User not found: ${userId}`);
  return email.toLowerCase();
}

/**
 * Atomic check-and-increment against public.user_limits (same FOR UPDATE
 * row lock as the Python original). Increments and returns normally when
 * the caller is within their rolling 7-day limit; throws
 * PromptLimitExceededError otherwise. Call this once per actual Claude
 * prompt - not per request - so cached reads (e.g. a digest served from
 * public.weekly_digests without calling Claude) don't count against it.
 */
export async function enforceUserPromptLimit(userId: string): Promise<void> {
  const limitKey = await getLimitKeyFromUserId(userId);

  await withAdmin(async (sql) => {
    await sql.begin(async (tx) => {
      const rows = await tx`
        SELECT window_start, prompt_count
        FROM public.user_limits
        WHERE limit_key = ${limitKey} AND limit_type = ${LIMIT_TYPE}
        FOR UPDATE
      `;
      const now = new Date();

      if (rows.length === 0) {
        await tx`
          INSERT INTO public.user_limits (limit_key, limit_type, window_start, prompt_count)
          VALUES (${limitKey}, ${LIMIT_TYPE}, ${now.toISOString()}, 1)
        `;
        return;
      }

      const windowStart = new Date(rows[0].window_start as string);
      const promptCount = Number(rows[0].prompt_count);
      const windowEnd = new Date(windowStart.getTime() + WINDOW_DAYS * 24 * 60 * 60 * 1000);

      if (now >= windowEnd) {
        await tx`
          UPDATE public.user_limits
          SET window_start = ${now.toISOString()}, prompt_count = 1
          WHERE limit_key = ${limitKey} AND limit_type = ${LIMIT_TYPE}
        `;
        return;
      }

      if (promptCount >= WEEKLY_PROMPT_LIMIT) {
        throw new PromptLimitExceededError({ promptCount, limit: WEEKLY_PROMPT_LIMIT, windowEnd });
      }

      await tx`
        UPDATE public.user_limits
        SET prompt_count = prompt_count + 1
        WHERE limit_key = ${limitKey} AND limit_type = ${LIMIT_TYPE}
      `;
    });
  });
}
