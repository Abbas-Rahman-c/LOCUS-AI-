// supabase/functions/_shared/memory/crypto.ts
//
// Decrypt-only copy of the AES-256-GCM / "LOCUS1" routine already
// duplicated in api/index.ts and admin-debug-conversation/index.ts (reverse
// of ai-worker/index.ts's encryptRawContent). Needed here so the real
// historical replay can read raw_events.raw_content - a third, read-only
// copy rather than a new shared export, matching this codebase's existing
// pattern of duplicating this small routine per-function rather than
// centralizing it.

const LOCUS_MAGIC = new TextEncoder().encode("LOCUS1");
const NONCE_LEN = 12;

async function getAesKey(): Promise<CryptoKey> {
  const secret = Deno.env.get("RAW_EVENTS_ENCRYPTION_KEY") || Deno.env.get("APP_SECRET_KEY");
  if (!secret) throw new Error("RAW_EVENTS_ENCRYPTION_KEY or APP_SECRET_KEY is not set");
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret));
  return crypto.subtle.importKey("raw", hash, "AES-GCM", false, ["decrypt"]);
}

export async function decryptRawContent(encrypted: Uint8Array): Promise<string> {
  const key = await getAesKey();
  const nonce = encrypted.slice(LOCUS_MAGIC.length, LOCUS_MAGIC.length + NONCE_LEN);
  const ciphertext = encrypted.slice(LOCUS_MAGIC.length + NONCE_LEN);
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, key, ciphertext);
  return new TextDecoder().decode(plaintext);
}

// postgres.js's bytea decoding varies by wire format - normally a
// Uint8Array/Buffer, but a hex-encoded "\x4c4f..." string is also possible.
export function byteaToUint8Array(value: unknown): Uint8Array {
  if (value instanceof Uint8Array) return value;
  if (typeof value === "string") {
    const hex = value.startsWith("\\x") ? value.slice(2) : value;
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
    return bytes;
  }
  return new Uint8Array(value as ArrayLike<number>);
}
