const CACHE = 'droperog-v1';
const URLS = ['/', '/index.html', '/style.css', '/app.js', '/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(URLS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))));
});

self.addEventListener('fetch', e => {
  if (e.request.url.includes('api.github.com') || e.request.url.includes('raw.githubusercontent')) {
    e.respondWith(fetch(e.request).catch(() => new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json' } })));
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
