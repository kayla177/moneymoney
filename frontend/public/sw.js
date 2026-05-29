// Minimal service worker so the app is installable ("Add to Home Screen").
// Network-first: always try the network, fall back to cache when offline. We deliberately
// avoid aggressive caching of API responses so spend data is never stale.
const CACHE = "moneymoney-v1";
const SHELL = ["/", "/index.html"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Never cache API calls.
  if (new URL(request.url).pathname.startsWith("/api")) return;
  event.respondWith(
    fetch(request).catch(() => caches.match(request).then((r) => r || caches.match("/")))
  );
});
