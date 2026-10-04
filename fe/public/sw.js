/* COMPASS intentionally does not cache authenticated pages, API data, or forms. */
const OFFLINE_CACHE = "compass-offline-v1";
const DESTINATION = "/portal/notifications";
const SAFE_BODIES = new Set([
  "You have a new Call Slip.",
  "You have a Call Slip update.",
  "You have an appointment update.",
  "Your Good Moral request has an update.",
  "You have a new request to review in COMPASS.",
  "Your COMPASS account security changed.",
]);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(OFFLINE_CACHE).then((cache) => cache.add("/offline.html")));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(Promise.all([
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("compass-offline-") && key !== OFFLINE_CACHE).map((key) => caches.delete(key)))),
    self.clients.claim(),
  ]));
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;
  event.respondWith(fetch(event.request).catch(async () => {
    const cached = await (await caches.open(OFFLINE_CACHE)).match("/offline.html");
    return cached || Response.error();
  }));
});

self.addEventListener("push", (event) => {
  let body = "You have a new notification.";
  try {
    const value = event.data?.json();
    if (value && SAFE_BODIES.has(value.body)) body = value.body;
  } catch { /* An unrecognized payload remains generic. */ }
  event.waitUntil(self.registration.showNotification("COMPASS", {
    body,
    icon: "/brand/compass-192.png",
    badge: "/brand/compass-192.png",
    data: { path: DESTINATION },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil((async () => {
    const destination = new URL(DESTINATION, self.location.origin).href;
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const current = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (current) {
      await current.navigate(destination);
      return current.focus();
    }
    return self.clients.openWindow(destination);
  })());
});
