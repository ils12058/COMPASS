// Development-only fallback for API reads made by Next while rendering test pages on the server.
// Browser suites still provide their own per-test route fixtures; unknown server-side calls fail
// closed with JSON instead of producing an empty proxy response or touching a real API.
import { createServer } from "node:http";

const port = Number(process.env.COMPASS_TEST_API_PORT ?? 8000);

const server = createServer((request, response) => {
  const url = new URL(request.url ?? "/", `http://127.0.0.1:${port}`);
  if (url.pathname === "/__health") {
    response.writeHead(200, { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" });
    response.end("ok");
    return;
  }

  const status = 503;
  const payload = { error: { code: "synthetic_unavailable", message: "Server-side API calls are not part of browser fixtures." } };

  console.log(`${request.method ?? "GET"} ${url.pathname}${url.search} -> ${status}`);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(JSON.stringify(payload));
});

server.listen(port, "127.0.0.1", () => console.log(`Synthetic SSR API fallback listening on 127.0.0.1:${port}`));

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
