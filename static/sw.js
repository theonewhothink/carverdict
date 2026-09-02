/* MotorJury service worker: app shell offline, assets stale-while-revalidate, pages
   network-first with an offline fallback. Version bumps on every deploy via the build. */
var V = 'mj-__BUILD__';
var SHELL = ['/', '/offline.html', '/assets/site.css', '/assets/app.css', '/assets/app.js', '/assets/site.js', '/assets/account.js', '/icon-192.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(V).then(function (c) { return c.addAll(SHELL).catch(function () {}); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== V; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.pathname.indexOf('/api/') === 0 || url.pathname.indexOf('/cdn-cgi/') === 0) return;
  if (url.origin === location.origin && (url.pathname.indexOf('/assets/') === 0 || /\.(png|svg|ico|webmanifest|json)$/.test(url.pathname))) {
    e.respondWith(caches.open(V).then(function (c) {
      return c.match(req).then(function (hit) {
        var net = fetch(req).then(function (res) { if (res.ok) c.put(req, res.clone()); return res; }).catch(function () { return hit; });
        return hit || net;
      });
    }));
    return;
  }
  if (url.hostname === 'commons.wikimedia.org' || url.hostname === 'upload.wikimedia.org') {
    e.respondWith(caches.open(V + '-img').then(function (c) {
      return c.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) { if (res.ok || res.type === 'opaque') c.put(req, res.clone()); return res; });
      });
    }));
    return;
  }
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then(function (res) {
      if (res.ok) caches.open(V).then(function (c) { c.put(req, res.clone()); });
      return res;
    }).catch(function () {
      return caches.match(req).then(function (hit) { return hit || caches.match('/offline.html'); });
    }));
  }
});
