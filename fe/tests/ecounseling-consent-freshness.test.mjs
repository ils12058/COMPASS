import assert from "node:assert/strict";
import { test } from "node:test";

import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { ECounselingConsentFreshness, CONSENT_FALLBACK_REFRESH_MS, CONSENT_LIVE_SAFETY_REFRESH_MS } from "../src/features/ecounseling/consent-freshness.ts";
import { getECounselingAccess } from "../src/features/ecounseling/ecounseling-access.ts";
import { parseServerFrame } from "../src/features/realtime/realtime-protocol.ts";
import { getECounselingGetMyWorkspaceQueryKey, getECounselingListMyConsentsQueryKey, getECounselingGetAssignedWorkspaceQueryKey, getECounselingListAssignedConsentsQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";
import { getAuthGetSessionQueryKey } from "../src/lib/api/generated/auth/auth.ts";
import { createAccountOwnership } from "../src/lib/query/account-ownership.ts";

const A = "a0000000-0000-4000-8000-000000000001";
const B = "b0000000-0000-4000-8000-000000000001";
const settle = () => new Promise((resolve) => setImmediate(resolve));
const keys = {
  STUDENT: [getECounselingListMyConsentsQueryKey, getECounselingGetMyWorkspaceQueryKey],
  COUNSELOR: [getECounselingListAssignedConsentsQueryKey, getECounselingGetAssignedWorkspaceQueryKey],
};
const capabilities = { STUDENT: ["ecounseling.view_self", "ecounseling.consent_self"], COUNSELOR: ["ecounseling.view_assigned", "ecounseling.manage_media_assigned"] };

function fixture(role = "STUDENT", fetch) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const document = new EventTarget(); document.visibilityState = "visible";
  const window = new EventTarget();
  const timers = new Map(); let timerId = 0;
  window.setInterval = (callback, ms) => { timers.set(++timerId, { callback, ms }); return timerId; };
  window.clearInterval = (id) => timers.delete(id);
  const navigator = { onLine: true };
  const consumer = new ECounselingConsentFreshness(client, getECounselingAccess({ role, capabilities: capabilities[role] ?? [] }));
  const calls = []; const releases = [];
  const observer = (key, enabled = true) => {
    const query = new QueryObserver(client, { queryKey: key, enabled, queryFn: async () => {
      calls.push(key[0]);
      return fetch ? fetch(key, calls.length) : { authoritative: calls.length };
    } });
    releases.push(query.subscribe(() => {}));
    return query;
  };
  const seed = (id = A, options = {}) => {
    for (const key of keys[role] ?? []) {
      client.setQueryData(key(id), { authoritative: "previous HTTP approval" });
      if (options.active !== false) observer(key(id), options.enabled !== false);
    }
  };
  consumer.start({ document, window, navigator });
  return {
    client, consumer, document, window, navigator, timers, calls, observer, seed,
    tick: () => [...timers.values()][0]?.callback(),
    delay: () => [...timers.values()][0]?.ms,
    close: () => { consumer.stop(); for (const release of releases) release(); client.clear(); },
  };
}

test("only the exact content-free consent event is parsed", () => {
  const value = { v: 1, type: "ecounseling.consent.changed", appointment_id: A };
  assert.deepEqual(parseServerFrame(JSON.stringify(value)), { kind: "event", event: value });
  const rejected = [
    { ...value, decision: "APPROVED" }, { ...value, scope: "SESSION_MEDIA_CAPTURE" },
    { ...value, room_id: B }, { ...value, consent_id: B }, { ...value, student_id: B },
    { v: 1, type: value.type }, { ...value, appointment_id: "bad" },
    { ...value, appointment_id: A.toUpperCase() }, { ...value, appointment_id: 1 },
    { ...value, appointment_id: null }, { ...value, v: 2 }, { ...value, v: true },
    { ...value, v: "1" }, { ...value, type: "ecounseling.capture.changed" },
  ];
  for (const frame of rejected) assert.equal(parseServerFrame(JSON.stringify(frame)), null, JSON.stringify(frame));
  assert.equal(parseServerFrame(JSON.stringify({ v: 1, type: "messages.thread_changed", thread_id: B, appointment_id: A })), null);
  assert.equal(parseServerFrame(JSON.stringify({ v: 1, type: "notifications.changed", appointment_id: A })), null);
});

for (const role of ["STUDENT", "COUNSELOR"]) test(`${role} hint refreshes only its appointment and authorized canonical query families`, async () => {
  const f = fixture(role);
  try {
    f.seed(A); f.seed(B);
    const opposite = role === "STUDENT" ? "COUNSELOR" : "STUDENT";
    for (const key of keys[opposite]) { f.client.setQueryData(key(A), "wrong role"); f.observer(key(A)); }
    f.consumer.requestRefresh(A);
    assert.equal(f.consumer.isPending(A), true, "Old approval is fenced before HTTP starts");
    await settle();
    assert.deepEqual(f.calls.sort(), keys[role].map((key) => key(A)[0]).sort());
    assert.equal(f.consumer.isPending(A), false);
    for (const key of keys[role]) assert.equal(f.client.getQueryState(key(B)).isInvalidated, false);
  } finally { f.close(); }
});

test("inactive queries become stale; disabled observers never activate HTTP", async () => {
  const f = fixture();
  try {
    f.seed(A, { active: false }); f.seed(B, { enabled: false });
    f.consumer.requestRefresh(A); f.consumer.requestRefresh(B);
    await settle();
    assert.deepEqual(f.calls, []);
    for (const id of [A, B]) for (const key of keys.STUDENT) assert.equal(f.client.getQueryState(key(id)).isInvalidated, true);
  } finally { f.close(); }
});

test("one event with page and active-call observers makes one fetch per family", async () => {
  const f = fixture();
  try {
    f.seed();
    f.observer(getECounselingGetMyWorkspaceQueryKey(A));
    f.consumer.requestRefresh(A);
    await settle();
    assert.equal(f.calls.length, 2);
  } finally { f.close(); }
});

test("a synchronous burst coalesces before fetching", async () => {
  const f = fixture();
  try {
    f.seed();
    for (let i = 0; i < 20; i++) f.consumer.requestRefresh(A);
    await settle();
    assert.equal(f.calls.length, 2);
  } finally { f.close(); }
});

test("hints during active reads queue one trailing reconciliation and keep Start fenced", async () => {
  const held = [];
  const f = fixture("COUNSELOR", () => new Promise((resolve) => held.push(resolve)));
  try {
    f.seed(); f.consumer.requestRefresh(A); await settle();
    assert.equal(held.length, 2);
    for (let i = 0; i < 20; i++) f.consumer.requestRefresh(A);
    for (const resolve of held.splice(0)) resolve({ decision: "old approval" });
    await settle();
    assert.equal(f.calls.length, 4, "Only one trailing refresh per key");
    assert.equal(f.consumer.isPending(A), true, "Old successful response is still unconfirmed");
    for (const resolve of held.splice(0)) resolve({ decision: "withdrawn authoritative response" });
    await settle();
    assert.equal(f.consumer.isPending(A), false);
    assert.equal(f.calls.length, 4);
  } finally { f.close(); }
});

test("a read already started elsewhere is reused instead of canceled; a later hint still heals", async () => {
  const held = [];
  const f = fixture("STUDENT", () => new Promise((resolve) => held.push(resolve)));
  try {
    f.seed();
    const initial = f.client.refetchQueries({ queryKey: getECounselingListMyConsentsQueryKey(A) });
    await settle(); f.consumer.requestRefresh(A); await settle();
    assert.equal(f.calls.length, 2, "Existing consent fetch is reused, workspace fetch starts once");
    f.consumer.requestRefresh(A);
    for (const resolve of held.splice(0)) resolve({ confirmed: 1 });
    await initial; await settle();
    assert.equal(f.calls.length, 4);
    for (const resolve of held.splice(0)) resolve({ confirmed: 2 });
    await settle();
  } finally { f.close(); }
});

test("the first hint during a preexisting read requires a post-hint read even without another hint", async () => {
  const held = [];
  const f = fixture("COUNSELOR", () => new Promise((resolve) => held.push(resolve)));
  try {
    f.seed();
    const oldRead = f.client.refetchQueries({ queryKey: getECounselingListAssignedConsentsQueryKey(A) });
    await settle();
    f.consumer.requestRefresh(A); await settle();
    assert.equal(f.calls.length, 2, "Old consent request reused without restart");
    for (const resolve of held.splice(0)) resolve({ data: { items: [{ effective: true }] } });
    await oldRead; await settle();
    assert.equal(f.calls.length, 4, "One necessary post-hint reconciliation");
    assert.equal(f.consumer.isPending(A), true, "Pre-hint approval never lifts the Start fence");
    for (const resolve of held.splice(0)) resolve({ data: { items: [{ effective: false }] } });
    await settle(); assert.equal(f.consumer.isPending(A), false);
  } finally { f.close(); }
});

for (const state of ["disabled", "idle", "connecting", "reconnecting", "offline"]) test(`${state} keeps bounded pre-call consent polling fallback`, async () => {
  const f = fixture();
  try {
    f.seed(); f.consumer.setRealtimeStatus({ state, generation: 0 });
    assert.equal(f.delay(), CONSENT_FALLBACK_REFRESH_MS);
    f.tick(); await settle(); assert.deepEqual(f.calls, [getECounselingListMyConsentsQueryKey(A)[0]], "Unchanged consent polling adds no workspace loop");
  } finally { f.close(); }
});

test("initial ready and reconnect refresh once each; live cadence is slower", async () => {
  const f = fixture();
  try {
    f.seed(); f.consumer.setRealtimeStatus({ state: "live", generation: 1 }); await settle();
    assert.equal(f.calls.length, 2); assert.equal(f.delay(), CONSENT_LIVE_SAFETY_REFRESH_MS);
    f.consumer.setRealtimeStatus({ state: "live", generation: 1 }); await settle(); assert.equal(f.calls.length, 2);
    f.consumer.setRealtimeStatus({ state: "reconnecting", generation: 1 }); assert.equal(f.delay(), CONSENT_FALLBACK_REFRESH_MS);
    f.consumer.setRealtimeStatus({ state: "live", generation: 2 }); await settle(); assert.equal(f.calls.length, 4);
    assert.equal(f.timers.size, 1);
  } finally { f.close(); }
});

test("safety polling refreshes workspace only when canonical consent items actually change", async () => {
  let effective = true;
  const f = fixture("COUNSELOR", (key) => key[0].endsWith("/consents") ? { data: { items: [{ id: A, effective }] } } : { authoritative: "workspace" });
  try {
    f.seed();
    f.client.setQueryData(getECounselingListAssignedConsentsQueryKey(A), { data: { items: [{ id: A, effective }] } });
    f.tick(); await settle(); assert.equal(f.calls.length, 1, "Unchanged list does not refresh workspace");
    effective = false;
    f.tick(); await settle();
    assert.equal(f.calls.length, 3, "Changed authoritative consent list refreshes its workspace once");
    assert.equal(f.calls[2], getECounselingGetAssignedWorkspaceQueryKey(A)[0]);
  } finally { f.close(); }
});

for (const boundary of ["hidden", "offline"]) test(`${boundary} issues no freshness requests and recovers on return`, async () => {
  const f = fixture();
  try {
    f.seed();
    if (boundary === "hidden") f.document.visibilityState = "hidden";
    else f.navigator.onLine = false;
    f.consumer.requestRefresh(A); f.tick(); await settle(); assert.equal(f.calls.length, 0);
    assert.equal(f.consumer.isPending(A), true);
    f.document.visibilityState = "visible"; f.navigator.onLine = true;
    (boundary === "hidden" ? f.document : f.window).dispatchEvent(new Event(boundary === "hidden" ? "visibilitychange" : "online"));
    await settle(); assert.equal(f.calls.length, 2); assert.equal(f.consumer.isPending(A), false);
  } finally { f.close(); }
});

test("focus reconciles without depending on a Daily call", async () => {
  const f = fixture();
  try { f.seed(); f.window.dispatchEvent(new Event("focus")); await settle(); assert.equal(f.calls.length, 2); }
  finally { f.close(); }
});

test("unmount removes timers/listeners and prevents queued or trailing reads", async () => {
  const held = [];
  const f = fixture("STUDENT", () => new Promise((resolve) => held.push(resolve)));
  try {
    f.seed(); f.consumer.requestRefresh(A); await settle(); f.consumer.requestRefresh(A);
    f.consumer.stop(); assert.equal(f.timers.size, 0);
    f.window.dispatchEvent(new Event("focus")); f.document.dispatchEvent(new Event("visibilitychange"));
    for (const resolve of held) resolve({ done: true });
    await settle(); assert.equal(f.calls.length, 2); assert.equal(f.consumer.isPending(A), false);
  } finally { f.close(); }
});

test("failed HTTP reconciliation preserves only an unconfirmed prior approval", async () => {
  const f = fixture("COUNSELOR", () => { throw new Error("synthetic offline read"); });
  try {
    f.seed(); f.consumer.requestRefresh(A); await settle();
    const state = f.client.getQueryState(getECounselingListAssignedConsentsQueryKey(A));
    assert.equal(state.status, "error"); assert.equal(state.isInvalidated, true);
    assert.ok(state.data, "Last confirmed data is retained but cannot authorize Start");
  } finally { f.close(); }
});

for (const role of ["GUIDANCE_SERVICES_STAFF", "IT_ADMIN"]) test(`${role} cannot activate a consent endpoint`, async () => {
  const f = fixture(role);
  try {
    for (const key of [...keys.STUDENT, ...keys.COUNSELOR]) { f.client.setQueryData(key(A), "unrelated"); f.observer(key(A)); }
    f.consumer.requestRefresh(A); f.consumer.reconcile(); await settle(); assert.deepEqual(f.calls, []);
  } finally { f.close(); }
});

test("unknown or malformed appointments never allocate a query or trigger a fetch", async () => {
  const f = fixture();
  try {
    f.seed();
    for (const id of [B, "not-an-id", 1, null]) f.consumer.requestRefresh(id);
    await settle(); assert.deepEqual(f.calls, []); assert.equal(f.client.getQueryCache().getAll().length, 2);
  } finally { f.close(); }
});

test("account ownership discards old protected queries before a new account can receive hints", async () => {
  const f = fixture();
  const ownership = createAccountOwnership({ isSessionQuery: (query) => query.queryKey[0] === getAuthGetSessionQueryKey()[0] }); const detach = ownership.attach(f.client);
  try {
    f.client.setQueryData(getAuthGetSessionQueryKey(), { data: { user: { id: A }, session: { id: "session-A" } } });
    f.seed(); f.consumer.stop();
    f.client.setQueryData(getAuthGetSessionQueryKey(), { data: { user: { id: B }, session: { id: "session-B" } } });
    assert.equal(f.client.getQueryState(getECounselingListMyConsentsQueryKey(A)), undefined);
    f.consumer.requestRefresh(A); await settle(); assert.deepEqual(f.calls, []);
  } finally { detach(); f.close(); }
});

test("a stopped coordinator cannot invalidate the next account's data after an old read settles", async () => {
  const held = [];
  const f = fixture("COUNSELOR", () => new Promise((resolve) => held.push(resolve)));
  const ownership = createAccountOwnership({ isSessionQuery: (query) => query.queryKey[0] === getAuthGetSessionQueryKey()[0] });
  const detach = ownership.attach(f.client);
  try {
    f.client.setQueryData(getAuthGetSessionQueryKey(), { data: { user: { id: A }, session: { id: "session-A" } } });
    f.seed(); f.consumer.requestRefresh(A); await settle(); f.consumer.requestRefresh(A);
    f.consumer.stop();
    f.client.setQueryData(getAuthGetSessionQueryKey(), { data: { user: { id: B }, session: { id: "session-B" } } });
    const key = getECounselingListAssignedConsentsQueryKey(A);
    f.client.setQueryData(key, { data: { items: [{ owner: "new confirmed account" }] } });
    for (const resolve of held) resolve({ data: { items: [{ owner: "old account response" }] } });
    await settle();
    assert.equal(f.client.getQueryState(key).isInvalidated, false);
    assert.equal(f.client.getQueryData(key).data.items[0].owner, "new confirmed account");
    assert.equal(f.calls.length, 2);
  } finally { detach(); f.close(); }
});
