self.addEventListener('push', (event) => {
  const payload = event.data
    ? event.data.json()
    : { title: 'Life OS reminder', body: 'A task is due.' };
  event.waitUntil(
    self.registration.showNotification(payload.title || 'Life OS reminder', {
      body: payload.body || 'A task is due.',
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      tag: payload.tag || 'life-os-reminder',
      data: { url: payload.url || '/' },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/', self.location.origin)
    .href;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((client) => client.url.startsWith(self.location.origin));
      if (existing) {
        existing.focus();
        return existing.navigate(target);
      }
      return self.clients.openWindow(target);
    }),
  );
});
