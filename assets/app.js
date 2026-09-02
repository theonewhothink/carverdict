/* app.js — the phone layer (see app.css). Runs on every page; does nothing above 767px.
   Bottom tab bar, one-row header with search and country buttons, full-screen search that
   reuses the site's own instant-search engine, bottom sheets for country and rating,
   a sticky action bar on car pages, install prompt and service worker. */
(function () {
  'use strict';
  var mq = window.matchMedia('(max-width:767px)');
  var I = {
    home: '<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
    search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>',
    library: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/></svg>',
    heart: '<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.4-9-9a4.5 4.5 0 0 1 8-3.5A4.5 4.5 0 0 1 21 11c-2 4.6-9 9-9 9z"/></svg>',
    user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/></svg>',
    globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18"/></svg>'
  };
  var path = location.pathname;
  var lang = (path.match(/^\/(pt|es|fr|de|he)\//) || [])[1];
  var pre = lang ? '/' + lang : '';

  function el(html) { var d = document.createElement('div'); d.innerHTML = html; return d.firstElementChild; }
  function on(root, ev, sel, fn) { root.addEventListener(ev, function (e) { var t = e.target.closest(sel); if (t) fn(e, t); }); }

  /* ---------- bottom tabs ---------- */
  function tabs() {
    var signed = false;
    var items = [
      ['/', 'Home', I.home, function () { return path === '/' || path === pre + '/'; }],
      ['#search', 'Search', I.search, function () { return path.indexOf('/search/') === 0; }],
      ['/library/', 'Library', I.library, function () { return /^\/(cars|library|compare|problems)\//.test(path); }],
      ['/loved/', 'Loved', I.heart, function () { return path.indexOf('/loved/') === 0; }],
      ['/account/', 'Account', I.user, function () { return /^\/(account|login|garage)\//.test(path); }]
    ];
    var bar = el('<nav class="app-tabs" aria-label="App navigation">' + items.map(function (t) {
      return '<a href="' + t[0] + '"' + (t[3]() ? ' class="on"' : '') + (t[0] === '#search' ? ' data-app-search' : '') + '>' + t[2] + '<span>' + t[1] + '</span></a>';
    }).join('') + '</nav>');
    document.body.appendChild(bar);
    // account tab follows sign-in state once account.js has resolved it
    fetch('/api/auth/me', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (j && j.user) { signed = true; bar.lastElementChild.href = '/garage/'; }
      else bar.lastElementChild.href = '/login/';
    }).catch(function () {});
  }

  /* ---------- header buttons ---------- */
  function header() {
    var hin = document.querySelector('.hdr-in');
    if (!hin) return;
    var acct = hin.querySelector('.acct-host');
    var sBtn = el('<button class="app-hdr-btn" type="button" aria-label="Search" data-app-search>' + I.search + '</button>');
    var gBtn = el('<button class="app-hdr-btn" type="button" aria-label="Country and currency" data-app-geo>' + I.globe + '</button>');
    hin.insertBefore(gBtn, acct || null);
    hin.insertBefore(sBtn, acct || null);
    if (!document.querySelector('[data-geo-chip]')) gBtn.remove();
  }

  /* ---------- sheets ---------- */
  var scrim = el('<div class="app-scrim"></div>');
  var sheet = el('<div class="app-sheet" role="dialog" aria-modal="true"></div>');
  var restore = null;
  function openSheet(title, node, onClose) {
    closeSheet();
    sheet.innerHTML = '';
    if (title) sheet.appendChild(el('<h3>' + title + '</h3>'));
    if (node) {
      if (node.parentNode) { var ph = document.createComment('app-sheet'); node.parentNode.insertBefore(ph, node); restore = function () { ph.parentNode.insertBefore(node, ph); ph.remove(); }; }
      sheet.appendChild(node);
    }
    sheet.onclose = onClose || null;
    document.body.appendChild(scrim); document.body.appendChild(sheet);
    requestAnimationFrame(function () { scrim.classList.add('open'); sheet.classList.add('open'); });
    document.body.style.overflow = 'hidden';
  }
  function closeSheet() {
    if (!sheet.classList.contains('open')) return;
    scrim.classList.remove('open'); sheet.classList.remove('open');
    document.body.style.overflow = '';
    if (restore) { restore(); restore = null; }
    if (sheet.onclose) sheet.onclose();
  }
  scrim.addEventListener('click', closeSheet);
  var startY = 0;
  sheet.addEventListener('touchstart', function (e) { startY = e.touches[0].clientY; }, { passive: true });
  sheet.addEventListener('touchend', function (e) { if (sheet.scrollTop === 0 && e.changedTouches[0].clientY - startY > 70) closeSheet(); }, { passive: true });

  function geoSheet() {
    var chip = document.querySelector('.geo-chip');
    if (!chip) { location.href = '/calculators/'; return; }
    openSheet('Your country', chip);
    var sel = chip.querySelector('select');
    if (sel) sel.addEventListener('change', function () { setTimeout(closeSheet, 250); }, { once: true });
  }

  /* ---------- full-screen search ---------- */
  var searchUI = null, recentKey = 'mj.recent';
  function recent() { try { return JSON.parse(localStorage.getItem(recentKey) || '[]'); } catch (e) { return []; } }
  function remember(q) { try { var r = recent().filter(function (x) { return x !== q; }); r.unshift(q); localStorage.setItem(recentKey, JSON.stringify(r.slice(0, 8))); } catch (e) {} }
  function searchOpen() {
    var q = document.getElementById('q'), out = document.getElementById('q-out');
    if (!searchUI) {
      searchUI = el('<div class="app-search" role="dialog" aria-label="Search"><div class="app-search-bar"><div class="app-slot" style="flex:1"></div><button type="button" data-app-close>Cancel</button></div><div class="app-search-body"><div class="app-out"></div><div class="app-recent"></div></div></div>');
      document.body.appendChild(searchUI);
      on(searchUI, 'click', '[data-app-close]', searchClose);
      on(searchUI, 'click', 'a', function (e, a) { var t = (a.textContent || '').trim(); if (t) remember(t); });
      on(searchUI, 'click', '[data-recent]', function (e, b) { e.preventDefault(); if (q) { q.value = b.getAttribute('data-recent'); q.dispatchEvent(new Event('input', { bubbles: true })); } });
    }
    var slot = searchUI.querySelector('.app-slot'), body = searchUI.querySelector('.app-out');
    if (q && !slot.contains(q)) { var box = q.closest('.searchbox') || q; searchUI._ph = document.createComment('q'); box.parentNode.insertBefore(searchUI._ph, box); searchUI._box = box; slot.appendChild(q); if (out) body.appendChild(out); }
    if (!q) slot.innerHTML = '<form action="/search/" method="get"><input type="search" name="q" placeholder="Search any car ever made…" autocomplete="off"></form>';
    var r = recent();
    searchUI.querySelector('.app-recent').innerHTML = r.length
      ? '<h4>Recent</h4>' + r.map(function (x) { return '<a href="#" data-recent="' + x.replace(/"/g, '&quot;') + '">' + x.replace(/</g, '&lt;') + '</a>'; }).join('')
      : '<p class="app-search-empty">Type a make, a model or a year. Every car ever made is in here.</p>';
    searchUI.classList.add('open');
    document.body.style.overflow = 'hidden';
    var inp = searchUI.querySelector('input');
    if (inp) { inp.value = ''; if (out) out.hidden = true; setTimeout(function () { inp.focus(); }, 80); }
    history.pushState({ appSearch: 1 }, '');
  }
  function searchClose() {
    if (!searchUI || !searchUI.classList.contains('open')) return;
    searchUI.classList.remove('open');
    document.body.style.overflow = '';
    var q = document.getElementById('q'), out = document.getElementById('q-out');
    if (searchUI._ph && q) { var box = searchUI._box; searchUI._ph.parentNode.insertBefore(box, searchUI._ph); searchUI._ph.remove(); searchUI._ph = null; if (box !== q) box.insertBefore(q, box.firstChild); if (out) { box.appendChild(out); out.hidden = true; } }
    if (history.state && history.state.appSearch) history.back();
  }
  window.addEventListener('popstate', function () { if (searchUI && searchUI.classList.contains('open')) { searchUI.classList.remove('open'); document.body.style.overflow = ''; searchClose(); } closeSheet(); });

  /* ---------- sticky action bar on car pages ---------- */
  function actionBar() {
    if (!/^\/(cars|library)\/[^/]+\/[^/]+\//.test(path)) return;
    var h1 = document.querySelector('h1'); if (!h1) return;
    var name = h1.textContent.replace(/:.*$/, '').trim();
    var price = document.querySelector('.price-big b, .price-big strong, .price-big .val, .price-big');
    var meta = price ? price.textContent.replace(/\s+/g, ' ').replace(/Typical price today/i, '').trim().split(/ used | · /)[0].slice(0, 40) : '';
    if (!meta) { var f = document.querySelector('.facts b, .facts strong'); if (f) meta = f.textContent.trim().slice(0, 40); }
    var costs = document.querySelector('.cost-table, [data-tco], .calc, #tco, .price-head');
    var bar = el('<div class="app-actionbar"><div class="ab-txt"><div class="ab-name"></div><div class="ab-meta"></div></div>' +
      (costs ? '<button type="button" data-ab-costs>Costs</button>' : '') + '<button type="button" class="pri" data-ab-rate>' + I.heart.replace('<svg', '<svg style="width:18px;height:18px;vertical-align:-4px;stroke:#fff;fill:none;stroke-width:2"') + ' Rate</button></div>');
    bar.querySelector('.ab-name').textContent = name;
    bar.querySelector('.ab-meta').textContent = meta;
    document.body.appendChild(bar);
    on(bar, 'click', '[data-ab-costs]', function () { costs.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    on(bar, 'click', '[data-ab-rate]', function () {
      var row = document.querySelector('.engage-row');
      if (row) openSheet('Your verdict on the ' + name, row);
      else { var host = document.querySelector('[data-engage]'); if (host) host.scrollIntoView({ behavior: 'smooth' }); else location.href = '/login/'; }
    });
    var shown = false;
    function tick() { var s = window.scrollY > 260 && (window.innerHeight + window.scrollY) < document.body.scrollHeight - 200; if (s !== shown) { shown = s; bar.classList.toggle('show', s); } }
    window.addEventListener('scroll', tick, { passive: true }); tick();
  }

  /* ---------- carousels for long link grids on the home page ---------- */
  function carousels() {
    document.querySelectorAll('.icons-home .rel-grid, section.card > .rel-grid').forEach(function (g) {
      if (g.children.length >= 6 && g.closest('section.card')) g.classList.add('app-carousel');
    });
  }

  /* ---------- install prompt + service worker ---------- */
  function pwa() {
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(function () {});
    var deferred = null;
    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault(); deferred = e;
      var n = 0; try { n = +(localStorage.getItem('mj.visits') || 0) + 1; localStorage.setItem('mj.visits', n); } catch (x) {}
      if (n < 2 || sessionStorage.getItem('mj.install.dismissed')) return;
      var pill = el('<div class="app-sheet open" style="visibility:visible;transform:none;max-height:none"><h3>Add MotorJury to your home screen</h3><p style="color:var(--muted);margin:0 0 14px;font-size:15px">Opens full screen, works offline, one tap away.</p><div class="row"><button class="btn" type="button" data-inst>Add</button><button class="btn ghost" type="button" data-dis>Not now</button></div></div>');
      document.body.appendChild(pill);
      on(pill, 'click', '[data-inst]', function () { deferred.prompt(); pill.remove(); });
      on(pill, 'click', '[data-dis]', function () { pill.remove(); try { sessionStorage.setItem('mj.install.dismissed', '1'); } catch (x) {} });
    });
  }

  function boot() {
    if (!mq.matches) return;
    tabs(); header(); actionBar(); carousels(); pwa();
    on(document, 'click', '[data-app-search]', function (e) { e.preventDefault(); searchOpen(); });
    on(document, 'click', '[data-app-geo]', function (e) { e.preventDefault(); geoSheet(); });
    // Enter in the search overlay: go to the results page and remember the query
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && searchUI && searchUI.classList.contains('open')) {
        var inp = searchUI.querySelector('input'); var v = inp && inp.value.trim();
        if (v) { remember(v); location.href = '/search/?q=' + encodeURIComponent(v); }
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
