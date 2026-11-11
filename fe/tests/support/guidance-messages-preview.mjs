// Safe local native-browser preview: every API request ends here, and mutations are refused.
import http from "node:http";
import { LONG_STAFF, messagesAccount, sessionFor, studentWorld, threadIds } from "./guidance-messages-fixtures.mjs";

const backend = studentWorld();
backend.state.threads.get(threadIds.counseling).counselor = LONG_STAFF;
backend.state.relationships[0].counselor = LONG_STAFF;
const empty = { items: [], page: 1, page_size: 20, has_next: false };
const upstreamPort = Number(process.env.COMPASS_PREVIEW_UPSTREAM_PORT ?? 3127);
const previewPort = Number(process.env.COMPASS_PREVIEW_PORT ?? 3128);
http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${previewPort}`);
  if (url.pathname.startsWith("/api/")) {
    const reply = (body, status = 200) => {
      res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify(body));
    };
    if (req.method !== "GET") return reply({ error: { code: "synthetic_preview", message: "Read-only synthetic preview" } }, 403);
    if (url.pathname === "/api/v1/auth/session") return reply(sessionFor(messagesAccount("STUDENT")));
    if (url.pathname === "/api/v1/auth/csrf") return reply({ csrf_token: "synthetic-preview" });
    if (url.pathname === "/api/v1/me/profile") return reply({ full_name: "Synthetic Student", photo: null });
    if (url.pathname === "/api/v1/platform/status") return reply({ status: "operational", starts_at: null, ends_at: null, message: null });
    if (url.pathname === "/api/v1/notifications/unread-count") return reply({ unread_count: 0 });
    if (url.pathname === "/api/v1/notifications/push/config") return reply({ enabled: false, vapid_public_key: null });
    if (["/api/v1/privacy/my-notices", "/api/v1/notifications"].includes(url.pathname)) return reply(empty);
    if (await backend.handler({ url, pathname: url.pathname, method: "GET", request: { postData: () => null }, reply })) return;
    return reply({ error: { code: "synthetic_unavailable" } }, 404);
  }
  const proxy = http.request({ hostname: "127.0.0.1", port: upstreamPort, path: req.url, method: req.method, headers: { ...req.headers, host: `127.0.0.1:${upstreamPort}` } }, (upstream) => {
    res.writeHead(upstream.statusCode, upstream.headers);
    upstream.pipe(res);
  });
  proxy.on("error", () => { res.writeHead(502); res.end("Start the separate local frontend preview."); });
  req.pipe(proxy);
}).listen(previewPort, "127.0.0.1", () => {
  console.log(`Synthetic Messages preview: http://127.0.0.1:${previewPort}/portal/messages/${threadIds.counseling}`);
});
