/* events.js — search and filter the motoring calendar.

   The whole dataset is inlined in the page (about 130 rows), so filtering is instant and
   works with no network after first load. Filters are reflected in the URL so a filtered
   view — "every concours in Italy" — is a link somebody can share. */
(function () {
  var el = document.getElementById('ev-data');
  var grid = document.getElementById('ev-grid');
  if (!el || !grid) return;

  var rows = [];
  try { rows = JSON.parse(el.textContent); } catch (e) { return; }

  var q = document.getElementById('ev-q');
  var cat = document.getElementById('ev-cat');
  var co = document.getElementById('ev-co');
  var mo = document.getElementById('ev-mo');
  var soon = document.getElementById('ev-soon');
  var count = document.getElementById('ev-count');
  var onlyDated = false;

  // deep-link support: /events/?cat=Concours&co=Italy&q=le+mans
  var params = new URLSearchParams(location.search);
  if (params.get('q')) q.value = params.get('q');
  if (params.get('cat')) cat.value = params.get('cat');
  if (params.get('co')) co.value = params.get('co');
  if (params.get('mo')) mo.value = params.get('mo');
  if (params.get('dated')) { onlyDated = true; soon.classList.add('on'); }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function card(r) {
    var when = r.dh
      ? '<span class="ev-when ok">' + esc(r.dh) + '</span>'
      : '<span class="ev-when">' + (r.w.toLowerCase().indexOf(r.mo.toLowerCase()) === 0 ? esc(r.w) : esc(r.mo) + ' · ' + esc(r.w)) + '</span>';
    return '<a class="ev-card" href="' + r.u + '">' +
      '<span class="ev-cat">' + esc(r.c) + '</span>' +
      '<b>' + esc(r.n) + '</b>' +
      when +
      '<small>' + esc(r.p) + ', ' + esc(r.co) + '</small></a>';
  }

  function apply() {
    var term = (q.value || '').trim().toLowerCase();
    var out = rows.filter(function (r) {
      if (cat.value && r.c !== cat.value) return false;
      if (co.value && r.co !== co.value) return false;
      if (mo.value && r.mo !== mo.value) return false;
      if (onlyDated && !r.d) return false;
      if (!term) return true;
      return (r.n + ' ' + r.s + ' ' + r.p + ' ' + r.co + ' ' + r.c).toLowerCase().indexOf(term) > -1;
    });

    grid.innerHTML = out.length
      ? out.map(card).join('')
      : '<p class="muted">Nothing matches that. Try clearing a filter.</p>';
    count.textContent = out.length === rows.length
      ? rows.length + ' events, listed by the month they fall in.'
      : out.length + ' of ' + rows.length + ' events.';

    var p = new URLSearchParams();
    if (term) p.set('q', q.value.trim());
    if (cat.value) p.set('cat', cat.value);
    if (co.value) p.set('co', co.value);
    if (mo.value) p.set('mo', mo.value);
    if (onlyDated) p.set('dated', '1');
    var qs = p.toString();
    history.replaceState(null, '', qs ? '?' + qs : location.pathname);
  }

  [q, cat, co, mo].forEach(function (n) {
    n.addEventListener('input', apply);
    n.addEventListener('change', apply);
  });
  soon.addEventListener('click', function () {
    onlyDated = !onlyDated;
    soon.classList.toggle('on', onlyDated);
    apply();
  });

  apply();
})();
