/* loved.js — the most-loved leaderboard, read live from the love counters. */
(function () {
  var host = document.getElementById('loved-app');
  if (!host) return;
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function safeLink(value) {
    if (typeof value !== 'string' || !/^\/(?!\/)/.test(value) || /[\\\u0000-\u0020]/.test(value)) return '/';
    try { var u = new URL(value, location.origin); return u.origin === location.origin ? u.pathname + u.search + u.hash : '/'; } catch (e) { return '/'; }
  }
  fetch('/api/most-loved?limit=48').then(function (r) { return r.json(); }).then(function (j) {
    var items = j.items || [];
    if (!items.length) {
      host.innerHTML = '<p class="muted">No reader votes yet. Find a car you love and tap its heart to start the list. <a href="/cars/">Explore the cars →</a></p>';
      return;
    }
    host.innerHTML = items.map(function (it, i) {
      return '<a class="loved-card" href="' + esc(safeLink(it.url)) + '">' +
        '<span class="loved-rank">' + (i + 1) + '</span>' +
        '<b>' + esc(it.name || it.item) + '</b>' +
        '<span class="loved-n"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" ' +
        'd="M12 21s-7.5-4.7-9.5-9C1 8.6 2.6 5 6.2 5 8.4 5 10 6.3 12 8.6 14 6.3 15.6 5 17.8 5c3.6 0 5.2 3.6 3.7 7-2 4.3-9.5 9-9.5 9z"/></svg>' +
        it.n + '</span></a>';
    }).join('');
  }).catch(function () {
    host.innerHTML = '<p class="muted">Could not load the list right now.</p>';
  });
})();
