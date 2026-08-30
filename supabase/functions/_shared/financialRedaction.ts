// supabase/functions/_shared/financialRedaction.ts
//
// Deterministic (regex-based, not AI-judgment-based) scrubbing of financial
// identifiers. Applied to every connector's raw_content in queue.ts before
// the event is enqueued, and again to extraction output in ai-worker before
// it's persisted to decisions - so a card/account/routing number can never
// reach raw_events or a permanent decision record intact, regardless of
// whether the triage LLM correctly classifies the surrounding message.
//
// This is a defense-in-depth heuristic, not a perfect PII detector: it is
// intentionally biased toward over-redacting (e.g. a long order/tracking
// number) rather than under-redacting, since the cost of losing an
// incidental long number is far lower than the cost of leaking a real
// financial identifier.

const CARD_NUMBER_RE = /\b(?:\d[ -]?){13,19}\b/g;
const IBAN_RE = /\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}\b/g;
const SSN_RE = /\b\d{3}-\d{2}-\d{4}\b/g;
// Catch-all: any standalone run of 9+ digits (routing numbers, bank account
// numbers, card numbers that failed the Luhn check due to a typo/OCR error,
// etc.) not already redacted above.
const LONG_DIGIT_RUN_RE = /\b\d{9,}\b/g;

// Real bug found live: Discord's structural mention syntax
// (<@123456789012345678>, <@!...> nickname form, <#...> channel, <@&...>
// role) embeds a genuine 17-19 digit snowflake ID - not a financial
// identifier, just platform protocol syntax, the same category as Slack's
// <@U12345> user-id syntax (which never matched LONG_DIGIT_RUN_RE to begin
// with, since Slack ids aren't pure digits). Left unprotected, every
// mention in a Discord message got mangled into "<@[REDACTED-NUMBER]>" -
// confirmed live, and combined with the "readable prose" length gate in
// htmlText.ts, it made otherwise-real short messages (a lone "Hi <@user>")
// disappear from the reconstructed conversation entirely. Protected here
// before the digit-run pass runs, then restored after - the surrounding
// redaction logic (real card/SSN/IBAN detection) is untouched.
const DISCORD_MENTION_RE = /<[@#](?:&|!)?\d{9,}>/g;

// Same bracket-glyph-sentinel convention as htmlText.ts's SOFT/HARD/BULLET
// markers: printable, but a shape real prose essentially never produces,
// so restoring it afterward can't accidentally eat or collide with a real
// standalone number already in the message (a plain " N " placeholder
// could).
const MENTION_PLACEHOLDER_RE = /⟦M(\d+)⟧/g;

function luhnValid(digits: string): boolean {
  let sum = 0;
  let alt = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let n = parseInt(digits[i], 10);
    if (alt) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    sum += n;
    alt = !alt;
  }
  return sum % 10 === 0;
}

export function redactFinancialInfo(input: string): string {
  if (!input) return input;

  const protectedMentions: string[] = [];
  let out = input.replace(DISCORD_MENTION_RE, (match) => {
    protectedMentions.push(match);
    return `⟦M${protectedMentions.length - 1}⟧`;
  });

  out = out.replace(CARD_NUMBER_RE, (match) => {
    const digits = match.replace(/[ -]/g, "");
    return digits.length >= 13 && digits.length <= 19 && luhnValid(digits)
      ? "[REDACTED-CARD]"
      : match;
  });

  out = out.replace(IBAN_RE, "[REDACTED-IBAN]");
  out = out.replace(SSN_RE, "[REDACTED-SSN]");
  out = out.replace(LONG_DIGIT_RUN_RE, "[REDACTED-NUMBER]");

  out = out.replace(MENTION_PLACEHOLDER_RE, (_full, i) => protectedMentions[Number(i)]);

  return out;
}

// Recursively redacts every string value in a JSON-like structure (objects,
// arrays, nested combinations) - raw_content shapes differ per connector
// (Gmail: flat string fields, Notion: a full nested page object), so this
// has to walk arbitrary structure rather than assume flat fields.
export function redactFinancialInfoDeep<T>(value: T): T {
  if (typeof value === "string") {
    return redactFinancialInfo(value) as unknown as T;
  }
  if (Array.isArray(value)) {
    return value.map((v) => redactFinancialInfoDeep(v)) as unknown as T;
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = redactFinancialInfoDeep(v);
    }
    return out as T;
  }
  return value;
}
