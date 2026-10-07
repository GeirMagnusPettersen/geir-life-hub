// Minimal service worker: enables installability and a basic offline
// app-shell cache. Intentionally simple for this skeleton phase; a real
// caching/update strategy can replace this later (e.g. Workbox).
//
// Bump CACHE_NAME whenever this file changes so old caches are evicted.
const CACHE_NAME = "lifehub-shell-v2";
const APP_SHELL = ["/", "/index.html", "/manifest.json", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  // Never intercept cross-origin requests (e.g. the backend API running on
  // a different port/host). Caching those here could make login/API calls
  // appear to hang or return stale data, and offline support for them is
  // not useful anyway.
  if (url.origin !== self.location.origin) {
    return;
  }

  // Navigation requests (loading index.html) and the HTML file itself must
  // always prefer the network so a rebuilt app (new hashed asset filenames)
  // is picked up immediately. Falling back to a stale cached index.html can
  // reference JS/CSS bundles that no longer exist on the server, leaving
  // the app stuck on its initial loading screen forever. Only fall back to
  // the cache when the network is unavailable (offline).
  if (request.mode === "navigate" || url.pathname === "/" || url.pathname === "/index.html") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          void caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached ?? caches.match("/index.html"))),
    );
    return;
  }

  // Other same-origin assets (hashed JS/CSS, manifest, icons) are safe to
  // serve cache-first, since content changes produce new filenames.
  event.respondWith(
    caches.match(request).then((cached) => cached ?? fetch(request)),
  );
});
