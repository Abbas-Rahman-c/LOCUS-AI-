// supabase/functions/_shared/htmlText.ts
//
// Was a private copy inside gmail-manual-sync/index.ts, used only when
// extracting the plain-text body to feed ai-worker. api/index.ts's
// extractEventText() - which reconstructs the "CONVERSATION" thread shown
// in Memory Explorer - reads the same stored envelope.raw_content.body but
// never ran it through this cleanup, so raw HTML captured before this fix
// existed (or any other row that ends up with markup in `body`) rendered
// verbatim in the UI instead of clean text. Shared here so both places stay
// in sync instead of drifting into two different HTML handling paths again.

// Lightweight tag-stripping, not a real HTML parser - good enough to turn a
// newsletter's markup into readable text without pulling in a DOM dependency
// inside a Deno edge function.
export function htmlToPlainText(html: string): string {
  return html
    .replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|tr|li|h[1-6])>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, "\"")
    .replace(/&#39;/gi, "'")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Cheap, conservative heuristic - real prose essentially never contains a
// doctype/html/head tag or more than a couple of angle-bracket tags, so
// false positives (treating real text as HTML) are effectively impossible;
// the failure mode to guard against is a false negative (missing real HTML),
// which is why the tag-count check has a low threshold.
export function looksLikeHtml(text: string): boolean {
  if (/<!doctype html|<html[\s>]|<head[\s>]|<body[\s>]/i.test(text)) return true;
  const tagMatches = text.match(/<\/?[a-z][a-z0-9]*(\s[^<>]*)?>/gi);
  return (tagMatches?.length ?? 0) >= 3;
}

// Defensive cleanup for any stored body that might still carry raw HTML
// (legacy rows ingested before the source-side fix, or any future gap in
// it) - runs htmlToPlainText only when the text actually looks like markup,
// so already-clean bodies pass through untouched. Falls back to a plain
// placeholder when nothing readable survives (e.g. a legacy row whose
// stored body was already reduced to a stray HTML fragment like "96" from
// a style attribute, with nothing left to recover), instead of rendering
// a near-empty wall of whitespace.
export function cleanDisplayText(text: string): string {
  const cleaned = looksLikeHtml(text) ? htmlToPlainText(text) : text.trim();
  const meaningful = cleaned.replace(/[^a-zA-Z]/g, "").length;
  return meaningful >= 5 ? cleaned : "(no readable message content captured)";
}
