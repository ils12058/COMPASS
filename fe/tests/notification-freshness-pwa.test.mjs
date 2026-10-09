import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

import { initialPushState } from "../src/features/notifications/browser-push-capability.ts";
import { disableBrowserPush, enableBrowserPush } from "../src/features/notifications/browser-push-actions.ts";
import { NOTIFICATION_FALLBACK_REFRESH_MS, startNotificationFreshness } from "../src/features/notifications/notification-freshness.tsx";
import manifest from "../src/app/manifest.ts";

test("foreground notification state refreshes promptly and recovers after focus/network changes", async () => {
  const document = new EventTarget();
  document.visibilityState = "visible";
  const window = new EventTarget();
  let tick;
  let cleared = false;
  window.setInterval = (callback, delay) => { assert.equal(delay, NOTIFICATION_FALLBACK_REFRESH_MS); tick = callback; return 1; };
  window.clearInterval = () => { cleared = true; };
  const navigator = { onLine: true };
  const keys = [];
  const queryClient = { invalidateQueries: ({ queryKey }) => { keys.push(queryKey[0]); return Promise.resolve(); } };
  const { stop } = startNotificationFreshness(queryClient, { document, window, navigator });

  tick();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(keys.sort(), ["/api/v1/notifications", "/api/v1/notifications/unread-count"]);
  keys.length = 0;
  document.visibilityState = "hidden";
  tick();
  assert.equal(keys.length, 0);
  document.visibilityState = "visible";
  document.dispatchEvent(new Event("visibilitychange"));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(keys.length, 2);
  keys.length = 0;
  navigator.onLine = false;
  tick();
  assert.equal(keys.length, 0);
  navigator.onLine = true;
  window.dispatchEvent(new Event("online"));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(keys.length, 2);
  stop();
  keys.length = 0;
  tick();
  window.dispatchEvent(new Event("focus"));
  assert.equal(keys.length, 0);
  assert.equal(cleared, true);
});

test("Apple browser guidance, installed mode, support and denial are distinct", () => {
  assert.equal(initialPushState({ appleMobile: true, standalone: false, supported: true, permission: "default" }), "install-required");
  assert.equal(initialPushState({ appleMobile: true, standalone: true, supported: true, permission: "default" }), "available");
  assert.equal(initialPushState({ appleMobile: false, standalone: false, supported: true, permission: "default" }), "available");
  assert.equal(initialPushState({ appleMobile: false, standalone: false, supported: false, permission: "default" }), "unsupported");
  assert.equal(initialPushState({ appleMobile: false, standalone: false, supported: true, permission: "denied" }), "blocked");
});

test("permission is requested only by Enable and registration belongs to this device", async () => {
  let prompts = 0;
  let registrations = 0;
  let removals = 0;
  let unsubscribed = 0;
  const subscription = {
    endpoint: "https://fcm.googleapis.com/fcm/send/test",
    toJSON: () => ({ keys: { p256dh: "public", auth: "auth" } }),
    unsubscribe: async () => { unsubscribed += 1; return true; },
  };
  const registration = { pushManager: { getSubscription: async () => subscription } };
  const actions = {
    permission: "default", publicKey: "cHVibGlj",
    requestPermission: async () => { prompts += 1; return "granted"; },
    registration: async () => registration,
    register: async (value) => { registrations += 1; assert.equal(value.endpoint, subscription.endpoint); },
  };
  assert.equal(prompts, 0, "merely rendering or checking capability never asks permission");
  assert.equal(await enableBrowserPush(actions), "enabled");
  assert.equal(prompts, 1);
  assert.equal(registrations, 1);
  assert.equal(await enableBrowserPush({ ...actions, permission: "denied" }), "blocked");
  assert.equal(prompts, 1, "browser denial is never reprompted");
  await disableBrowserPush({ registration: actions.registration, remove: async ({ endpoint }) => { assert.equal(endpoint, subscription.endpoint); removals += 1; } });
  assert.equal(removals, 1);
  assert.equal(unsubscribed, 1);
});

test("PWA opens at a public entry and the worker keeps only an offline shell", async () => {
  assert.equal(manifest().start_url, "/");
  assert.equal(manifest().display, "standalone");
  const source = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");
  const listeners = {};
  const cache = { add: async () => undefined, match: async () => new Response("offline") };
  const shown = [];
  const opened = [];
  const context = {
    self: { addEventListener: (name, handler) => { listeners[name] = handler; }, skipWaiting() {}, location: { origin: "https://compass.example" }, registration: { showNotification: async (title, options) => { shown.push({ title, options }); } }, clients: { claim: async () => undefined, matchAll: async () => [], openWindow: async (url) => { opened.push(url); } } },
    caches: { open: async () => cache, keys: async () => [], delete: async () => true },
    fetch: async () => { throw new Error("offline"); },
    Response,
    URL,
    Set,
    Promise,
  };
  vm.runInNewContext(source, context);
  assert.ok(listeners.fetch);
  assert.ok(listeners.push);
  const requests = [];
  listeners.fetch({ request: { mode: "navigate", url: "https://example.test/portal" }, respondWith: (result) => requests.push(result) });
  assert.equal(requests.length, 1);
  const apiRequests = [];
  listeners.fetch({ request: { mode: "cors", url: "https://example.test/api/v1/notifications" }, respondWith: (result) => apiRequests.push(result) });
  assert.equal(apiRequests.length, 0, "authenticated API requests are never intercepted");
  const pending = [];
  listeners.push({ data: { json: () => ({ body: "Private counseling details", path: "https://evil.example" }) }, waitUntil: (promise) => pending.push(promise) });
  await Promise.all(pending);
  assert.deepEqual({ title: shown[0].title, body: shown[0].options.body }, { title: "COMPASS", body: "You have a new notification." });
  listeners.push({ data: { json: () => ({ body: "You have an appointment update." }) }, waitUntil: (promise) => pending.push(promise) });
  await Promise.all(pending);
  assert.equal(shown[1].options.body, "You have an appointment update.");
  const clickPromises = [];
  listeners.notificationclick({ notification: { close() {}, data: { path: "https://evil.example" } }, waitUntil: (promise) => clickPromises.push(promise) });
  await Promise.all(clickPromises);
  assert.deepEqual(opened, ["https://compass.example/portal/notifications"]);
});
