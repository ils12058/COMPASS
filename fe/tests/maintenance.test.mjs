import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  MaintenanceNotice,
  PortalMaintenanceView,
  PublicMaintenanceGate,
} from "../src/features/platform/maintenance-presentation.tsx";
import {
  boundaryRefetchDelay,
  checkMaintenanceStatus,
  maintenancePhase,
  portalMaintenanceMode,
} from "../src/features/platform/maintenance-status.ts";
import { getPlatformPublicStatusQueryKey } from "../src/lib/api/generated/platform-operations/platform-operations.ts";

const SERVER_NOW = "Sun, 04 Oct 2026 02:00:00 GMT";
const serverNow = Date.parse(SERVER_NOW);
const inMinutes = (minutes) => new Date(serverNow + minutes * 60_000).toISOString();

const operational = { status: "operational", message: null, starts_at: null, ends_at: null };
const scheduled = { status: "maintenance_scheduled", message: "Database upgrade.", starts_at: inMinutes(30), ends_at: inMinutes(90) };
const active = { status: "maintenance_active", message: "Back after the upgrade.", starts_at: null, ends_at: inMinutes(60) };

function clientWith(status) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (status) {
    client.setQueryData(getPlatformPublicStatusQueryKey(), { data: status, status: 200, headers: { date: SERVER_NOW } });
  }
  return client;
}

function render(client, element) {
  return renderToStaticMarkup(createElement(QueryClientProvider, { client }, element));
}

const PAGE = "ORDINARY-PUBLIC-PAGE";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

test("the phase comes only from the backend status, and an unread status is unknown", () => {
  assert.equal(maintenancePhase(undefined), "unknown");
  assert.equal(maintenancePhase(operational), "operational");
  assert.equal(maintenancePhase(scheduled), "scheduled");
  assert.equal(maintenancePhase(active), "active");
  // An expected end in the past does not end maintenance: only the backend does.
  assert.equal(maintenancePhase({ ...active, ends_at: inMinutes(-120) }), "active");
});

test("operational status renders the ordinary public page", () => {
  const html = render(clientWith(operational), createElement(PublicMaintenanceGate, null, PAGE));
  assert.ok(html.includes(PAGE));
  assert.ok(!html.includes("temporarily unavailable"));
});

test("scheduled maintenance keeps the public page and shows a compact notice", () => {
  const client = clientWith(scheduled);
  const html = render(client, createElement(PublicMaintenanceGate, null, PAGE));
  assert.ok(html.includes(PAGE));
  const notice = render(client, createElement(MaintenanceNotice));
  assert.match(notice, /Scheduled maintenance/);
  assert.match(notice, /Database upgrade\./);
});

test("active maintenance replaces the ordinary public page", () => {
  const html = render(clientWith(active), createElement(PublicMaintenanceGate, null, PAGE));
  assert.ok(!html.includes(PAGE));
  assert.match(html, /<h1[^>]*>COMPASS is temporarily unavailable<\/h1>/);
  assert.match(html, /Back after the upgrade\./);
  assert.match(html, /Expected back/);
  assert.match(html, /<button[^>]*>Check again<\/button>/);
  assert.match(html, /href="\/login"/);
  assert.doesNotMatch(html, /503|maintenance_mode|Manual|source/i);
});

test("a status that could not be read never locks COMPASS", () => {
  const html = render(clientWith(undefined), createElement(PublicMaintenanceGate, null, PAGE));
  assert.ok(html.includes(PAGE));
});

test("the configured message is rendered as text, never as markup", () => {
  const html = render(clientWith({ ...active, message: "<b>Maintenance</b>\nSecond line" }), createElement(PublicMaintenanceGate, null, PAGE));
  assert.ok(html.includes("&lt;b&gt;Maintenance&lt;/b&gt;"));
  assert.ok(!html.includes("<b>Maintenance</b>"));
  assert.match(html, /whitespace-pre-wrap/);
});

test("sign-in stays usable during active maintenance, with a compact notice", () => {
  const client = clientWith(active);
  const auth = render(client, createElement(MaintenanceNotice, { surface: "auth" }));
  assert.match(auth, /COMPASS is under maintenance/);
  assert.match(auth, /Most workspaces are temporarily unavailable\./);
  assert.doesNotMatch(auth, /Check again|<h1/);
  // Ordinary pages show nothing here: the gate replaces them instead.
  assert.equal(render(client, createElement(MaintenanceNotice)), "");
});

const WORKSPACE = "DOCK-AND-WORKSPACE";
const PAGE_ONLY = "PLATFORM-PAGE";

function portal(props) {
  return renderToStaticMarkup(
    createElement(PortalMaintenanceView, {
      status: active,
      phase: "active",
      pending: false,
      pathname: "/portal/appointments/my",
      canOperate: false,
      workspace: WORKSPACE,
      page: PAGE_ONLY,
      controls: null,
      checking: false,
      checkedAt: null,
      onCheck: () => undefined,
      ...props,
    }),
  );
}

test("active maintenance replaces ordinary portal workspaces, dock included", () => {
  const html = portal({});
  assert.ok(!html.includes(WORKSPACE));
  assert.ok(!html.includes(PAGE_ONLY));
  assert.match(html, /<h1[^>]*>COMPASS is under maintenance<\/h1>/);
  assert.doesNotMatch(html, /Open Platform Operations/);
});

test("operators can reach Platform Operations during active maintenance", () => {
  const screen = portal({ canOperate: true });
  assert.match(screen, /href="\/portal\/platform\/maintenance"[^>]*>Open Platform Operations</);

  const recovery = portal({ canOperate: true, pathname: "/portal/platform/maintenance" });
  assert.ok(recovery.includes(PAGE_ONLY));
  assert.ok(!recovery.includes(WORKSPACE));
  assert.match(recovery, /Maintenance Mode is active\./);

  // Without Platform Operations access, those routes show maintenance like any other.
  const denied = portal({ pathname: "/portal/platform/maintenance" });
  assert.ok(!denied.includes(PAGE_ONLY));
  assert.match(denied, /COMPASS is under maintenance/);
});

test("scheduled, operational, and unknown status keep the portal usable", () => {
  for (const [status, phase] of [[scheduled, "scheduled"], [operational, "operational"], [undefined, "unknown"]]) {
    const html = portal({ status, phase });
    assert.equal(html, WORKSPACE);
  }
  assert.equal(portalMaintenanceMode({ phase: "active", pathname: "/portal/platformer", canOperate: true }), "maintenance");
  assert.equal(portalMaintenanceMode({ phase: "active", pathname: "/portal/platform", canOperate: true }), "recovery");
});

test("boundaries schedule a fresh check by the server clock, and never an unlock", () => {
  const receivedAt = Date.now();
  // Scheduled: ask again just after the window starts.
  const start = boundaryRefetchDelay(scheduled, SERVER_NOW, receivedAt);
  assert.ok(start > 30 * 60_000 && start <= 30 * 60_000 + 1_000);
  // Active: ask again just after the window's end.
  const end = boundaryRefetchDelay(active, SERVER_NOW, receivedAt);
  assert.ok(end > 60 * 60_000 && end <= 60 * 60_000 + 1_000);
  // An expected end already past when read schedules nothing; the status stays active until polled.
  assert.equal(boundaryRefetchDelay({ ...active, ends_at: inMinutes(-5) }, SERVER_NOW, receivedAt), null);
  assert.equal(boundaryRefetchDelay(operational, SERVER_NOW, receivedAt), null);
});

function respond(body) {
  globalThis.fetch = async (url) => {
    respond.calls.push(String(url));
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", date: SERVER_NOW } });
  };
}
respond.calls = [];

test("Check again reads the status afresh, and COMPASS returns only when the backend says so", async () => {
  process.env.COMPASS_API_BASE_URL = "http://backend.test";
  const client = clientWith({ ...active, ends_at: inMinutes(-1) });

  respond.calls = [];
  respond({ ...active, ends_at: inMinutes(-1) });
  await checkMaintenanceStatus(client);
  assert.equal(respond.calls.length, 1);
  assert.match(respond.calls[0], /\/api\/v1\/platform\/status$/);
  // Past the expected end but still active: the screen stays.
  assert.ok(!render(client, createElement(PublicMaintenanceGate, null, PAGE)).includes(PAGE));

  respond(operational);
  await checkMaintenanceStatus(client);
  assert.ok(render(client, createElement(PublicMaintenanceGate, null, PAGE)).includes(PAGE));
});

test("a failed check keeps the last confirmed status and invents none", async () => {
  process.env.COMPASS_API_BASE_URL = "http://backend.test";
  globalThis.fetch = async () => {
    throw new TypeError("network down");
  };
  const unread = clientWith(undefined);
  await assert.rejects(checkMaintenanceStatus(unread));
  assert.ok(render(unread, createElement(PublicMaintenanceGate, null, PAGE)).includes(PAGE));

  const running = clientWith(operational);
  await assert.rejects(checkMaintenanceStatus(running));
  assert.ok(render(running, createElement(PublicMaintenanceGate, null, PAGE)).includes(PAGE));
});
