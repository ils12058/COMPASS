import { createHash } from "node:crypto";

export function diagnosticURL(value) {
  try {
    const url = new URL(value);
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    // External paths can themselves be signed. Never retain an external media URL.
    return local ? `${url.origin}${url.pathname}` : `${url.origin}/[external]`;
  } catch { return "unavailable"; }
}

export function diagnosticError(error) {
  const stack = typeof error === "string" ? error : error.stack ?? error.message ?? String(error);
  const name = typeof error === "string" ? stack.split(":")[0].split("\n")[0] : error.name;
  return {
    name: /^[A-Za-z]*Error$/.test(name) ? name : "Error",
    fingerprint: createHash("sha256").update(stack).digest("hex").slice(0, 16),
    // Stack locations identify hydration/runtime failures without including their private message.
    sources: [...new Set((stack.match(/https?:\/\/[^\s)]+/g) ?? []).map(diagnosticURL))].slice(0, 8),
  };
}

export async function documentReadiness(page, timeoutMs = 1000) {
  let timer;
  try {
    return await Promise.race([
      page.evaluate(() => document.readyState).catch(() => "unavailable"),
      new Promise(resolve => { timer = setTimeout(() => resolve("unavailable"), timeoutMs); }),
    ]);
  } finally { clearTimeout(timer); }
}

export function diagnosticAssertion(error) {
  // Assertion diffs may contain fixture bodies. Keep the assertion header, not its value dump.
  return String(error.message).split("\n")[0]
    .replace(/https?:\/\/[^\s)'"<>]+/g, diagnosticURL).slice(0, 500);
}
