// The portal realtime runtime (ADR-100): one socket per tab for the confirmed account, one-time
// tickets sent only in the first frame, bounded reconnects, and nothing at all when disabled.
// Sockets, tickets and timers are fakes; no test opens a network connection.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { parseRealtimeConfig, REALTIME_SOCKET_PATH } from "../src/features/realtime/realtime-config.ts";
import { authenticateFrame, parseServerFrame } from "../src/features/realtime/realtime-protocol.ts";
import {
  BACKOFF_MAX_MS,
  backoffDelay,
  HIDDEN_GRACE_MS,
  LIFETIME_RECONNECT_SPREAD_MS,
  READY_TIMEOUT_MS,
  RealtimeRuntime,
  realtimeAccount,
  STABLE_CONNECTION_MS,
} from "../src/features/realtime/realtime-runtime.ts";

const SOCKET_URL = "wss://staging-api.example.test/api/realtime/v1/socket";
const READY = '{"v":1,"type":"ready"}';
const THREAD = "0b6f1c2e-4a5d-4e8f-9a1b-2c3d4e5f6a7b";
const flush = () => new Promise((resolve) => setImmediate(resolve));

function createHarness({ url = SOCKET_URL, online = true, visible = true } = {}) {
  const log = [];
  const sockets = [];
  const tickets = [];
  const timers = new Map();
  let clock = 0;
  let nextTimer = 1;
  let sessionEnded = 0;

  class FakeSocket {
    constructor(socketUrl) {
      this.url = socketUrl;
      this.sent = [];
      this.closedWith = null;
      this.onopen = this.onmessage = this.onclose = this.onerror = null;
      this.index = sockets.length;
      sockets.push(this);
      log.push(`socket:${this.index}`);
    }
    send(data) {
      this.sent.push(data);
    }
    close(code) {
      this.closedWith = code;
      log.push(`close:${this.index}`);
    }
    serverOpen() {
      this.onopen?.({});
    }
    serverSend(data) {
      this.onmessage?.({ data });
    }
    serverClose(code) {
      this.onclose?.({ code });
    }
  }

  const runtime = new RealtimeRuntime({
    url,
    requestTicket: (signal) =>
      new Promise((resolve) => {
        tickets.push({ signal, resolve });
        log.push(`ticket:${tickets.length - 1}`);
      }),
    createSocket: (socketUrl) => new FakeSocket(socketUrl),
    onSessionEnded: () => {
      sessionEnded += 1;
      log.push("session-ended");
    },
    isOnline: () => online,
    isVisible: () => visible,
    setTimer: (callback, ms) => {
      const id = nextTimer++;
      timers.set(id, { at: clock + ms, callback });
      return id;
    },
    clearTimer: (id) => timers.delete(id),
    now: () => clock,
    random: () => 0.5,
  });

  async function advance(ms) {
    const target = clock + ms;
    for (;;) {
      const due = [...timers.entries()].filter(([, timer]) => timer.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      timers.delete(due[0]);
      clock = due[1].at;
      due[1].callback();
      await flush();
    }
    clock = target;
    await flush();
  }

  async function grant(account, index = tickets.length - 1) {
    tickets[index].resolve({ kind: "ticket", ticket: `ticket-for-${account}-${index}`, userId: account });
    await flush();
    return sockets.at(-1);
  }

  async function goLive(account) {
    const socket = await grant(account);
    socket.serverOpen();
    socket.serverSend(READY);
    return socket;
  }

  return {
    runtime,
    log,
    sockets,
    tickets,
    advance,
    grant,
    goLive,
    state: () => runtime.getSnapshot().state,
    generation: () => runtime.getSnapshot().generation,
    sessionEnded: () => sessionEnded,
    pendingTimers: () => timers.size,
  };
}

test("configuration enables realtime only for the exact socket URL", () => {
  const production = { production: true };
  assert.deepEqual(parseRealtimeConfig("true", SOCKET_URL, production), { enabled: true, url: SOCKET_URL });
  assert.deepEqual(parseRealtimeConfig(undefined, SOCKET_URL, production), { enabled: false });
  assert.deepEqual(parseRealtimeConfig("false", SOCKET_URL, production), { enabled: false });
  assert.deepEqual(parseRealtimeConfig("true", undefined, production), { enabled: false });
  for (const url of [
    "ws://staging-api.example.test/api/realtime/v1/socket",
    "https://staging-api.example.test/api/realtime/v1/socket",
    `${SOCKET_URL}?ticket=abc`,
    `${SOCKET_URL}#ticket`,
    `${SOCKET_URL}?`,
    "wss://user:secret@staging-api.example.test/api/realtime/v1/socket",
    "wss://staging-api.example.test/api/v1/realtime/tickets",
    "wss://staging-api.example.test/api/realtime/v1/socket/",
    "not a url",
  ]) {
    assert.deepEqual(parseRealtimeConfig("true", url, production), { enabled: false }, url);
  }
  assert.deepEqual(
    parseRealtimeConfig("true", `ws://localhost:8080${REALTIME_SOCKET_PATH}`, { production: false }),
    { enabled: true, url: `ws://localhost:8080${REALTIME_SOCKET_PATH}` },
  );
});

test("a disabled build never requests a ticket or opens a socket", async () => {
  const h = createHarness({ url: null });
  h.runtime.setAccount("a");
  h.runtime.setOnline(false);
  h.runtime.setOnline(true);
  h.runtime.setVisible(false);
  h.runtime.setVisible(true);
  await h.advance(10 * 60_000);
  assert.equal(h.state(), "disabled");
  assert.equal(h.tickets.length, 0);
  assert.equal(h.sockets.length, 0);
});

test("only a confirmed account has a socket", async () => {
  for (const state of ["pending", "unverified", "signed-out"]) assert.equal(realtimeAccount(state, "a"), null, state);
  assert.equal(realtimeAccount("confirmed", null), null);
  assert.equal(realtimeAccount("confirmed", "a"), "a");

  const h = createHarness();
  h.runtime.setAccount(null);
  await h.advance(60_000);
  assert.equal(h.state(), "idle");
  assert.equal(h.tickets.length, 0);
});

test("a confirmed account gets one socket; the ticket is only in the first frame", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  assert.equal(h.state(), "connecting");
  assert.equal(h.tickets.length, 1);
  const socket = await h.grant("a");

  assert.equal(h.sockets.length, 1);
  assert.equal(socket.url, SOCKET_URL, "The socket URL is the configured URL, never carrying the ticket");
  assert.doesNotMatch(socket.url, /ticket/);
  assert.deepEqual(socket.sent, [], "Nothing is sent before the socket opens");
  socket.serverOpen();
  assert.deepEqual(socket.sent, [authenticateFrame("ticket-for-a-0")]);
  socket.serverOpen();
  assert.equal(socket.sent.length, 1, "The ticket is sent once");
  assert.equal(h.state(), "connecting");

  socket.serverSend(READY);
  assert.deepEqual(h.runtime.getSnapshot(), { state: "live", generation: 1 });
  assert.equal(h.sockets.length, 1);
  assert.equal(h.tickets.length, 1);
});

test("changing accounts closes the previous socket before the next account's ticket", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  const first = await h.goLive("a");

  h.runtime.setAccount("b");

  assert.equal(first.closedWith, 1000);
  assert.deepEqual(h.log.slice(h.log.indexOf("close:0")), ["close:0", "ticket:1"]);
  assert.equal(h.tickets[0].signal.aborted, true);
  first.serverSend('{"v":1,"type":"test.changed"}');
  first.serverClose(1006);
  assert.equal(h.tickets.length, 2, "The closed socket schedules nothing");
  const second = await h.goLive("b");
  second.serverOpen();
  assert.deepEqual(second.sent, [authenticateFrame("ticket-for-b-1")]);
  assert.equal(h.state(), "live");
});

test("a ticket requested for an abandoned account never opens a socket", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  h.runtime.setAccount("b");
  assert.equal(h.tickets[0].signal.aborted, true);
  await h.grant("a", 0);
  assert.equal(h.sockets.length, 0);
  await h.grant("b", 1);
  assert.equal(h.sockets.length, 1);
});

test("a ticket for a different account than the confirmed one is refused", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  h.tickets[0].resolve({ kind: "ticket", ticket: "ticket-for-b", userId: "b" });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(h.sockets.length, 0);
  assert.equal(h.sessionEnded(), 1);
  assert.equal(h.state(), "connecting");
});

test("signing out or unmounting closes the socket and schedules nothing", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  const socket = await h.goLive("a");

  h.runtime.setAccount(null);

  assert.equal(socket.closedWith, 1000);
  assert.equal(h.state(), "idle");
  assert.equal(h.pendingTimers(), 0);
  await h.advance(10 * 60_000);
  assert.equal(h.tickets.length, 1);
});

test("offline closes the socket and stops attempts; online retries at once", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  const socket = await h.goLive("a");

  h.runtime.setOnline(false);
  assert.equal(socket.closedWith, 1000);
  assert.equal(h.state(), "offline");
  await h.advance(30 * 60_000);
  assert.equal(h.tickets.length, 1, "No ticket requests while offline");

  h.runtime.setOnline(true);
  assert.equal(h.tickets.length, 2, "Back online retries immediately");
  assert.equal(h.state(), "reconnecting");
});

test("a tab that starts offline waits for the network", async () => {
  const h = createHarness({ online: false });
  h.runtime.setAccount("a");
  await h.advance(60_000);
  assert.equal(h.state(), "offline");
  assert.equal(h.tickets.length, 0);
  h.runtime.setOnline(true);
  assert.equal(h.tickets.length, 1);
});

test("a hidden tab closes after the grace period and reconnects when shown", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  const socket = await h.goLive("a");

  h.runtime.setVisible(false);
  await h.advance(HIDDEN_GRACE_MS - 1);
  h.runtime.setVisible(true);
  await h.advance(HIDDEN_GRACE_MS * 2);
  assert.equal(socket.closedWith, null, "A quick tab switch keeps the socket");

  h.runtime.setVisible(false);
  await h.advance(HIDDEN_GRACE_MS);
  assert.equal(socket.closedWith, 1000);
  assert.equal(h.state(), "idle");
  await h.advance(30 * 60_000);
  assert.equal(h.tickets.length, 1, "Hidden tabs do not reconnect");

  h.runtime.setVisible(true);
  assert.equal(h.tickets.length, 2, "Showing the tab reconnects with a fresh ticket");
  await h.goLive("a");
  assert.deepEqual(h.runtime.getSnapshot(), { state: "live", generation: 2 });
});

test("a tab opened in the background does not connect until shown", async () => {
  const h = createHarness({ visible: false });
  h.runtime.setAccount("a");
  assert.equal(h.tickets.length, 0);
  assert.equal(h.state(), "idle");
  h.runtime.setVisible(true);
  assert.equal(h.tickets.length, 1);
});

test("ticket failures back off exponentially with jitter, within a bound", async () => {
  assert.equal(backoffDelay(0, () => 0.5), 750);
  assert.equal(backoffDelay(1, () => 0.5), 1500);
  assert.equal(backoffDelay(3, () => 0), 4000);
  for (const attempt of [10, 20, 50]) {
    assert.ok(backoffDelay(attempt, () => 1) <= BACKOFF_MAX_MS);
    assert.ok(backoffDelay(attempt, () => 0) >= BACKOFF_MAX_MS / 2);
  }

  const h = createHarness();
  h.runtime.setAccount("a");
  const expected = [750, 1500, 3000, 6000, 12000, 24000, 45000, 45000, 45000];
  for (const [index, delay] of expected.entries()) {
    h.tickets[index].resolve({ kind: "unavailable" });
    await flush();
    await h.advance(delay - 1);
    assert.equal(h.tickets.length, index + 1, `attempt ${index + 1} waits ${delay} ms`);
    await h.advance(1);
    assert.equal(h.tickets.length, index + 2);
  }
  assert.equal(h.state(), "connecting");
  assert.equal(h.sockets.length, 0);
});

test("rejected authentication and server failures close and retry with backoff", async () => {
  for (const code of [4401, 4408, 1008, 1013, 1006, 1011, 1012]) {
    const h = createHarness();
    h.runtime.setAccount("a");
    const socket = await h.grant("a");
    socket.serverOpen();
    socket.serverClose(code);
    assert.equal(h.state(), "connecting", `close ${code}`);
    await h.advance(749);
    assert.equal(h.tickets.length, 1, `close ${code} waits`);
    await h.advance(1);
    assert.equal(h.tickets.length, 2, `close ${code} retries`);
  }
});

test("a socket that never becomes ready is dropped and retried", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  const socket = await h.grant("a");
  socket.serverOpen();
  await h.advance(READY_TIMEOUT_MS - 1);
  assert.equal(socket.closedWith, null);
  await h.advance(1);
  assert.equal(socket.closedWith, 1000);
  await h.advance(750);
  assert.equal(h.tickets.length, 2);
});

test("a revoked session asks the portal to re-check it and backs off", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  const socket = await h.goLive("a");
  socket.serverClose(4403);
  assert.equal(h.sessionEnded(), 1);
  assert.equal(h.state(), "reconnecting");
  await h.advance(749);
  assert.equal(h.tickets.length, 1);
  await h.advance(1);
  h.tickets[1].resolve({ kind: "session-ended" });
  await flush();
  assert.equal(h.sessionEnded(), 2);
  assert.equal(h.sockets.length, 1);
});

test("the bounded lifetime reconnects promptly and resets the backoff", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  h.tickets[0].resolve({ kind: "unavailable" });
  await flush();
  await h.advance(750);
  h.tickets[1].resolve({ kind: "unavailable" });
  await flush();
  await h.advance(1500);
  const socket = await h.goLive("a");
  await h.advance(15 * 60_000);

  socket.serverClose(4000);
  assert.equal(h.state(), "reconnecting");
  await h.advance(LIFETIME_RECONNECT_SPREAD_MS / 2);
  assert.equal(h.tickets.length, 4);
  h.tickets[3].resolve({ kind: "unavailable" });
  await flush();
  await h.advance(749);
  assert.equal(h.tickets.length, 4);
  await h.advance(1);
  assert.equal(h.tickets.length, 5, "The backoff restarted from the first step");
});

test("a connection that stayed live resets the backoff; a flapping one does not", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  let socket = await h.goLive("a");
  socket.serverClose(1006);
  await h.advance(750);
  socket = await h.goLive("a");
  socket.serverClose(1006);
  await h.advance(1499);
  assert.equal(h.tickets.length, 2, "Immediate drops keep backing off");
  await h.advance(1);
  socket = await h.goLive("a");
  await h.advance(STABLE_CONNECTION_MS);
  socket.serverClose(1006);
  await h.advance(750);
  assert.equal(h.tickets.length, 4, "A stable connection resets the backoff");
});

test("every ready starts a new reconciliation generation", async () => {
  const h = createHarness();
  const seen = [];
  h.runtime.subscribe(() => seen.push({ ...h.runtime.getSnapshot() }));
  h.runtime.setAccount("a");
  let socket = await h.goLive("a");
  socket.serverSend(READY);
  socket.serverClose(1012);
  await h.advance(750);
  socket = await h.goLive("a");
  assert.deepEqual(seen, [
    { state: "connecting", generation: 0 },
    { state: "live", generation: 1 },
    { state: "reconnecting", generation: 1 },
    { state: "live", generation: 2 },
  ]);
});

test("consumers share the one socket and receive only valid hints after ready", async () => {
  const h = createHarness();
  const first = [];
  const second = [];
  h.runtime.subscribeEvent("test.thread_changed", (event) => first.push(event));
  const unsubscribe = h.runtime.subscribeEvent("test.thread_changed", (event) => second.push(event));
  h.runtime.subscribeEvent("test.thread_changed", () => {
    throw new Error("A consumer failure");
  });
  h.runtime.setAccount("a");
  const socket = await h.grant("a");
  socket.serverOpen();
  const event = `{"v":1,"type":"test.thread_changed","thread_id":"${THREAD}"}`;
  socket.serverSend(event);
  assert.equal(first.length, 0, "Nothing is delivered before ready");
  socket.serverSend(READY);
  socket.serverSend(event);
  for (const invalid of [
    "not json",
    '{"v":2,"type":"test.thread_changed"}',
    '{"v":1,"type":"test.thread_changed","body":"Counseling notes"}',
    `{"v":1,"type":"test.thread_changed","thread_id":"${THREAD}","title":"x"}`,
    '{"v":1,"type":"ready","user_id":"x"}',
  ]) {
    socket.serverSend(invalid);
  }
  unsubscribe();
  socket.serverSend(event);

  assert.deepEqual(first, [JSON.parse(event), JSON.parse(event)]);
  assert.deepEqual(second, [JSON.parse(event)]);
  assert.equal(h.sockets.length, 1);
  assert.equal(h.state(), "live");
});

test("a server that has realtime turned off stops all attempts", async () => {
  const h = createHarness();
  h.runtime.setAccount("a");
  h.tickets[0].resolve({ kind: "disabled" });
  await flush();
  assert.equal(h.state(), "disabled");
  h.runtime.setOnline(false);
  h.runtime.setOnline(true);
  h.runtime.setAccount("b");
  await h.advance(60 * 60_000);
  assert.equal(h.tickets.length, 1);
  assert.equal(h.sockets.length, 0);
});

test("server frames are content-free and versioned", () => {
  assert.deepEqual(parseServerFrame(READY), { kind: "ready" });
  assert.equal(parseServerFrame('{"v":1,"type":"Ready"}'), null);
  assert.equal(parseServerFrame(`{"v":1,"type":"x.y","n":"${"a".repeat(600)}"}`), null);
  assert.equal(parseServerFrame({ v: 1, type: "ready" }), null);
  assert.deepEqual(parseServerFrame('{"v":1,"type":"notifications.changed"}'), {
    kind: "event",
    event: { v: 1, type: "notifications.changed" },
  });
  assert.equal(authenticateFrame("abc"), '{"type":"authenticate","ticket":"abc"}');
});

test("only the portal runtime opens a WebSocket; no feature owns one", () => {
  const src = fileURLToPath(new URL("../src/", import.meta.url));
  const files = [];
  const walk = (directory) => {
    for (const name of readdirSync(directory)) {
      const path = join(directory, name);
      if (statSync(path).isDirectory()) {
        if (name !== "generated") walk(path);
      } else if (/\.(ts|tsx)$/.test(name)) files.push(path);
    }
  };
  walk(src);
  const sockets = files.filter((file) => /new\s+WebSocket\s*\(/.test(readFileSync(file, "utf8")));
  assert.deepEqual(sockets.map((file) => relative(src, file)), ["features/realtime/realtime-provider.tsx"]);
  const seam = files.filter((file) => readFileSync(file, "utf8").includes("__COMPASS_REALTIME_TEST_CONFIG__"));
  assert.deepEqual(seam.map((file) => relative(src, file)), ["features/realtime/realtime-config.ts"]);
  const config = readFileSync(join(src, "features/realtime/realtime-config.ts"), "utf8");
  assert.match(config, /!production && typeof window !== "undefined" && window\.__COMPASS_REALTIME_TEST_CONFIG__/);
  const ticket = readFileSync(join(src, "features/realtime/realtime-ticket.ts"), "utf8");
  assert.doesNotMatch(ticket, /localStorage|sessionStorage|console\./);
});
