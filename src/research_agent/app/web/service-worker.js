/**
 * P20 — Research Agent Service Worker
 * Cache-first for static assets, network-first for API calls, offline fallback.
 */

const CACHE_NAME = "research-agent-v1";
const STATIC_CACHE = "research-agent-static-v1";
const API_CACHE = "research-agent-api-v1";

const PRECACHE_URLS = [
  "/",
  "/static/index.html",
  "/static/styles_premium.css",
  "/static/app.js",
  "/static/personal_library.js",
  "/static/plugins.js",
  "/static/repro_enhancements.js",
  "/static/onboarding_guide.js",
  "/static/collaborative-editor.js",
  "/static/pwa-icon-192.svg",
  "/static/pwa-icon-512.svg",
  "/offline.html",
  "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=Fira+Code:wght@400;500&display=swap",
  "https://cdn.quilljs.com/1.3.6/quill.snow.css",
  "https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.min.css",
  "https://d3js.org/d3.v7.min.js",
];

// ── Install ────────────────────────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn("[SW] Precache partial failure:", err);
      });
    })
  );
  self.skipWaiting();
});

// ── Activate ───────────────────────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => {
      return Promise.all(
        names
          .filter((name) => name !== STATIC_CACHE && name !== API_CACHE && name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// ── Fetch ──────────────────────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const isStatic =
    url.pathname.startsWith("/static/") ||
    url.pathname.startsWith("/web/") ||
    url.pathname === "/offline.html" ||
    url.pathname === "/manifest.json" ||
    url.pathname === "/";

  const isApi = url.pathname.startsWith("/api/");
  const isCDN = url.hostname.includes("cdn.") || url.hostname.includes("fonts.googleapis.com");

  // Cache-first for static assets and CDN resources
  if (isStatic || isCDN) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  // Network-first for API calls (with offline fallback)
  if (isApi) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // For everything else, try network, fallback to cache
  event.respondWith(networkFirst(event.request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && response.status === 200 && response.type === "basic") {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    // If it's a navigation request, serve offline page
    if (request.mode === "navigate") {
      const offline = await caches.match("/offline.html");
      if (offline) return offline;
    }
    // Return a basic offline response for failed static assets
    return new Response("Offline", { status: 503, headers: { "Content-Type": "text/plain" } });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);

    // Cache successful GET API responses for offline use
    if (response && response.status === 200 && request.method === "GET") {
      // Don't cache large streaming responses
      const contentType = response.headers.get("Content-Type") || "";
      if (!contentType.includes("text/event-stream")) {
        const cache = await caches.open(API_CACHE);
        // Clone because response body can only be consumed once
        cache.put(request, response.clone());
      }
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;

    // Navigation fallback
    if (request.mode === "navigate") {
      const offline = await caches.match("/offline.html");
      if (offline) return offline;
    }

    // For API calls, return a structured error
    if (request.url.includes("/api/")) {
      return new Response(JSON.stringify({ error: "offline", message: "You are offline. Some features are unavailable." }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response("Offline", { status: 503 });
  }
}

// ── Background Sync ───────────────────────────────────────────────────────
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-library") {
    event.waitUntil(syncLibraryData());
  }
});

async function syncLibraryData() {
  // Attempt to re-fetch key API data when back online
  const cache = await caches.open(API_CACHE);
  const urlsToRefresh = [
    "/api/personal-library/items?limit=200",
    "/api/personal-library/collections",
    "/api/personal-library/reading-list",
  ];
  for (const url of urlsToRefresh) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        cache.put(url, response);
      }
    } catch (err) {
      // Silently skip - will retry on next sync
    }
  }
}

// ── Message Handling ──────────────────────────────────────────────────────
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
  if (event.data && event.data.type === "CACHE_API_DATA") {
    const { url, data } = event.data;
    if (url && data) {
      const response = new Response(JSON.stringify(data), {
        headers: { "Content-Type": "application/json" },
      });
      caches.open(API_CACHE).then((cache) => cache.put(url, response));
    }
  }
});
