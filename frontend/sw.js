// Service Worker: App-Shell-Cache (Offline-Start) + Web-Push. API-Antworten werden nie gecacht.
const CACHE = 'todo-shell-v5';
const SHELL = ['/', '/app.css', '/app.js', '/manifest.webmanifest', '/icons/icon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return res;
    }).catch(() => caches.match(e.request).then((r) => r || caches.match('/'))));
});

self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { /* ignore */ }
  const opts = { body: d.body || '', icon: '/icons/icon-192.png', badge: '/icons/icon-192.png', data: { url: d.url || '/' } };
  if (d.todo_id && d.token) { // Aktionen direkt in der Benachrichtigung (signierter Token, keine Sitzung nötig)
    opts.actions = [{ action: 'done', title: 'Erledigt' }, { action: 'snooze', title: '10 Min. später' }];
    opts.data.token = d.token; opts.tag = 'todo-' + d.todo_id; opts.renotify = true;
  }
  e.waitUntil(self.registration.showNotification(d.title || 'Todo', opts));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const token = e.notification.data && e.notification.data.token;
  if (token && (e.action === 'done' || e.action === 'snooze')) {
    e.waitUntil(fetch('/api/actions', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, action: e.action, minutes: 10 }) }).catch(() => {}));
    return;
  }
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const c of list) { if ('focus' in c) { c.navigate(url).catch(() => {}); return c.focus(); } }
    return self.clients.openWindow(url);
  }));
});
