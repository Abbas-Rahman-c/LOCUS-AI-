// supabase/functions/_shared/memory/embeddings.ts
//
// Same Voyage call shape as ai-worker/index.ts's embedDocument - shared
// here since both the memory write path and (in Batch 2) entity resolution
// need it.

const VOYAGE_API_KEY = Deno.env.get("VOYAGE_API_KEY") ?? "";
const VOYAGE_MODEL = Deno.env.get("VOYAGE_EMBED_MODEL") ?? "voyage-4-large";
const VOYAGE_OUTPUT_DIMENSION = 1024;

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function embedText(text: string, inputType: "document" | "query" = "document"): Promise<number[]> {
  const resp = await fetchWithTimeout("https://api.voyageai.com/v1/embeddings", {
    method: "POST",
    headers: { Authorization: `Bearer ${VOYAGE_API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify({
      input: [text],
      model: VOYAGE_MODEL,
      input_type: inputType,
      output_dimension: VOYAGE_OUTPUT_DIMENSION,
      truncation: true,
    }),
  }, 30_000);
  if (!resp.ok) throw new Error(`Voyage API error ${resp.status}: ${await resp.text()}`);
  const data = await resp.json();
  const embedding = data.data?.[0]?.embedding;
  if (!Array.isArray(embedding) || embedding.length !== VOYAGE_OUTPUT_DIMENSION) {
    throw new Error("Voyage returned an unexpected embedding shape");
  }
  return embedding;
}
