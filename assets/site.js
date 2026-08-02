/* CarVerdict site.js — universal car search.
   Results are ranked: exact brand > brand prefix > model prefix > model contains.
   BRAND rows link to that brand's library page; MODEL rows link to the page that actually
   contains that model (its own brand), so a result can never land on an unrelated brand. */
(function () {
  var q = document.getElementById('q'), out = document.getElementById('q-out');
  if (!q) return;
  var MODELS = null, BRANDS = null, T;

  function load(cb) {
    if (MODELS) return cb();
    fetch('/assets/library-data.json').then(function (r) { return r.json(); }).then(function (j) {
      MODELS = []; BRANDS = [];
      Object.keys(j).forEach(function (b) {
        BRANDS.push({ n: b, s: j[b].s, c: j[b].m.length });
        j[b].m.forEach(function (m) { MODELS.push({ n: m[0], b: b, s: j[b].s, y: m[2] }); });
      });
      cb();
    });
  }

  function mslug(s) {
    return s.toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/[\s_]+/g, '-').slice(0, 60) || 'x';
  }
  function score(name, v) {
    var l = name.toLowerCase();
    if (l === v) return 0;
    if (l.indexOf(v) === 0) return 1;
    if (l.indexOf(' ' + v) > -1) return 2;
    if (l.indexOf(v) > -1) return 3;
    return 99;
  }

  function render(rows) {
    if (!rows.length) {
      out.innerHTML = '<div class="q-none">' + (q.getAttribute('data-none') || 'No matches') + '</div>';
      out.hidden = false; return;
    }
    out.innerHTML = rows.map(function (h) {
      if (h.kind === 'brand') {
        return '<a href="/library/' + h.s + '/" class="q-brand">' +
          '<span class="q-n"><i>Brand</i> ' + h.n + '</span>' +
          '<span class="q-b">' + h.c + ' models</span></a>';
      }
      return '<a href="/library/' + h.s + '/' + mslug(h.n) + '/">' +
        '<span class="q-n">' + h.n + '</span>' +
        '<span class="q-b">' + h.b + (h.y ? ' · ' + h.y : '') + '</span></a>';
    }).join('');
    out.hidden = false;
  }

  q.addEventListener('input', function () {
    clearTimeout(T);
    var v = q.value.trim().toLowerCase();
    if (v.length < 2) { out.hidden = true; return; }
    T = setTimeout(function () {
      load(function () {
        var hits = [], i, sc;
        for (i = 0; i < BRANDS.length; i++) {
          sc = score(BRANDS[i].n, v);
          if (sc < 4) hits.push({ kind: 'brand', sc: sc - 10, n: BRANDS[i].n, s: BRANDS[i].s, c: BRANDS[i].c });
        }
        for (i = 0; i < MODELS.length; i++) {
          sc = score(MODELS[i].n, v);
          if (sc > 3) sc = score(MODELS[i].b + ' ' + MODELS[i].n, v);
          if (sc < 4) hits.push({ kind: 'model', sc: sc, n: MODELS[i].n, b: MODELS[i].b, s: MODELS[i].s, y: MODELS[i].y });
          if (hits.length > 400) break;
        }
        hits.sort(function (a, b) { return a.sc - b.sc || a.n.length - b.n.length; });
        render(hits.slice(0, 9));
      });
    }, 110);
  });

  document.addEventListener('click', function (e) { if (!e.target.closest('.searchbox')) out.hidden = true; });
  q.addEventListener('keydown', function (e) { if (e.key === 'Escape') out.hidden = true; });
})();

/* progressive brand-page rendering: the remaining models render on demand */
(function () {
  document.addEventListener('click', function (e) {
    var b = e.target.closest('.more-btn');
    if (!b) return;
    var bs = b.getAttribute('data-brand');
    var grid = document.getElementById('lib-grid');
    b.textContent = 'Loading…';
    fetch('/assets/brand-rest.json').then(function (r) { return r.json(); }).then(function (all) {
    var rest = all[bs] || [];
    grid.insertAdjacentHTML('beforeend', rest.map(function (r) {
      var name = r[0], photo = r[1], year = r[2], slug = r[3];
      var href = slug ? '/library/' + bs + '/' + slug + '/' : '/library/' + bs + '/';
      var img = photo
        ? '<span class="ph"><img loading="lazy" alt="' + name + '" src="https://commons.wikimedia.org/wiki/Special:FilePath/' +
          encodeURIComponent(photo.replace(/ /g, '_')) + '?width=480"></span>'
        : '<span class="ph noimg"><svg viewBox="0 0 64 28"><path d="M6 22c2-6 8-9 14-9h20c6 0 12 3 14 9" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="18" cy="22" r="4" fill="currentColor"/><circle cx="46" cy="22" r="4" fill="currentColor"/></svg></span>';
      return '<a class="lib-card" href="' + href + '">' + img + '<b>' + name + '</b>' +
        (year ? '<small>since ' + year + '</small>' : '') + '</a>';
    }).join(''));
    b.remove();
    });
  });
})();
