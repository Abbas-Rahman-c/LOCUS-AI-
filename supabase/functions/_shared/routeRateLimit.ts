// supabase/functions/_shared/routeRateLimit.ts
//
// Deno port of backend/src/modules/ratelimit/limiter.py - the per-tenant
// "expensive route" guard (20 requests / 5 min per tenant+route) that
// exists because of a real incident: a shared Anthropic account hit its
// monthly cap from testing volume stacking up with no application-level
// guard in place to catch it early.
//
// The Python version is deliberately in-memory (a module-level dict) -
// its own header comment calls this out as a real, accepted tradeoff for
// a single long-lived process. An Edge Function has no such guarantee:
// Supabase can run multiple isolates concurrently and recycle them between
// requests, so a module-level Map here would silently under-count (or
// lose state entirely) rather than actually limiting anything. Backed by
// public.user_limits instead - the same table the per-user weekly prompt
// limiter uses (its own migration comment already documents limit_key as
// deliberately generic: "email, user_id, organization_id, or other
// identifier"), keyed here by tenant_id + route name so the counter is
// real, shared, and atomic regardless of which isolate handles a request.

import { withAdmin } from "./db.ts";

const MAX_REQUESTS = 20;
const WINDOW_SECONDS = 300;
const LIMIT_TYPE_PREFIX = "expensive_route:";

export class RouteRateLimitExceededError extends Error {
  retryAfterSeconds: number;
  constructor(retryAfterSeconds: number) {
    super(`Rate limit exceeded for this endpoint. Try again in ${retryAfterSeconds} seconds.`);
    this.name = "RouteRateLimitExceededError";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/**
 * Atomic check-and-increment against public.user_limits, keyed by
 * (tenant_id, route). Fixed window, same reset-on-expiry shape as the
 * Python RateLimiter.check(): allows MAX_REQUESTS per tenant per route
 * per WINDOW_SECONDS. Throws RouteRateLimitExceededError when exceeded;
 * otherwise increments and returns normally.
 */
export async function enforceRouteRateLimit(tenantId: string, routeName: string): Promise<void> {
  const limitType = `${LIMIT_TYPE_PREFIX}${routeName}`;

  await withAdmin(async (sql) => {
    await sql.begin(async (tx) => {
      const rows = await tx`
        SELECT window_start, prompt_count
        FROM public.user_limits
        WHERE limit_key = ${tenantId} AND limit_type = ${limitType}
        FOR UPDATE
      `;
      const now = new Date();

      if (rows.length === 0) {
        await tx`
          INSERT INTO public.user_limits (limit_key, limit_type, window_start, prompt_count)
          VALUES (${tenantId}, ${limitType}, ${now.toISOString()}, 1)
        `;
        return;
      }

      const windowStart = new Date(rows[0].window_start as string);
      const count = Number(rows[0].prompt_count);
      const elapsedSeconds = (now.getTime() - windowStart.getTime()) / 1000;

      if (elapsedSeconds >= WINDOW_SECONDS) {
        await tx`
          UPDATE public.user_limits
          SET window_start = ${now.toISOString()}, prompt_count = 1
          WHERE limit_key = ${tenantId} AND limit_type = ${limitType}
        `;
        return;
      }

      if (count >= MAX_REQUESTS) {
        const retryAfterSeconds = Math.max(1, Math.round(WINDOW_SECONDS - elapsedSeconds));
        throw new RouteRateLimitExceededError(retryAfterSeconds);
      }

      await tx`
        UPDATE public.user_limits
        SET prompt_count = prompt_count + 1
        WHERE limit_key = ${tenantId} AND limit_type = ${limitType}
      `;
    });
  });
}
