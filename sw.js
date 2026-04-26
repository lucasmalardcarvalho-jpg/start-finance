// PenseFinances — Service Worker v2.4 (detalhe customizado por tipo de ativo)
const CACHE = 'pf-v2.4';
const STATIC = [
  '/',
  '/dashboard',
  '/logo.svg',
  '/logo-icon.svg',
  '/manifest.json',
  'https://fonts.googleapis.com/css2?family=Cabinet+Grotesk:wght@400;500;700;800;900&family=Lora:ital@1&display=swap'
];

// Instalação: pré-caches estáticos
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC).catch(()=>{}))
  );
  self.skipWaiting();
});

// Ativação: limpa caches antigos
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first para API, cache-first para assets
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API: sempre tenta rede, sem cache
  if(url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(e.request).catch(() => new Response('{"erro":"offline"}',{headers:{'Content-Type':'application/json'}})));
    return;
  }

  // Dashboard HTML: network-first (garante versão atualizada)
  if(url.pathname === '/' || url.pathname === '/dashboard' || url.pathname === '/app') {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Outros assets: cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
      const clone = res.clone();
      caches.open(CACHE).then(c => c.put(e.request, clone));
      return res;
    }))
  );
});

// Push notifications
self.addEventListener('push', e => {
  const data = e.data?.json() || {};
  const title = data.title || 'PenseFinances';
  const body  = data.body  || 'Você tem um aviso financeiro.';
  const icon  = '/logo-icon.svg';
  e.waitUntil(
    self.registration.showNotification(title, { body, icon, badge: icon, vibrate:[200,100,200] })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow('/'));
});

// Recebe postMessage do app para exibir notificação local
self.addEventListener('message', e => {
  if(e.data && e.data.type === 'NOTIFY'){
    const { title='PenseFinances', body='', tag='pf' } = e.data;
    e.waitUntil(
      self.registration.showNotification(title, {
        body, tag,
        icon: '/logo-icon.svg',
        badge: '/logo-icon.svg',
        vibrate: [200, 100, 200],
      })
    );
  }
});
