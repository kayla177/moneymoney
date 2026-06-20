// Service worker for the installable PWA ("Add to Home Screen").
//
// Strategy, tuned for a slow/cold backend (Oracle micro VM over Tailscale):
//   - App shell + static assets: CACHE-FIRST (stale-while-revalidate). The app opens
//     instantly from cache and never waits on the server to render. Safe because Vite
//     content-hashes asset filenames, so a changed bundle has a new URL — the cached
//     copy can never be stale-but-wrong.
//   - Navigations (index.html): serve cached shell immediately, refresh in background so
//     a new deploy is picked up on the next open.
//   - API calls: NETWORK-ONLY so spend data is never stale, but with a timeout so a hung
//     VM fails fast instead of leaving the UI spinning ("server stopped responding").
const CACHE = "moneymoney-v2";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg"];
const API_TIMEOUT_MS = 8000;

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

// Cache-first with a background refresh. Returns whatever is cached immediately (instant
// open), and updates the cache from the network in the background for next time.
function staleWhileRevalidate(request) {
  return caches.open(CACHE).then((cache) =>
    cache.match(request).then((cached) => {
      const network = fetch(request)
        .then((resp) => {
          // Only cache successful, basic (same-origin) GETs.
          if (resp && resp.ok && resp.type === "basic") {
            cache.put(request, resp.clone());
          }
          return resp;
        })
        .catch(() => cached); // offline: fall back to whatever we have
      return cached || network;
    })
  );
}

// Network-only with a timeout, so a slow/dead VM doesn't hang the UI.
function networkWithTimeout(request) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  return fetch(request, { signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // POST/PATCH go straight to the network

  const url = new URL(request.url);

  // API: must be fresh. Bound it with a timeout so the app fails fast, not forever.
  if (url.pathname.startsWith("/api")) {
    event.respondWith(networkWithTimeout(request));
    return;
  }

  // Navigations: serve the cached shell instantly, refresh in the background.
  if (request.mode === "navigate") {
    event.respondWith(
      staleWhileRevalidate(request).then(
        (resp) => resp || caches.match("/index.html")
      )
    );
    return;
  }

  // Everything else (hashed JS/CSS, icons, manifest): cache-first.
  event.respondWith(staleWhileRevalidate(request));
});
