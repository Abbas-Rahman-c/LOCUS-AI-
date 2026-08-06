// supabase/functions/loci-chat/index.ts
//
// Backend for "Loci" (pronounced "Loki"), the support/FAQ chat widget for
// tsenta.com. Deliberately hosted in the Locus AI Supabase project to reuse
// its already-paid-for Pro-plan compute rather than pay for a second
// project - Tsenta is otherwise unrelated to Locus AI, which is why its
// tables (loci_*) carry no tenant_id and are not part of the Locus AI RLS
// model. Reuses the same ANTHROPIC_API_KEY secret already configured in
// this project, so it draws from the same Anthropic billing/usage limit as
// the rest of Locus AI.
//
// Public-facing and reachable by anyone on the internet - unlike the
// internal Gmail/Slack/Notion pipeline, which only ever processes data from
// connectors the tenant controls. Rate limiting here is not optional.

import { withAdmin } from "../_shared/db.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const MODEL = Deno.env.get("ANTHROPIC_LOCI_MODEL") ?? "claude-haiku-4-5-20251001";

// ── Rate limits ────────────────────────────────────────────────────────
// Two independent windows: per-session (a real visitor having a real
// conversation) and per-IP (catches someone cycling session ids to get
// around the session limit). Both are deliberately generous enough for a
// real conversation but nowhere near what a script hammering the endpoint
// would need.
const SESSION_LIMIT = 30; // messages
const SESSION_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const IP_LIMIT = 60; // messages
const IP_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const MAX_MESSAGE_CHARS = 2000; // guards against someone pasting a novel to inflate token cost per call

// deno-lint-ignore no-explicit-any
async function ensureSchema(sql: any) {
  await sql`
    CREATE TABLE IF NOT EXISTS public.loci_conversations (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      session_id text NOT NULL,
      role text NOT NULL CHECK (role IN ('user', 'assistant')),
      content text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    )
  `;
  await sql`
    CREATE INDEX IF NOT EXISTS loci_conversations_session_idx
      ON public.loci_conversations (session_id, created_at)
  `;
  await sql`
    CREATE TABLE IF NOT EXISTS public.loci_rate_limits (
      key text PRIMARY KEY,
      window_start timestamptz NOT NULL DEFAULT now(),
      request_count int NOT NULL DEFAULT 0
    )
  `;
}

// Fixed-window check-and-increment. Returns true if the request is allowed.
// deno-lint-ignore no-explicit-any
async function checkRateLimit(sql: any, key: string, limit: number, windowMs: number): Promise<boolean> {
  const rows = await sql`SELECT window_start, request_count FROM public.loci_rate_limits WHERE key = ${key}`;
  const now = Date.now();

  if (rows.length === 0) {
    await sql`INSERT INTO public.loci_rate_limits (key, window_start, request_count) VALUES (${key}, now(), 1)`;
    return true;
  }

  const windowStart = new Date(rows[0].window_start as string).getTime();
  const count = rows[0].request_count as number;

  if (now - windowStart > windowMs) {
    // Window elapsed - reset.
    await sql`UPDATE public.loci_rate_limits SET window_start = now(), request_count = 1 WHERE key = ${key}`;
    return true;
  }

  if (count >= limit) return false;

  await sql`UPDATE public.loci_rate_limits SET request_count = request_count + 1 WHERE key = ${key}`;
  return true;
}

// ── System prompt, built from tsenta.com's own real content ─────────────
// Explicitly told what it does NOT know (anything account-specific) so it
// never invents an application status, a receipt, or a reply it has no
// access to - this is the FAQ/product/signup guide, not a logged-in
// account assistant. That would need real Tsenta API access, which does
// not exist yet.
const SYSTEM_PROMPT = `You are Loci (pronounced "Loki"), the support and product assistant on tsenta.com's chat widget. You help visitors understand Tsenta and get started - you do not have access to any individual user's account, applications, or data.

## What Tsenta is

Tsenta is an AI agent, backed by Y Combinator, that auto-applies to jobs for you. It watches 50,000+ company career pages across Workday, Greenhouse, Lever, Ashby, and 15+ other ATSes (application tracking systems). The moment a role goes live that fits a user's resume and preferences, Tsenta submits a tailored application - often before the posting shows up on LinkedIn or elsewhere.

## The four-stage pipeline

1. FIND - Tsenta watches career pages directly. When a matching role appears, the user is typically the first or among the very first applicants, well ahead of applicants going through job boards.
2. PREP - For each role, Tsenta reads the job description, identifies the keywords/skills being screened for, and rewrites the user's resume and cover letter to align - using only true facts from the resume the user uploaded, never invented experience. Every change is shown to the user before anything is sent.
3. APPLY - Tsenta opens the actual application form on the company's ATS and fills it out: every field, open-ended questions answered in the user's voice, resume/cover letter uploaded, and submits. The user can watch it happen or let it run in the background.
4. TRACK - Recruiter emails and replies are automatically routed to the right application, so status updates (viewed, replied, interview) happen without the user checking their inbox manually.

## Where Tsenta works

Web dashboard, iMessage (Tsenta texts about a match, user replies yes, it applies), a Chrome extension (auto-fills any job posting form), and an MCP server / CLI for agent tools like Claude Code - "apply to the new Stripe role" as a natural-language command.

## Pricing (monthly; quarterly and annual billing also available)

- Starter: $19/month, 600 applications per 30-day cycle
- Pro (most popular): $39/month, 1,500 applications per 30-day cycle
- Power: $99/month, 4,500 applications per 30-day cycle
- All tiers are the full product - they differ only in application volume.
- Free tier: the first 25 applications are free, no card required, full product access.
- Cancel any time, one click.

## Frequently asked questions

- How does Tsenta find jobs? It watches 50,000+ company career pages directly, so new roles show up within seconds of going live. There's also a curated daily list, and users can paste any job URL to add it manually.
- How do I know it applied correctly? Every submitted application gets a receipt: exact fields filled, answers to open-ended questions, the resume/cover letter that went out, and confirmation from the ATS. Users can review and flag anything for next time.
- Will recruiters know I used Tsenta? No - applications go through the same standard forms a manual applicant uses, with no automated flag.
- How does resume tailoring work? It reads the job description, aligns keywords/skills, and rewrites using only facts already present in the uploaded resume.
- Does Tsenta help with OPT/visa sponsorship situations? Yes - set work authorization status once (OPT, STEM-OPT, H-1B, citizen, etc.) and Tsenta filters out non-sponsoring roles and answers work-authorization questions correctly on every application. Sponsorship signals are surfaced where known, but Tsenta doesn't guarantee a company's sponsorship policy.
- Is there a free plan? Yes, the first 25 applications, no card required.

## How to behave

- Be direct and concise - most answers should be a few sentences, not an essay.
- You have NO access to any specific user's account, application history, tracker status, résumé, or messages. If asked something account-specific ("why hasn't my application to X been submitted", "what's my match score for Y"), say plainly that you can't see account details from this chat, and point them to their dashboard or founders@tsenta.com for anything account-specific.
- Never invent a fact about Tsenta that isn't in this prompt - this applies even when a plausible-sounding answer would be easy to infer. If something isn't explicitly stated above (geographic coverage, language support, specific integrations, timelines, guarantees, anything not written out in this prompt), say you don't have that specific information rather than reasoning your way to a guess, and point to founders@tsenta.com. A confident-sounding wrong answer is worse than "I don't know, but here's who can tell you."
- If someone seems ready to sign up, point them at the free tier (25 applications, no card required) as the natural next step.`;

function buildCorsResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "content-type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return buildCorsResponse(405, { error: "Method not allowed" });
  }

  let body: { session_id?: string; message?: string };
  try {
    body = await req.json();
  } catch {
    return buildCorsResponse(400, { error: "Invalid JSON body" });
  }

  const sessionId = (body.session_id ?? "").trim();
  const message = (body.message ?? "").trim();
  if (!sessionId || !message) {
    return buildCorsResponse(400, { error: "session_id and message are required" });
  }
  if (message.length > MAX_MESSAGE_CHARS) {
    return buildCorsResponse(400, { error: `message too long (max ${MAX_MESSAGE_CHARS} characters)` });
  }

  // Cloudflare/most proxies set this; falls back to the direct connection
  // info Deno exposes if not present (e.g. local testing).
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || req.headers.get("cf-connecting-ip")
    || "unknown";

  try {
    const result = await withAdmin(async (sql) => {
      await ensureSchema(sql);

      const sessionOk = await checkRateLimit(sql, `session:${sessionId}`, SESSION_LIMIT, SESSION_WINDOW_MS);
      if (!sessionOk) return { rateLimited: "session" as const };

      const ipOk = await checkRateLimit(sql, `ip:${ip}`, IP_LIMIT, IP_WINDOW_MS);
      if (!ipOk) return { rateLimited: "ip" as const };

      // Last 10 turns of real history for this session - enough for a
      // coherent conversation without unboundedly growing the prompt.
      const history = await sql`
        SELECT role, content FROM public.loci_conversations
        WHERE session_id = ${sessionId}
        ORDER BY created_at DESC LIMIT 10
      `;
      const messages = (history as unknown as { role: string; content: string }[])
        .reverse()
        .map((m) => ({ role: m.role, content: m.content }));
      messages.push({ role: "user", content: message });

      const resp = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: MODEL,
          max_tokens: 400,
          temperature: 0.3,
          system: [{ type: "text", text: SYSTEM_PROMPT, cache_control: { type: "ephemeral" } }],
          messages,
        }),
      });

      if (!resp.ok) {
        const errText = await resp.text();
        return { error: `Anthropic API error ${resp.status}: ${errText}` };
      }

      const data = await resp.json();
      const textBlock = (data.content ?? []).find((b: { type?: string }) => b.type === "text");
      const replyText = textBlock?.text ?? "Sorry, I couldn't generate a response - try again in a moment.";

      await sql`INSERT INTO public.loci_conversations (session_id, role, content) VALUES (${sessionId}, 'user', ${message})`;
      await sql`INSERT INTO public.loci_conversations (session_id, role, content) VALUES (${sessionId}, 'assistant', ${replyText})`;

      return { reply: replyText };
    });

    if (result.rateLimited) {
      return buildCorsResponse(429, {
        error: result.rateLimited === "session"
          ? "You've sent a lot of messages - give it a bit and try again."
          : "Too many requests from this network - give it a bit and try again.",
      });
    }
    if (result.error) {
      console.error("loci-chat: Anthropic call failed:", result.error);
      return buildCorsResponse(502, { error: "Something went wrong generating a response. Try again shortly." });
    }
    return buildCorsResponse(200, { reply: result.reply });
  } catch (err) {
    console.error("loci-chat: unexpected error:", err);
    return buildCorsResponse(500, { error: "Unexpected server error." });
  }
});
