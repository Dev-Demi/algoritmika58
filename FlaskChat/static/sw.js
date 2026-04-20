// This is a placeholder service worker file.
// A service worker is required for a web app to be installable (PWA).

self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing...');
  // You can pre-cache assets here if needed.
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');
});

self.addEventListener('fetch', (event) => {
  // For now, we are not intercepting any requests.
  // This is a network-first approach.
  event.respondWith(fetch(event.request));
});
