// Christduell service worker — push notifications only, no caching. The app
// itself stays network-served so deploys reach everyone immediately.

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = { title: "Christduell", body: "", data: {} };
  try {
    payload = { ...payload, ...event.data.json() };
  } catch {
    // A push without JSON payload still shows the default title.
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      data: payload.data,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: payload.data && payload.data.duelId ? `duel-${payload.data.duelId}` : undefined,
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Focus an open tab if there is one, otherwise open the app.
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) return client.focus();
      }
      return self.clients.openWindow("/");
    }),
  );
});
