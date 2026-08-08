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
//
// <li>/<h1-6> get real structure, not just a line break: list items were
// closing-tag-only (</li> -> \n), so a real bulleted list read as a run of
// unmarked lines with nothing to show they were ever a list; headings had
// no separation from the paragraph before them. Opening tags now add a
// bullet marker / blank-line break of their own, so the plain-text result
// still reads like the list/heading it was instead of flattened prose.
export function htmlToPlainText(html: string): string {
  return html
    .replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    // Block-starting tags open on a fresh paragraph; <li> only needs its own
    // line, not a full paragraph break, and gets no closing-tag newline of
    // its own - back-to-back bullets would otherwise end up with a blank
    // line between every single item instead of reading as one tight list.
    .replace(/<(p|div|h[1-6])[^>]*>/gi, "\n\n")
    .replace(/<li[^>]*>/gi, "\n• ")
    .replace(/<\/(p|div|tr|h[1-6])>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, "\"")
    .replace(/&#39;/gi, "'")
    .replace(/[ \t]+/g, " ")
    .replace(/[ \t]*\n[ \t]*/g, "\n")
    // Real HTML source usually has its own newlines between tags for
    // readability - those combine with the "\n• " a <li> just inserted into
    // a blank line ahead of every single bullet, regardless of why the
    // double newline happened. Collapsing straight to one line break right
    // before a bullet marker is what actually makes a list read as tight
    // instead of spaced out.
    .replace(/\n{2,}(?=• )/g, "\n")
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
//
// Only collapses spaces/tabs, never newlines - an earlier version used
// \s{2,} here, which also matched newlines and flattened every real
// paragraph break htmlToPlainText had just inserted into one run-on wall of
// text (confirmed live: a clean email read as a single unbroken paragraph
// instead of the several the sender actually wrote).
function stripCssRemnants(text: string): string {
  return text
    .replace(/[.#@]?[\w-]+\s*\{[^{}]*\}/g, " ") // rule blocks: .foo { ... }
    .replace(/[a-zA-Z-]+\s*:\s*[^;{}\n]+;/g, " ") // bare declarations: color: red;
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// A markup/CSS fragment can leave a short-lived remnant that isn't itself a
// full rule block or declaration - just a bare token like "96" (from
// "<o:PixelsPerInch>96</o:PixelsPerInch>") sitting right before the real
// message starts. Narrow on purpose: only strips 1-3 digits at the very
// start of the text, immediately followed by a capitalized word - real
// sentences that legitimately start with a number ("3 tests failing...")
// are lowercase after the digit and won't match.
function stripLeadingArtifactToken(text: string): string {
  return text.replace(/^\d{1,3}\s+(?=[A-Z])/, "");
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
  const cleaned = stripLeadingArtifactToken(stripCssRemnants(htmlStripped));
  return isReadableProse(cleaned) ? cleaned : "(no readable message content captured)";
}
