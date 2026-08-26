/* MotorJury site.js — universal car search.
   Results are ranked: exact brand > brand prefix > model prefix > model contains.
   BRAND rows link to that brand's library page; MODEL rows link to the page that actually
   contains that model (its own brand), so a result can never land on an unrelated brand. */
(function () {
  var MODELS = null, BRANDS = null, DEEP = null, DEEP_LOADING = false;

  function load(cb) {
    if (MODELS) return cb();
    fetch('/assets/library-data.json').then(function (r) { return r.json(); }).then(function (j) {
      MODELS = []; BRANDS = [];
      Object.keys(j).forEach(function (b) {
        BRANDS.push({ n: b, s: j[b].s, c: j[b].m.length });
        j[b].m.forEach(function (m) { MODELS.push({ n: m[0], b: b, s: j[b].s, y: m[2], h: m[3] }); });
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

  /* Enthusiast synonyms: expand nicknames before scoring so "Vette" finds the
     Corvette and "Bimmer" finds BMW. Both the raw and the expanded query are
     scored; the better rank wins, so real names are never penalised. */
  var SYN = {
    'vette': 'corvette', 'stang': 'mustang',
    'bimmer': 'bmw', 'beemer': 'bmw', 'beamer': 'bmw',
    'merc': 'mercedes-benz', 'benz': 'mercedes-benz',
    'chevy': 'chevrolet', 'vw': 'volkswagen',
    'lambo': 'lamborghini', 'jag': 'jaguar',
    'caddy': 'cadillac', 'landy': 'land rover'
  };
  function variants(v) {
    var out = [v];
    var swapped = v.split(/\s+/).map(function (w) { return SYN[w] || w; }).join(' ');
    if (swapped !== v) out.push(swapped);
    return out;
  }
  function best(name, vs) {
    var b = 99, i, s;
    for (i = 0; i < vs.length; i++) { s = score(name, vs[i]); if (s < b) b = s; }
    return b;
  }

  /* One binder serves every search box on the page: the header's #q everywhere,
     plus the large #q404 box on the branded not-found page. */
  function bind(q, out) {
  if (!q || !out) return;
  var T;
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
      /* h.h is the has-page flag from library-data.json. Only about half the
         catalogue has a page of its own; the rest live on their marque page, so
         those hits deep-link to the marque page anchored on the exact model.
         Linking a model URL blindly is what produced the site's 404 wave. */
      var url = h.h ? '/library/' + h.s + '/' + mslug(h.n) + '/'
                    : '/library/' + h.s + '/#m-' + mslug(h.n);
      return '<a href="' + url + '">' +
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
        var hits = [], i, sc, vs = variants(v);
        for (i = 0; i < BRANDS.length; i++) {
          sc = best(BRANDS[i].n, vs);
          if (sc < 4) hits.push({ kind: 'brand', sc: sc - 10, n: BRANDS[i].n, s: BRANDS[i].s, c: BRANDS[i].c });
        }
        for (i = 0; i < MODELS.length; i++) {
          sc = best(MODELS[i].n, vs);
          if (sc > 3) sc = best(MODELS[i].b + ' ' + MODELS[i].n, vs);
          if (sc < 4) hits.push({ kind: 'model', sc: sc, n: MODELS[i].n, b: MODELS[i].b, s: MODELS[i].s, y: MODELS[i].y });
          if (hits.length > 400) break;
        }
        hits.sort(function (a, b) { return a.sc - b.sc || a.n.length - b.n.length; });
        /* The primary index carries every car with a photo or a page. When it comes up
           short, the deep index — the long tail of real but thinly-recorded cars from the
           widened harvest — is fetched once and searched too; those hits land on the
           marque page, anchored on the model. */
        if (hits.length < 3) {
          if (DEEP) {
            for (i = 0; i < DEEP.length && hits.length < 9; i++) {
              if (best(DEEP[i][0], vs) < 4 || best(DEEP[i][1] + ' ' + DEEP[i][0], vs) < 4) {
                hits.push({ kind: 'model', sc: 5, n: DEEP[i][0], b: DEEP[i][1], s: DEEP[i][2], y: '', h: 0 });
              }
            }
          } else if (!DEEP_LOADING) {
            DEEP_LOADING = true;
            fetch('/assets/deep-index.json').then(function (r) { return r.json(); })
              .then(function (j) { DEEP = j; q.dispatchEvent(new Event('input')); })
              .catch(function () { DEEP = []; });
          }
        }
        render(hits.slice(0, 9));
        // the typeahead finds a car by name; the finder filters by year, fuel and price
        out.insertAdjacentHTML('beforeend',
          '<a class="q-all" href="/search/?q=' + encodeURIComponent(v) + '">All results with filters →</a>');
      });
    }, 110);
  });

  document.addEventListener('click', function (e) { if (!e.target.closest('.searchbox')) out.hidden = true; });
  q.addEventListener('keydown', function (e) { if (e.key === 'Escape') out.hidden = true; });
  }
  bind(document.getElementById('q'), document.getElementById('q-out'));
  bind(document.getElementById('q404'), document.getElementById('q404-out'));
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
      /* brand-rest.json is empty in every current build (every model already renders
         on the marque page), so this path is dormant; kept correct in case the cap
         returns. */
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

/* Photo self-heal — any catalogue image still unloaded after the page settles is
   reloaded eagerly once. Recovers from native lazy-load stalls and transient
   Commons throttling, both of which otherwise leave grey boxes. */
window.addEventListener('load', function () {
  function heal() {
    document.querySelectorAll('.ph img, .gal-cell img, .st-cell img, .hh-mosaic img, .model-shot img, .bio-fig img').forEach(function (im) {
      if ((im.complete && im.naturalWidth > 0) || im.dataset.healed) return;
      im.dataset.healed = '1';
      im.loading = 'eager';
      var s = im.src; im.removeAttribute('src'); im.src = s;
    });
  }
  setTimeout(heal, 1200);
  setTimeout(heal, 4000);
});
