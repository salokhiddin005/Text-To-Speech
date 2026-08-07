// Minimal service worker: cache the shell, network-first for the rest.

// Bumped to v2 to purge caches holding the pre-token page, which had no
// page-token meta tag and left the Speak button inert.
const CACHE_NAME = 'tts-v2';
// '/' is deliberately absent: it carries a per-visit token and must always come
// from the network, or a cached copy hands out a token the server won't accept.
const SHELL = ['/manifest.json', '/static/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Don't try to cache POST/PUT/DELETE etc.
  if (event.request.method !== 'GET') return;
  // Always go to network for: the synthesis endpoints, and any page navigation.
  // The HTML carries a per-visit token, so serving it from cache would hand the
  // visitor a token the server rejects.
  const url = new URL(event.request.url);
  if (url.pathname === '/speak' || url.pathname.startsWith('/api/')) return;
  if (event.request.mode === 'navigate' || url.pathname === '/') return;

  event.respondWith(
    fetch(event.request)
      .then((res) => {
        // Only cache real successes — caching a 404/500 would serve that error
        // back from the cache long after the server recovered.
        if (res.ok && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});
