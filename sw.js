// eRPH-PM Service Worker — offline-first for a logged-in browser.
// Network-first for app navigations (so the auth gate still applies online),
// cache-first for CDN assets. Same-origin static files are cached at runtime.
var CACHE = 'erph-v15-hub2027';
var CDN = [
  'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js',
  'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js',
  'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js'
];
var LOCAL = ['/tailwind.css', '/curriculum-db.js', '/rpt-data.js', '/exam-browser.js', '/icon.svg', '/manifest.webmanifest'];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      var tasks = CDN.map(function (u) {
        return fetch(u, { mode: 'cors' }).then(function (r) {
          if (r && r.ok) return c.put(u, r.clone());
        }).catch(function () {});
      });
      LOCAL.forEach(function (u) { tasks.push(c.add(u).catch(function () {})); });
      return Promise.all(tasks);
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (ks) {
      return Promise.all(ks.filter(function (k) { return k !== CACHE; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

function put(req, res) {
  try {
    caches.open(CACHE).then(function (c) { c.put(req, res); });
  } catch (err) {}
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);

  if (url.origin === location.origin) {
    if (req.mode === 'navigate') {
      // Network first (keeps auth working), then cached shell offline.
      e.respondWith(
        fetch(req).then(function (r) {
          var copy = r.clone();
          try { caches.open(CACHE).then(function (c) { c.put('/', copy); }); } catch (err) {}
          return r;
        }).catch(function () {
          return caches.match('/').catch(function () { return undefined; });
        })
      );
    } else if (url.pathname === '/rpt-data.js' || url.pathname === '/curriculum-db.js') {
      // Data files change with yearly curriculum updates: serve fresh when online,
      // fall back to cache offline so the classroom still works.
      e.respondWith(
        fetch(req).then(function (r) {
          if (r && r.ok) put(req, r.clone());
          return r;
        }).catch(function () {
          return caches.match(req).catch(function () { return undefined; });
        })
      );
    } else {
      // Other same-origin static: cache-first, revalidate in background for instant repeat loads.
      e.respondWith(
        caches.match(req).then(function (h) {
          var net = fetch(req).then(function (r) {
            if (r && r.ok) put(req, r.clone());
            return r;
          }).catch(function () { return h; });
          return h || net;
        })
      );
    }
  } else if (
    url.origin === 'https://cdn.jsdelivr.net' ||
    url.origin === 'https://cdnjs.cloudflare.com'
  ) {
    // Cache-first for CDN so the app works offline in the classroom.
    e.respondWith(
      caches.match(req).then(function (h) {
        if (h) return h;
        return fetch(req).then(function (r) {
          if (r && r.ok) put(req, r.clone());
          return r;
        });
      })
    );
  }
});