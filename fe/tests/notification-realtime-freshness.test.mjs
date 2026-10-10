import assert from "node:assert/strict";
import { test } from "node:test";

import { QueryClient } from "@tanstack/react-query";
import {
  NOTIFICATION_FALLBACK_REFRESH_MS,
  NOTIFICATION_LIVE_SAFETY_REFRESH_MS,
  startNotificationFreshness,
} from "../src/features/notifications/notification-freshness.tsx";
import { parseServerFrame } from "../src/features/realtime/realtime-protocol.ts";
import {
  getNotificationsListMineQueryKey,
  getNotificationsGetUnreadCountQueryKey,
} from "../src/lib/api/generated/notifications/notifications.ts";

const settle = () => new Promise((resolve) => setImmediate(resolve));
const expectedKeys = ["/api/v1/notifications/unread-count", "/api/v1/notifications"];

function fixture(invalidate) {
  const document = new EventTarget();
  document.visibilityState = "visible";
  const window = new EventTarget();
  const timers = new Map();
  let timerId = 0;
  window.setInterval = (callback, ms) => { timers.set(++timerId, { callback, ms }); return timerId; };
  window.clearInterval = (id) => timers.delete(id);
  const navigator = { onLine: true };
  const keys = [];
  const queryClient = { invalidateQueries: ({ queryKey }) => {
    keys.push(queryKey[0]);
    return invalidate?.() ?? Promise.resolve();
  } };
  const consumer = startNotificationFreshness(queryClient, { document, window, navigator });
  return {
    document, window, navigator, timers, keys, consumer,
    tick: () => [...timers.values()][0]?.callback(),
    delay: () => [...timers.values()][0]?.ms,
  };
}

for (const state of ["disabled", "idle", "connecting", "reconnecting"]) {
  test(`${state} keeps the 8-second polling fallback, including server-disabled transport`, async () => {
    const f = fixture();
    try {
      f.consumer.setRealtimeStatus({ state, generation: 0 });
      assert.equal(f.delay(), NOTIFICATION_FALLBACK_REFRESH_MS);
      f.tick();
      await settle();
      assert.deepEqual(f.keys, expectedKeys);
    } finally { f.consumer.stop(); }
  });
}

test("live uses a 60-second safety poll, and failure restores the 8-second fallback", async () => {
  const f = fixture();
  try {
    f.consumer.setRealtimeStatus({ state: "live", generation: 1 });
    await settle();
    assert.deepEqual(f.keys, expectedKeys, "ready reconciles immediately");
    assert.equal(f.delay(), NOTIFICATION_LIVE_SAFETY_REFRESH_MS);
    assert.equal(f.timers.size, 1);
    f.keys.length = 0;
    f.tick();
    await settle();
    assert.deepEqual(f.keys, expectedKeys, "live still polls");
    f.consumer.setRealtimeStatus({ state: "reconnecting", generation: 1 });
    assert.equal(f.delay(), NOTIFICATION_FALLBACK_REFRESH_MS);
    assert.equal(f.timers.size, 1);
  } finally { f.consumer.stop(); }
});

test("notification hints reconcile only the two canonical query families immediately", async () => {
  const f = fixture();
  try {
    f.consumer.requestRefresh();
    await settle();
    assert.deepEqual(f.keys, expectedKeys);
  } finally { f.consumer.stop(); }
});

test("each advanced ready generation reconciles once; repeating it causes no loop", async () => {
  const f = fixture();
  try {
    for (const generation of [1, 2]) {
      f.consumer.setRealtimeStatus({ state: "live", generation });
      await settle();
      assert.deepEqual(f.keys, expectedKeys);
      f.keys.length = 0;
      for (let i = 0; i < 5; i++) f.consumer.setRealtimeStatus({ state: "live", generation });
      await settle();
      assert.deepEqual(f.keys, []);
    }
  } finally { f.consumer.stop(); }
});

for (const hints of [1, 20]) {
  test(`${hints} hints during an active refresh collapse into one trailing reconciliation`, async () => {
    const pending = [];
    const f = fixture(() => new Promise((resolve) => pending.push(resolve)));
    try {
      f.consumer.requestRefresh();
      assert.deepEqual(f.keys, expectedKeys);
      for (let i = 0; i < hints; i++) f.consumer.requestRefresh();
      assert.equal(f.keys.length, 2, "one active reconciliation");
      pending[0]();
      await settle();
      assert.equal(f.keys.length, 2, "both query families must settle first");
      pending[1]();
      await settle();
      assert.deepEqual(f.keys, [...expectedKeys, ...expectedKeys]);
      pending.slice(2).forEach((resolve) => resolve());
      await settle();
      assert.equal(f.keys.length, 4, "no further refresh without a new signal");
    } finally { f.consumer.stop(); }
  });
}

test("a hidden hint or ready does not fetch; visible return and focus reconcile", async () => {
  const f = fixture();
  try {
    f.document.visibilityState = "hidden";
    f.consumer.requestRefresh();
    f.consumer.setRealtimeStatus({ state: "live", generation: 1 });
    f.tick();
    f.window.dispatchEvent(new Event("focus"));
    await settle();
    assert.deepEqual(f.keys, []);
    f.document.visibilityState = "visible";
    f.document.dispatchEvent(new Event("visibilitychange"));
    await settle();
    assert.deepEqual(f.keys, expectedKeys);
    f.keys.length = 0;
    f.window.dispatchEvent(new Event("focus"));
    await settle();
    assert.deepEqual(f.keys, expectedKeys);
  } finally { f.consumer.stop(); }
});

test("offline hints and polls issue no requests; online return reconciles immediately", async () => {
  const f = fixture();
  try {
    f.navigator.onLine = false;
    f.consumer.setRealtimeStatus({ state: "offline", generation: 0 });
    for (let i = 0; i < 20; i++) { f.tick(); f.consumer.requestRefresh(); }
    await settle();
    assert.deepEqual(f.keys, []);
    f.navigator.onLine = true;
    f.window.dispatchEvent(new Event("online"));
    await settle();
    assert.deepEqual(f.keys, expectedKeys);
  } finally { f.consumer.stop(); }
});

test("a trailing refresh waits until visible/online again if the active fetch settles hidden", async () => {
  const pending = [];
  const f = fixture(() => new Promise((resolve) => pending.push(resolve)));
  try {
    f.consumer.requestRefresh();
    f.consumer.requestRefresh();
    f.document.visibilityState = "hidden";
    pending.splice(0).forEach((resolve) => resolve());
    await settle();
    assert.equal(f.keys.length, 2);
    f.document.visibilityState = "visible";
    f.document.dispatchEvent(new Event("visibilitychange"));
    assert.equal(f.keys.length, 4);
    pending.splice(0).forEach((resolve) => resolve());
    await settle();
  } finally { f.consumer.stop(); }
});

test("failed HTTP reconciliation settles and still honors a pending hint", async () => {
  let resolveFirst;
  let calls = 0;
  const f = fixture(() => ++calls === 1
    ? new Promise((resolve) => { resolveFirst = resolve; })
    : Promise.reject(new Error("synthetic HTTP failure")));
  try {
    f.consumer.requestRefresh();
    f.consumer.requestRefresh();
    resolveFirst();
    await settle();
    assert.equal(f.keys.length, 4);
  } finally { f.consumer.stop(); }
});

test("cleanup removes timers/listeners and drops any trailing reconciliation", async () => {
  const pending = [];
  const f = fixture(() => new Promise((resolve) => pending.push(resolve)));
  f.consumer.requestRefresh();
  f.consumer.requestRefresh();
  f.consumer.stop();
  assert.equal(f.timers.size, 0);
  f.document.dispatchEvent(new Event("visibilitychange"));
  f.window.dispatchEvent(new Event("focus"));
  f.window.dispatchEvent(new Event("online"));
  f.consumer.requestRefresh();
  f.consumer.setRealtimeStatus({ state: "live", generation: 9 });
  pending.forEach((resolve) => resolve());
  await settle();
  assert.equal(f.keys.length, 2);
  assert.equal(f.timers.size, 0);
});

test("base list invalidation reaches cached pages without enumerating page numbers", async () => {
  const client = new QueryClient();
  const f = fixture();
  const consumer = startNotificationFreshness(client, f);
  try {
    for (const page of [1, 2]) client.setQueryData(getNotificationsListMineQueryKey({ page }), { page });
    client.setQueryData(getNotificationsGetUnreadCountQueryKey(), { unread_count: 2 });
    client.setQueryData(["unrelated"], "unchanged");
    consumer.requestRefresh();
    await settle();
    for (const page of [1, 2]) assert.equal(client.getQueryState(getNotificationsListMineQueryKey({ page })).isInvalidated, true);
    assert.equal(client.getQueryState(getNotificationsGetUnreadCountQueryKey()).isInvalidated, true);
    assert.equal(client.getQueryState(["unrelated"]).isInvalidated, false);
  } finally { consumer.stop(); f.consumer.stop(); client.clear(); }
});

test("the notification wire hint contains exactly version/type and rejects even UUID extra fields", () => {
  assert.deepEqual(parseServerFrame('{"v":1,"type":"notifications.changed"}'), {
    kind: "event", event: { v: 1, type: "notifications.changed" },
  });
  for (const field of ["notification_id", "unread_count", "title", "message", "content", "arbitrary"]) {
    assert.equal(parseServerFrame(JSON.stringify({ v: 1, type: "notifications.changed", [field]: "10000000-0000-4000-8000-000000000001" })), null);
  }
});
