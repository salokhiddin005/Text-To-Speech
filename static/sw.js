// Minimal service worker: cache the shell, network-first for the rest.

const CACHE_NAME = 'tts-v1';
const SHELL = ['/', '/manifest.json', '/static/icon.svg'];

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
  // Don't cache the synthesis endpoint — always go to network.
  const url = new URL(event.request.url);
  if (url.pathname === '/speak' || url.pathname.startsWith('/api/')) return;

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
