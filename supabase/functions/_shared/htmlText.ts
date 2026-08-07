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

// Strips CSS that survives even when looksLikeHtml() finds no angle-bracket
// tags to trigger on - e.g. a legacy row whose stored body ended up being
// (or containing) the inside of a <style> block with the tags themselves
// already gone, leaving bare rule blocks and declarations. Confirmed live:
// one such row rendered as a lone "96" (a fragment of
// "<o:PixelsPerInch>96</o:PixelsPerInch>") with no HTML tags left to strip.
function stripCssRemnants(text: string): string {
  return text
    .replace(/[.#@]?[\w-]+\s*\{[^{}]*\}/g, " ") // rule blocks: .foo { ... }
    .replace(/[a-zA-Z-]+\s*:\s*[^;{}\n]+;/g, " ") // bare declarations: color: red;
    .replace(/\s{2,}/g, " ")
    .trim();
}

// A body counts as real prose only if it has several actual word-like
// tokens - catches style-property soup ("family Arial sans-serif") that a
// raw letter count would wrongly accept as "meaningful" text.
function isReadableProse(text: string): boolean {
  const words = text.split(/\s+/).filter((w) => /^[A-Za-z][A-Za-z'.,!?-]*$/.test(w) && w.length >= 2);
  return words.length >= 4;
}

// Defensive cleanup for any stored body that might still carry raw HTML/CSS
// (legacy rows ingested before the source-side fix, or any future gap in
// it) - so already-clean bodies pass through untouched, but nothing
// readable surviving falls back to a plain placeholder instead of
// rendering a near-empty wall of whitespace or a stray markup fragment.
export function cleanDisplayText(text: string): string {
  const htmlStripped = looksLikeHtml(text) ? htmlToPlainText(text) : text;
  const cleaned = stripCssRemnants(htmlStripped);
  return isReadableProse(cleaned) ? cleaned : "(no readable message content captured)";
}
