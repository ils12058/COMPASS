import assert from "node:assert/strict";
import { test } from "node:test";
import { QueryClient, QueryObserver } from "@tanstack/react-query";

import { ECounselingConsentFreshness } from "../src/features/ecounseling/consent-freshness.ts";
import { getECounselingAccess } from "../src/features/ecounseling/ecounseling-access.ts";
import { sessionRefreshInterval } from "../src/features/ecounseling/ecounseling-shared.ts";
import { parseServerFrame } from "../src/features/realtime/realtime-protocol.ts";
import { getECounselingGetMyWorkspaceQueryKey, getECounselingGetAssignedWorkspaceQueryKey, getECounselingListMyConsentsQueryKey, getECounselingListAssignedConsentsQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";

const A = "a0000000-0000-4000-8000-000000000001";
const B = "b0000000-0000-4000-8000-000000000001";
const settle = () => new Promise((resolve) => setImmediate(resolve));
const workspaceKey = { STUDENT: getECounselingGetMyWorkspaceQueryKey, COUNSELOR: getECounselingGetAssignedWorkspaceQueryKey };
const consentKey = { STUDENT: getECounselingListMyConsentsQueryKey, COUNSELOR: getECounselingListAssignedConsentsQueryKey };

function workspace(status = "NOT_STARTED", artifact = null, joinable = true) {
  const base = { consent_status: "APPROVED", capture_status: status, artifact_status: artifact, artifact_available: artifact === "STORED", artifact_disposed_at: artifact === "DISPOSED" ? "2026-10-14T00:00:00Z" : null };
  return { data: { provider_readiness: { join_allowed: joinable }, media: { media_policy_version: 2, recording: base, transcription: { ...base, capture_status: "NOT_STARTED", artifact_status: null, artifact_available: false, storage_consent_status: "NOT_REQUESTED", storage_enabled: false } } } };
}

function fixture({ role = "STUDENT", viewerOnly = false, fetch } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const document = new EventTarget(); document.visibilityState = "visible";
  const window = new EventTarget(); const timers = new Map(); let timerId = 0;
  window.setInterval = (callback, ms) => { timers.set(++timerId, { callback, ms }); return timerId; };
  window.clearInterval = (id) => timers.delete(id);
  const navigator = { onLine: true };
  const capabilities = role === "STUDENT" ? ["ecounseling.view_self", ...(viewerOnly ? [] : ["ecounseling.consent_self"])] : ["ecounseling.view_assigned", ...(viewerOnly ? [] : ["ecounseling.manage_media_assigned"])];
  const consumer = new ECounselingConsentFreshness(client, getECounselingAccess({ role, capabilities }));
  const calls = []; const releases = [];
  let current = workspace();
  const observe = (key, enabled = true) => {
    const observer = new QueryObserver(client, { queryKey: key, enabled, queryFn: async () => {
      calls.push(key[0]);
      return fetch ? fetch(key, calls.length) : key[0].endsWith("/consents") ? { data: { items: [] } } : current;
    } });
    const release = observer.subscribe(() => {});
    releases.push(release); return release;
  };
  const seed = (id = A, { active = true, enabled = true, value = workspace() } = {}) => {
    client.setQueryData(workspaceKey[role](id), value);
    client.setQueryData(consentKey[role](id), { data: { items: [] } });
    if (active) { observe(workspaceKey[role](id), enabled); observe(consentKey[role](id), enabled); }
  };
  consumer.start({ document, window, navigator });
  return {
    client, consumer, calls, document, window, navigator, timers, observe, seed,
    setCurrent: (value) => { current = value; },
    tick: () => { for (const timer of [...timers.values()]) timer.callback(); },
    close: () => { consumer.stop(); for (const release of releases) release(); client.clear(); },
  };
}

test("media contract is closed, canonical, versioned and content-free alongside all existing hints", () => {
  const frame = { v: 1, type: "ecounseling.media.changed", appointment_id: A };
  assert.deepEqual(parseServerFrame(JSON.stringify(frame)), { kind: "event", event: frame });
  for (const field of ["status", "student_id", "room_name", "instance_id", "session_id", "artifact_id", "url", "object_key", "consent", "error", "duration", "transcript"]) assert.equal(parseServerFrame(JSON.stringify({ ...frame, [field]: "private" })), null);
  for (const id of [undefined, null, "", "bad", A.toUpperCase(), 1, {}, A.replaceAll("-", "")]) assert.equal(parseServerFrame(JSON.stringify({ ...frame, appointment_id: id })), null);
  for (const v of [0, 2, true, "1", null]) assert.equal(parseServerFrame(JSON.stringify({ ...frame, v })), null);
  assert.equal(parseServerFrame(JSON.stringify({ ...frame, type: "ecounseling.recording.changed" })), null);
  assert.equal(parseServerFrame(JSON.stringify({ ...frame, private: "x".repeat(600) })), null);
  for (const existing of [{ v: 1, type: "notifications.changed" }, { v: 1, type: "messages.thread_changed", thread_id: A }, { v: 1, type: "ecounseling.consent.changed", appointment_id: A }]) assert.equal(parseServerFrame(JSON.stringify(existing))?.kind, "event");
});

for (const role of ["STUDENT", "COUNSELOR"]) test(`${role} media hint reads only exact workspace and never consent or another appointment`, async () => {
  const f = fixture({ role });
  try {
    f.seed(); f.seed(B);
    const opposite = role === "STUDENT" ? "COUNSELOR" : "STUDENT";
    f.client.setQueryData(workspaceKey[opposite](A), workspace()); f.observe(workspaceKey[opposite](A));
    f.consumer.requestMediaRefresh(A);
    assert.equal(f.consumer.isWorkspacePending(A), true);
    assert.equal(f.consumer.isPending(A), false, "Media hint does not create/lift a consent fence");
    await settle();
    assert.deepEqual(f.calls, [workspaceKey[role](A)[0]]);
    assert.equal(f.client.getQueryState(consentKey[role](A)).isInvalidated, false);
    assert.equal(f.client.getQueryState(workspaceKey[role](B)).isInvalidated, false);
    assert.equal(f.consumer.isWorkspacePending(A), false);
  } finally { f.close(); }
});

for (const role of ["STUDENT", "COUNSELOR"]) test(`${role} read-only viewer still receives workspace refresh without consent management`, async () => {
  const f = fixture({ role, viewerOnly: true });
  try { f.seed(); f.consumer.requestMediaRefresh(A); await settle(); assert.deepEqual(f.calls, [workspaceKey[role](A)[0]]); }
  finally { f.close(); }
});

test("inactive/disabled workspaces become stale and unknown appointments allocate no query", async () => {
  const f = fixture();
  try {
    f.seed(A, { active: false }); f.seed(B, { enabled: false });
    f.consumer.requestMediaRefresh(A); f.consumer.requestMediaRefresh(B);
    f.consumer.requestMediaRefresh("c0000000-0000-4000-8000-000000000001"); f.consumer.requestMediaRefresh("bad");
    await settle(); assert.deepEqual(f.calls, []);
    assert.equal(f.client.getQueryCache().getAll().length, 4);
    for (const id of [A, B]) assert.equal(f.client.getQueryState(workspaceKey.STUDENT(id)).isInvalidated, true);
  } finally { f.close(); }
});

test("page plus persistent-call observers and a burst cause one workspace read", async () => {
  const f = fixture();
  try {
    f.seed(); f.observe(workspaceKey.STUDENT(A)); f.consumer.setActiveCall(A);
    for (let i = 0; i < 30; i++) f.consumer.requestMediaRefresh(A);
    await settle(); assert.deepEqual(f.calls, [workspaceKey.STUDENT(A)[0]]);
    assert.equal(f.timers.size, 2, "One consent clock and one appointment workspace clock");
  } finally { f.close(); }
});

test("media hints while fetching queue one trailing read without canceling", async () => {
  const held = []; const f = fixture({ fetch: () => new Promise((resolve) => held.push(resolve)) });
  try {
    f.seed(); f.consumer.requestMediaRefresh(A); await settle();
    for (let i = 0; i < 30; i++) f.consumer.requestMediaRefresh(A);
    held.shift()(workspace("START_REQUESTED")); await settle();
    assert.equal(f.calls.length, 2); assert.equal(f.consumer.isWorkspacePending(A), true);
    held.shift()(workspace("ACTIVE")); await settle();
    assert.equal(f.consumer.isWorkspacePending(A), false); assert.equal(f.calls.length, 2);
  } finally { f.close(); }
});

test("safety clocks during a slow canonical read do not generate endless trailing requests", async () => {
  const held = []; const f = fixture({ fetch: () => new Promise((resolve) => held.push(resolve)) });
  try {
    f.seed(); f.consumer.requestMediaRefresh(A); await settle();
    for (let i = 0; i < 10; i++) f.tick();
    await settle(); assert.equal(f.calls.length, 1);
    held.shift()(workspace("ACTIVE")); await settle();
    assert.equal(f.calls.length, 1); assert.equal(f.consumer.isWorkspacePending(A), false);
  } finally { f.close(); }
});

test("first media hint during an older external read requires fresh trailing truth", async () => {
  const held = []; const f = fixture({ fetch: () => new Promise((resolve) => held.push(resolve)) });
  try {
    f.seed(); const old = f.client.refetchQueries({ queryKey: workspaceKey.STUDENT(A) }); await settle();
    f.consumer.requestMediaRefresh(A); await settle(); assert.equal(f.calls.length, 1);
    held.shift()(workspace()); await old; await settle();
    assert.equal(f.calls.length, 2); assert.equal(f.consumer.isWorkspacePending(A), true);
    held.shift()(workspace("STOP_REQUESTED")); await settle();
    assert.equal(f.consumer.isWorkspacePending(A), false);
  } finally { f.close(); }
});

test("workspace-only media reconciliation never bypasses an outstanding consent fence", async () => {
  const held = []; const f = fixture({ role: "COUNSELOR", fetch: (key) => new Promise((resolve) => held.push({ key, resolve })) });
  try {
    f.seed(); f.consumer.requestRefresh(A); await settle();
    f.consumer.requestMediaRefresh(A);
    held.find((item) => !item.key[0].endsWith("/consents")).resolve(workspace("ACTIVE"));
    await settle(); assert.equal(f.consumer.isPending(A), true);
    held.find((item) => item.key[0].endsWith("/consents")).resolve({ data: { items: [{ effective: false, withdrawn_at: "2026-10-14T00:00:00Z" }] } });
    await settle(); assert.equal(f.consumer.isPending(A), true, "Fence remains until joint work settles");
    assert.equal(f.calls.filter((key) => key.endsWith("/consents")).length, 1, "Media hint itself adds no consent read");
    held.at(-1).resolve(workspace("STOP_REQUESTED")); await settle();
    assert.equal(f.consumer.isPending(A), false);
  } finally { f.close(); }
});

for (const state of ["disabled", "idle", "connecting", "reconnecting", "offline"]) test(`${state} retains 7-second fallback for a joinable pre-call workspace`, async () => {
  const f = fixture();
  try {
    f.seed(); f.consumer.setRealtimeStatus({ state, generation: 0 });
    assert.deepEqual([...f.timers.values()].map((item) => item.ms), [7000, 7000]);
    f.setCurrent(workspace("START_REQUESTED")); f.tick(); await settle();
    assert.equal(f.calls.filter((key) => key === workspaceKey.STUDENT(A)[0]).length, 1);
    assert.equal(f.client.getQueryData(workspaceKey.STUDENT(A)).data.media.recording.capture_status, "START_REQUESTED");
  } finally { f.close(); }
});

for (const status of ["START_REQUESTED", "STOP_REQUESTED", "ERROR"]) test(`${status} keeps fast safety polling even on a healthy socket`, () => {
  const f = fixture();
  try {
    f.seed(A, { value: workspace(status) }); f.consumer.setRealtimeStatus({ state: "live", generation: 0 });
    assert.deepEqual([...f.timers.values()].map((item) => item.ms).sort((a, b) => a-b), [7000, 60000]);
    assert.equal(sessionRefreshInterval(false, workspace(status).data.media, true), 7000);
  } finally { f.close(); }
});

for (const [status, artifact] of [["ACTIVE", null], ["READY", "PENDING"], ["READY", "PROCESSING"], ["READY", "FAILED"]]) test(`${status}/${artifact} uses slower live safety, preserves unavailable fallback`, () => {
  const f = fixture();
  try {
    f.seed(A, { value: workspace(status, artifact) }); f.consumer.setRealtimeStatus({ state: "live", generation: 0 });
    assert.deepEqual([...f.timers.values()].map((item) => item.ms), [60000, 60000]);
    f.consumer.setRealtimeStatus({ state: "reconnecting", generation: 0 });
    assert.deepEqual([...f.timers.values()].map((item) => item.ms), [7000, 7000]);
  } finally { f.close(); }
});

test("settled historical and inactive cached appointments have no media polling", () => {
  const f = fixture();
  try {
    f.seed(A, { value: workspace("READY", "STORED", false) }); f.seed(B, { active: false, value: workspace("STOP_REQUESTED") });
    f.consumer.setRealtimeStatus({ state: "live", generation: 0 });
    assert.equal(f.timers.size, 1, "Only existing consent timer; no historical media clock");
    f.consumer.setActiveCall(A); assert.equal(f.timers.size, 2);
    f.consumer.setActiveCall(null); assert.equal(f.timers.size, 1);
  } finally { f.close(); }
});

test("legacy transcription STOPPED remains an unresolved fast safety refresh while live", () => {
  const value = workspace("NOT_STARTED", null, false);
  value.data.media.transcription.capture_status = "STOPPED";
  assert.equal(sessionRefreshInterval(false, value.data.media, true), 7000);
});

for (const recovery of ["visibility", "online", "focus"]) test(`${recovery} recovery reconciles pending media without hidden/offline HTTP`, async () => {
  const f = fixture();
  try {
    f.seed(); if (recovery === "online") f.navigator.onLine = false; else f.document.visibilityState = "hidden";
    f.consumer.requestMediaRefresh(A); f.tick(); await settle(); assert.deepEqual(f.calls, []);
    assert.equal(f.consumer.isWorkspacePending(A), true);
    f.navigator.onLine = true; f.document.visibilityState = "visible";
    (recovery === "visibility" ? f.document : f.window).dispatchEvent(new Event(recovery === "visibility" ? "visibilitychange" : recovery));
    await settle(); assert.equal(f.calls.filter((key) => key === workspaceKey.STUDENT(A)[0]).length, 1);
    assert.equal(f.consumer.isWorkspacePending(A), false);
  } finally { f.close(); }
});

test("initial ready/reconnect heal missed media once per advanced generation", async () => {
  const f = fixture();
  try {
    f.seed(); f.consumer.setRealtimeStatus({ state: "live", generation: 1 }); await settle();
    f.consumer.setRealtimeStatus({ state: "live", generation: 1 }); await settle();
    assert.equal(f.calls.filter((key) => key === workspaceKey.STUDENT(A)[0]).length, 1);
    f.consumer.setRealtimeStatus({ state: "live", generation: 2 }); await settle();
    assert.equal(f.calls.filter((key) => key === workspaceKey.STUDENT(A)[0]).length, 2);
  } finally { f.close(); }
});

test("failed canonical workspace refresh retains an error and does not patch media status", async () => {
  const f = fixture({ fetch: async () => { throw new Error("synthetic read failure"); } });
  try {
    f.seed(); f.consumer.requestMediaRefresh(A); await settle();
    assert.equal(f.client.getQueryState(workspaceKey.STUDENT(A)).status, "error");
    assert.equal(f.client.getQueryData(workspaceKey.STUDENT(A)).data.media.recording.capture_status, "NOT_STARTED");
    assert.equal(f.client.getQueryState(consentKey.STUDENT(A)).status, "success");
  } finally { f.close(); }
});

test("Daily/mutation refresh waits for the same coalesced workspace reconciliation", async () => {
  const held = []; const f = fixture({ fetch: () => new Promise((resolve) => held.push(resolve)) });
  try {
    f.seed(); let finished = false;
    const refreshing = f.consumer.refreshWorkspace(A).then(() => { finished = true; });
    f.consumer.requestMediaRefresh(A); await settle(); assert.equal(f.calls.length, 1); assert.equal(finished, false);
    held.shift()(workspace("ACTIVE")); await refreshing;
    assert.equal(finished, true); assert.equal(f.calls.length, 1);
  } finally { f.close(); }
});

test("stop/unmount cancels media timers, pending trails and late previous-account cache work", async () => {
  const held = []; const f = fixture({ fetch: () => new Promise((resolve) => held.push(resolve)) });
  try {
    f.seed(); f.consumer.requestMediaRefresh(A); await settle(); f.consumer.requestMediaRefresh(A);
    f.consumer.stop(); assert.equal(f.timers.size, 0);
    f.client.clear(); f.client.setQueryData(workspaceKey.STUDENT(A), workspace("READY", "DISPOSED"));
    held.shift()(workspace("ACTIVE")); await settle();
    assert.equal(f.calls.length, 1); assert.equal(f.client.getQueryState(workspaceKey.STUDENT(A)).isInvalidated, false);
    assert.equal(f.client.getQueryData(workspaceKey.STUDENT(A)).data.media.recording.artifact_status, "DISPOSED");
  } finally { f.close(); }
});
