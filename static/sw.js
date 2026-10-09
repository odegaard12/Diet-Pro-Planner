/*
 * Diet Pro Planner · offline shell (served at /sw.js, version injected by the server).
 * Network first for everything: online you always get the latest UI and data; offline the
 * last copy is shown read-only. Writes (POST/PUT/DELETE) are never cached or queued.
 */
const CACHE = 'dpp-__DPP_VERSION__';
const SHELL = ['/', '/static/manifest.webmanifest', '/static/icon-192.png', '/static/icon-512.png'];
// Read-only API snapshots worth having offline (last values seen on this device).
const API_READS = ['/api/state', '/api/profile', '/api/food-intel/day', '/api/smart-coach/day', '/api/analytics/overview', '/api/body-snapshot/latest'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => null).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith('dpp-') && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  const cacheable = req.mode === 'navigate' || url.pathname.startsWith('/static/') || API_READS.includes(url.pathname);
  if (!cacheable) return;
  event.respondWith((async () => {
    try {
      const res = await fetch(req);
      // Only keep real app responses (never the login page served for "/" while logged out).
      const isLogin = req.mode === 'navigate' && (res.headers.get('content-security-policy') || '').includes("default-src 'none'");
      if (res.ok && !res.redirected && !isLogin) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req.mode === 'navigate' ? '/' : req, copy));
      }
      return res;
    } catch (err) {
      const hit = await caches.match(req.mode === 'navigate' ? '/' : req);
      if (hit) return hit;
      if (url.pathname.startsWith('/api/')) {
        return new Response(JSON.stringify({error: 'Sin conexión con la Raspberry'}), {status: 503, headers: {'Content-Type': 'application/json'}});
      }
      throw err;
    }
  })());
});
