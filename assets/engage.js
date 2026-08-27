/* engage.js — retention moat: Car of the Day, Guess the Car (daily, streaks),
   My Garage (saved cars), preference memory. It works signed out in localStorage and,
   once signed in, syncs the same preferences through the account API. */
(function () {
  var P = 'cv_prefs';
  var prefs = read();
  var me = null, syncTimer = null;

  function read() {
    try { return JSON.parse(localStorage.getItem(P) || '{}'); } catch (e) { return {}; }
  }
  function save() {
    try { localStorage.setItem(P, JSON.stringify(prefs)); } catch (e) {}
    window.CV = window.CV || {};
    window.CV.prefs = prefs;
    if (me) {
      clearTimeout(syncTimer);
      syncTimer = setTimeout(function () {
        fetch('/api/prefs', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prefs: prefs }),
        }).catch(function () {});
      }, 250);
    }
  }
  window.CV = window.CV || {};
  window.CV.prefs = prefs;
  window.CV.savePrefs = save;
  window.CV.setPrefs = function (next) { prefs = next || {}; save(); };

  function mergeRows(server, local, key) {
    var out = (server || []).slice();
    (local || []).forEach(function (row) {
      if (!out.some(function (saved) { return saved[key] === row[key]; })) out.push(row);
    });
    return out;
  }

  document.addEventListener('cv:me', function (event) {
    me = event.detail || null;
    if (!me) return;
    var local = prefs;
    var server = me.prefs || {};
    prefs = Object.assign({}, local, server);
    prefs.garage = mergeRows(server.garage, local.garage, 'u');
    prefs.recent = mergeRows(server.recent, local.recent, 'u').slice(0, 12);
    delete prefs.ratings; // ratings live in the account-backed owner-response system
    save();
    garageButton();
    garageList();
    recentList();
  });

  // ---------- deterministic daily pick (same car for everyone, changes at UTC midnight) ----------
  function dayIndex() {
    return Math.floor(Date.now() / 864e5);
  }
  function hash(n) { // xorshift, stable across browsers
    n ^= n << 13; n ^= n >>> 17; n ^= n << 5;
    return Math.abs(n);
  }
  function thumb(f, w) {
    return 'https://commons.wikimedia.org/wiki/Special:FilePath/' + encodeURIComponent(String(f).replace(/ /g, '_')) + '?width=' + w;
  }

  var DB = null;
  function load() {
    if (DB) return Promise.resolve(DB);
    return fetch('/assets/daily-pool.json').then(function (r) { return r.json(); }).then(function (rows) {
      DB = rows.map(function (r) { return { n: r[0], b: r[1], s: r[2], y: r[3], p: r[4] }; });
      return DB;
    });
  }

  // ---------- Car of the Day ----------
  function carOfTheDay(host) {
    load().then(function (db) {
      var d = dayIndex();
      var pick = db[hash(d * 7919) % db.length];
      var week = db[hash(Math.floor(d / 7) * 104729) % db.length];
      host.innerHTML =
        tile('Car of the Day', pick, 'cotd') +
        tile('Car of the Week', week, 'cotw');
      host.classList.add('ready');
    });
  }
  function mslug(s) {
    return s.toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/[\s_]+/g, '-').slice(0, 60) || 'x';
  }
  function tile(label, c, cls) {
    return '<a class="daily ' + cls + '" href="/library/' + c.s + '/' + mslug(c.n) + '/">' +
      '<img src="' + thumb(c.p, 720) + '" alt="' + c.n + '" loading="lazy">' +
      '<div class="daily-b"><span class="daily-k">' + label + '</span>' +
      '<b>' + c.n + '</b><small>' + c.b + (c.y ? ' · ' + c.y : '') + '</small></div></a>';
  }

  // ---------- Guess the Car (daily, 5 rounds, streak) ----------
  function game(host) {
    load().then(function (db) {
      var d = dayIndex(), seed = hash(d * 6151), rounds = [], used = {};
      for (var i = 0; i < 5; i++) {
        var answer = db[hash(seed + i * 131) % db.length];
        var opts = [answer];
        // Decoys from roughly the same era make this a game. Drawing them at random from
        // the whole catalogue produced rounds like "Ferrari F1/86 vs Ursus C10 Bambi",
        // which is not a guess — it is a giveaway.
        var ay = parseInt(answer.y, 10);
        var near = !isNaN(ay) ? db.filter(function (x) {
          var y = parseInt(x.y, 10);
          return !isNaN(y) && Math.abs(y - ay) <= 12 && x.n !== answer.n;
        }) : [];
        var pool = near.length >= 3 ? near : db;
        for (var k = 0; opts.length < 4 && k < 200; k++) {
          var o = pool[hash(seed + i * 977 + k * 31) % pool.length];
          if (!opts.some(function (x) { return x.n === o.n; })) opts.push(o);
        }
        opts.sort(function (a, b) { return hash(a.n.length + i) - hash(b.n.length + i); });
        rounds.push({ a: answer, o: opts });
      }
      var st = prefs.game || {};
      if (st.day === d && st.done) return renderDone(host, st);
      var idx = 0, score = 0;
      draw();

      function draw() {
        var r = rounds[idx];
        host.innerHTML =
          '<div class="game-head"><b>Guess the Car</b><span>' + (idx + 1) + ' / 5 · streak ' + (prefs.streak || 0) + ' 🔥</span></div>' +
          '<div class="game-img"><img src="' + thumb(r.a.p, 900) + '" alt="Guess this car"></div>' +
          '<p class="game-ask">Which car is this?</p>' +
          '<div class="game-opts">' + r.o.map(function (o, i) {
            return '<button data-i="' + i + '">' + o.n + (o.y ? ' <small>· ' + o.y + '</small>' : '') + '</button>';
          }).join('') + '</div>' +
          '<p class="game-note">Photo: Wikimedia Commons · 5 cars a day, new set every morning</p>';
        host.querySelectorAll('button').forEach(function (b) {
          b.addEventListener('click', function () {
            var ok = r.o[+b.dataset.i].n === r.a.n;
            b.classList.add(ok ? 'ok' : 'no');
            if (ok) score++;
            else host.querySelectorAll('button').forEach(function (x) {
              if (r.o[+x.dataset.i].n === r.a.n) x.classList.add('ok');
            });
            host.querySelectorAll('button').forEach(function (x) { x.disabled = true; });
            setTimeout(function () {
              idx++;
              if (idx < rounds.length) draw(); else finish();
            }, 750);
          });
        });
      }
      function finish() {
        var yesterday = (prefs.game && prefs.game.day) === d - 1;
        prefs.streak = (score >= 3) ? ((yesterday ? (prefs.streak || 0) : 0) + 1) : 0;
        prefs.game = { day: d, done: true, score: score };
        save();
        renderDone(host, prefs.game);
      }
      function renderDone(h, st) {
        var share = 'I scored ' + st.score + '/5 on today\'s Guess the Car 🚗 streak ' + (prefs.streak || 0) + '🔥';
        h.innerHTML = '<div class="game-done"><b>' + st.score + ' / 5</b>' +
          '<p>Streak: ' + (prefs.streak || 0) + ' 🔥 — new cars tomorrow.</p>' +
          '<div class="share-row">' +
          sbtn('X', 'https://twitter.com/intent/tweet?text=' + encodeURIComponent(share + ' ' + location.origin + '/play/')) +
          sbtn('LinkedIn', 'https://www.linkedin.com/sharing/share-offsite/?url=' + encodeURIComponent(location.origin + '/play/')) +
          '<button id="cp">Copy result</button></div></div>';
        var cp = h.querySelector('#cp');
        if (cp) cp.addEventListener('click', function () {
          navigator.clipboard && navigator.clipboard.writeText(share + ' ' + location.origin + '/play/');
          cp.textContent = 'Copied ✓';
        });
      }
      function sbtn(t, u) { return '<a class="sbtn" target="_blank" rel="noopener" href="' + u + '">' + t + '</a>'; }
    });
  }

  // ---------- My Garage (save any model-year page) ----------
  function garageButton() {
    var host = document.querySelector('[data-garage]');
    if (!host) return;
    var id = location.pathname;
    prefs.garage = prefs.garage || [];
    var on = prefs.garage.some(function (g) { return g.u === id; });
    host.innerHTML = '<button class="gbtn' + (on ? ' on' : '') + '">' + (on ? '★ Saved to My Garage' : '☆ Save to My Garage') + '</button>';
    host.querySelector('button').addEventListener('click', function () {
      var i = prefs.garage.findIndex(function (g) { return g.u === id; });
      if (i > -1) prefs.garage.splice(i, 1);
      else prefs.garage.push({ u: id, t: document.title.split(':')[0], ts: Date.now() });
      // interest signal for curated content
      var mk = (host.getAttribute('data-garage') || '').toLowerCase();
      if (mk) { prefs.interests = prefs.interests || {}; prefs.interests[mk] = (prefs.interests[mk] || 0) + 1; }
      save(); garageButton();
    });
  }

  function garageList() {
    var host = document.querySelector('[data-garage-list]');
    if (!host) return;
    var g = prefs.garage || [];
    host.innerHTML = g.length
      ? '<div class="rel-grid">' + g.map(function (x) { return '<a href="' + x.u + '">' + x.t + '<small>saved</small></a>'; }).join('') + '</div>'
      : '<p class="muted">Nothing saved yet — hit ☆ Save on any car page. Sign in and your garage follows you to every device.</p>';
  }

  function recentList() {
    var host = document.getElementById('recent');
    if (!host) return;
    var rows = prefs.recent || [];
    host.innerHTML = rows.length
      ? rows.map(function (x) { return '<a href="' + x.u + '">' + x.t + '<small>viewed</small></a>'; }).join('')
      : '<p class="muted">No history yet.</p>';
  }

  // ---------- recently viewed → curated strip ----------
  function trackView() {
    if (!/^\/(..\/)?cars\/[^/]+\/[^/]+\/\d{4}\//.test(location.pathname)) return;
    prefs.recent = (prefs.recent || []).filter(function (r) { return r.u !== location.pathname; });
    prefs.recent.unshift({ u: location.pathname, t: document.title.split(':')[0], ts: Date.now() });
    prefs.recent = prefs.recent.slice(0, 12);
    save();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var d = document.querySelector('[data-daily]'); if (d) carOfTheDay(d);
    var g = document.querySelector('[data-game]'); if (g) game(g);
    garageButton(); garageList(); trackView(); recentList();
  });
})();
