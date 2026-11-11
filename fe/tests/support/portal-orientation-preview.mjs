// A safe local Safari/manual preview: every /api/v1 request is synthetic, writes are rejected,
// and the browser's CSP prevents connections to any external service. Run a local Next server
// first, then node tests/support/portal-orientation-preview.mjs and open the printed URL.
import { guideWorld } from "./task-guide-fixtures.mjs";
import { createServer } from "node:http";
import { navigationWorld, profiles } from "./f2-navigation-fixtures.mjs";

const upstream = new URL(process.env.COMPASS_UI_BASE_URL ?? "http://127.0.0.1:3217");
if (!["localhost", "127.0.0.1", "[::1]"].includes(upstream.hostname)) throw new Error("Use a local Next server.");
const port = Number(process.env.COMPASS_PREVIEW_PORT ?? 3219);
const world = process.env.COMPASS_PREVIEW_GUIDE ? guideWorld(process.env.COMPASS_PREVIEW_GUIDE) : navigationWorld(profiles.Student);
const empty = { items: [], page: 1, page_size: 20, has_next: false };
const reads = {
  "/api/v1/platform/status": { status: "operational", starts_at: null, ends_at: null, message: null },
  "/api/v1/notifications/unread-count": { unread_count: 0 },
  "/api/v1/notifications/push/config": { enabled: false, vapid_public_key: null },
  "/api/v1/privacy/my-notices": empty,
  "/api/v1/notifications": empty,
};
const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://127.0.0.1:${port}`);
  response.setHeader("Cache-Control", "no-store");
  const reply = (body, status = 200) => {
    response.writeHead(status, { "Content-Type": "application/json" });
    response.end(JSON.stringify(body));
  };
  if (url.pathname.startsWith("/api/v1/")) {
    if (request.method !== "GET") return reply({ error: { code: "synthetic_write_blocked", message: "Preview writes are disabled." } }, 405);
    if (await world.handler({ pathname: url.pathname, method: request.method, url, reply })) return;
    return reply(reads[url.pathname] ?? { error: { code: "synthetic_unavailable", message: "No preview fixture." } }, url.pathname in reads ? 200 : 404);
  }
  // A preview never installs a persistent worker in the reader's browser.
  if (url.pathname === "/sw.js") { response.writeHead(404); return response.end(); }
  try {
    const headers = new Headers();
    // Preserve App Router document/flight navigation, without forwarding cookies or credentials.
    for (const key of ["accept", "rsc", "next-router-state-tree", "next-router-prefetch", "next-router-segment-prefetch", "next-url"]) {
      const value = request.headers[key];
      if (typeof value === "string") headers.set(key, value);
    }
    const result = await fetch(new URL(url.pathname + url.search, upstream), { redirect: "manual", headers });
    response.statusCode = result.status;
    for (const [key, value] of result.headers) {
      if (!["content-encoding", "content-length", "set-cookie", "cache-control"].includes(key)) response.setHeader(key, value);
    }
    response.setHeader("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'none'; form-action 'none'");
    response.end(Buffer.from(await result.arrayBuffer()));
  } catch { response.writeHead(502); response.end("Start the local Next server before opening this synthetic preview."); }
});
server.listen(port, "127.0.0.1", () => console.log(`Synthetic preview: http://127.0.0.1:${port}/portal`));
