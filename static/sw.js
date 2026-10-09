const CACHE_NAME = "plantdex-cache-v1";
const STATIC_ASSETS = [
  "/",
  "/static/css/style.css",
  "/static/js/main.js",
  "/static/js/capture.js",
  "/credits",
  "/manifest.json"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  // Pass non-GET and API/POST requests directly to network
  if (e.request.method !== "GET" || e.request.url.includes("/capture/scan")) {
    return;
  }

  e.respondWith(
    caches.match(e.request).then((cached) => {
      return (
        cached ||
        fetch(e.request).catch(() => {
          // Fallback if offline
          return caches.match("/");
        })
      );
    })
  );
});
