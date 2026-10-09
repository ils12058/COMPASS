// The portal realtime runtime in a real browser (ADR-100). The realtime server is a Playwright
// WebSocket route and every API call is a synthetic fixture: no socket, account, or record is real.
// Realtime is enabled through the development-only test seam, never through build configuration.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { baseURL, check, shown, finish } = await createBrowserHarness("realtime-runtime");

const PAGE = "/portal/services";
const SOCKET_URL = `${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`;
const enableRealtime = `window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(SOCKET_URL)} };`;

const accountUser = (name) => ({ ...user("COUNSELOR"), id: `account-${name}`, first_name: `Account ${name}` });
const sessionFor = (account) => ({
  authenticated: true,
  user: account,
  session: { id: `session-${account.id}`, expires_at: "2099-10-07T00:00:00Z", is_current: true },
});

async function eventually(condition, message, timeout = 10_000) {
  const started = Date.now();
  while (!(await condition())) {
    if (Date.now() - started > timeout) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

// A fake realtime server and a mutable signed-in account shared by the session and ticket routes.
function realtimeWorld(initial) {
  const world = { account: initial, sockets: [], events: [], tickets: [] };
  world.overrides = {
    "/api/v1/auth/session": ({ reply }) =>
      world.account
        ? reply(sessionFor(world.account))
        : reply({ error: { code: "not_authenticated", message: "Synthetic sign-out" } }, 401),
    "POST /api/v1/realtime/tickets": ({ reply }) => {
      if (!world.account) return reply({ error: { code: "not_authenticated", message: "Synthetic" } }, 401);
      const ticket = `ticket-${world.account.id}-${world.tickets.length}`;
      world.tickets.push(ticket);
      return reply({ ticket, expires_in_seconds: 30, user_id: world.account.id });
    },
  };
  world.beforeNavigate = async ({ context }) => {
    await context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
      const socket = { index: world.sockets.length, url: route.url(), frames: [], closed: null, route };
      world.sockets.push(socket);
      world.events.push(`open:${socket.index}`);
      route.onMessage((message) => {
        socket.frames.push(String(message));
        const frame = JSON.parse(String(message));
        if (frame.type === "authenticate") {
          world.events.push(`auth:${socket.index}:${frame.ticket}`);
          route.send('{"v":1,"type":"ready"}');
        }
      });
      route.onClose((code) => {
        socket.closed = code ?? 1005;
        world.events.push(`close:${socket.index}`);
      });
    });
  };
  world.open = () => world.sockets.filter((socket) => socket.closed === null);
  // Replays the event log and returns the most sockets that were ever open at once.
  world.maxOpen = () => {
    let open = 0;
    let max = 0;
    for (const event of world.events) {
      if (event.startsWith("open:")) max = Math.max(max, ++open);
      if (event.startsWith("close:")) open -= 1;
    }
    return max;
  };
  return world;
}

const ticketRequests = (requests) => requests.filter((request) => request.pathname === "/api/v1/realtime/tickets");

{
  const world = realtimeWorld(accountUser("A"));
  await check("realtime is off unless enabled", PAGE, { overrides: world.overrides, beforeNavigate: world.beforeNavigate }, async (page, { requests }) => {
  await shown(page.getByRole("heading", { level: 1 }).first());
  await page.waitForTimeout(2_000);
  assert.equal(world.sockets.length, 0, "No socket is opened");
  assert.equal(ticketRequests(requests).length, 0, "No ticket is requested");
  });
}

{
  const world = realtimeWorld(accountUser("A"));
  await check(
    "one portal socket for the confirmed account, authenticated by its first frame",
    PAGE,
    { initScripts: [enableRealtime], overrides: world.overrides, beforeNavigate: world.beforeNavigate },
    async (page, { requests }) => {
      await shown(page.getByRole("heading", { level: 1 }).first());
      await eventually(() => world.events.some((event) => event.startsWith("auth:")), "The socket authenticates");
      await page.waitForTimeout(1_000);
      assert.equal(world.sockets.length, 1, "Exactly one socket");
      assert.equal(ticketRequests(requests).length, 1, "Exactly one ticket request");
      const [socket] = world.sockets;
      assert.equal(socket.url, SOCKET_URL, "The URL is the configured socket URL");
      assert.ok(!socket.url.includes("?") && !socket.url.includes(world.tickets[0]), "No ticket in the URL");
      assert.deepEqual(socket.frames, [JSON.stringify({ type: "authenticate", ticket: world.tickets[0] })]);
      assert.equal(ticketRequests(requests)[0].method, "POST");
    },
  );
}

{
  const world = realtimeWorld(accountUser("A"));
  await check(
    "changing accounts closes the previous account's socket before the next one opens",
    PAGE,
    { initScripts: [enableRealtime], overrides: world.overrides, beforeNavigate: world.beforeNavigate },
    async (page) => {
      await shown(page.getByRole("heading", { level: 1 }).first());
      await eventually(() => world.events.includes(`auth:0:${world.tickets[0]}`), "Account A authenticates");

      // Another tab signs in as Account B; this tab finds out at its next session check.
      world.account = accountUser("B");
      await page.clock.install();
      await page.clock.fastForward(31_000);
      await page.evaluate(() => {
        window.dispatchEvent(new Event("offline"));
        window.dispatchEvent(new Event("online"));
      });

      await eventually(
        () => world.events.some((event) => event.startsWith("auth:") && event.includes("ticket-account-B")),
        "Account B authenticates its own socket",
      ).catch((error) => {
        throw new Error(`${error.message}: ${world.events.join(" ")} tickets=${world.tickets.join(" ")}`);
      });
      assert.ok(world.sockets[0].closed !== null, "Account A's socket is closed");
      const bSocket = world.sockets.find((socket) => socket.frames.some((frame) => frame.includes("ticket-account-B")));
      assert.ok(world.events.indexOf("close:0") < world.events.indexOf(`open:${bSocket.index}`), "A closes before B opens");
      assert.equal(world.maxOpen(), 1, "Never two sockets at once");
      for (const socket of world.sockets) {
        const accounts = new Set(socket.frames.map((frame) => JSON.parse(frame).ticket.split("-").slice(0, 3).join("-")));
        assert.ok(accounts.size <= 1, "A socket never carries two accounts' tickets");
      }
      assert.ok(
        !world.sockets[0].frames.some((frame) => frame.includes("ticket-account-B")),
        "Account A's socket never authenticates as Account B",
      );
      assert.equal(world.open().length, 1);
    },
  );
}

{
  const world = realtimeWorld(accountUser("A"));
  await check(
    "a revoked session closes its socket and signs out without reconnecting",
    PAGE,
    { initScripts: [enableRealtime], overrides: world.overrides, beforeNavigate: world.beforeNavigate },
    async (page) => {
      await shown(page.getByRole("heading", { level: 1 }).first());
      await eventually(() => world.events.includes(`auth:0:${world.tickets[0]}`), "The socket authenticates");

      world.account = null;
      await world.sockets[0].route.close({ code: 4403, reason: "session_revoked" });

      await page.waitForURL(/\/login/, { timeout: 10_000 });
      await page.waitForTimeout(3_000);
      assert.equal(world.sockets.length, 1, "No socket reconnects for a revoked session");
      assert.equal(world.tickets.length, 1, "No ticket is issued after the revocation");
    },
  );
}

{
  const world = realtimeWorld(accountUser("A"));
  await check(
    "leaving the portal unmounts the runtime and closes its socket",
    PAGE,
    { initScripts: [enableRealtime], overrides: world.overrides, beforeNavigate: world.beforeNavigate },
    async (page) => {
      await shown(page.getByRole("heading", { level: 1 }).first());
      await eventually(() => world.events.includes(`auth:0:${world.tickets[0]}`), "The socket authenticates");

      // Client-side navigation keeps the document, so only the provider's unmount can close it.
      await page.evaluate(() => window.next.router.push("/"));
      await page.waitForURL((url) => url.pathname === "/", { timeout: 60_000 });
      await eventually(() => world.sockets[0].closed !== null, "The socket closes", 60_000);
      await page.waitForTimeout(2_000);
      assert.equal(world.sockets[0].closed, 1000, "The client closed it normally");
      assert.equal(world.sockets.length, 1, "No socket outside the portal");
      assert.equal(world.tickets.length, 1, "No ticket outside the portal");
    },
  );
}

await finish();
