const CACHE = "nuestra-vision-v1";
const RECURSOS = ["/", "/manifest.json"];
self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(RECURSOS)));
  self.skipWaiting();
});
self.addEventListener("activate", (evento) => evento.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (evento) => {
  if (evento.request.method !== "GET" || evento.request.url.includes("/api/")) return;
  evento.respondWith(fetch(evento.request).catch(() => caches.match(evento.request)));
});