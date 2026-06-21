/**
 * Cadence — clinician Web Push service worker (CAD-48).
 *
 * Receives zero-PHI push notifications from the backend escalation handler
 * and shows a browser notification. The payload contains NO patient data —
 * just a tap-to-open signal. All clinical detail lives behind the
 * authenticated dashboard session.
 *
 * Zero-PHI contract: the backend sends only
 *   { "title": "Cadence", "body": "A patient needs your attention — open dashboard." }
 */

self.addEventListener("push", (event) => {
  let data = { title: "Cadence", body: "A patient needs your attention — open dashboard." };
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      /* keep default */
    }
  }

  event.waitUntil(
    self.registration.showNotification(data.title ?? "Cadence", {
      body: data.body ?? "A patient needs your attention — open dashboard.",
      icon: "/cadence-icon.png",
      badge: "/cadence-icon.png",
      tag: "cadence-escalation",       // replaces previous notification instead of stacking
      renotify: true,
      requireInteraction: true,        // stays visible until clinician taps
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((list) => {
        // Focus existing tab if open
        for (const client of list) {
          if (client.url.includes(self.location.origin) && "focus" in client) {
            return client.focus();
          }
        }
        // Otherwise open the dashboard
        if (clients.openWindow) {
          return clients.openWindow("/");
        }
      }),
  );
});
