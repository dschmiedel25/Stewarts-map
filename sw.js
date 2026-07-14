// Minimal service worker — mainly exists to satisfy Android/Chrome's "Add to Home Screen"
// installability requirements. Also gives a small offline benefit: if someone opens the map
// with no signal, they'll see the last-loaded version of the page shell instead of a blank
// error page (ratings/tips still need a live connection to Firestore to load, though).

const CACHE_NAME = 'stewarts-map-shell-v1';
const SHELL_FILES = [
  './index.html'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

// Network-first for navigation requests (so updates show up quickly), falling back to the
// cached shell only if the network is unavailable.
self.addEventListener('fetch', (event) => {
  if(event.request.mode === 'navigate'){
    event.respondWith(
      fetch(event.request).catch(() => caches.match('./index.html'))
    );
  }
});
