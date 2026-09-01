/* account.js — sign-in, the love button, and the owner survey.

   The site knew nothing about its readers that survived a cleared browser. This is the
   client half of the fix: one small module that owns the account chip in the header, the
   sign-in and account pages, the love button on every car, and the owner-satisfaction
   survey. It talks to /api/*, which is the Worker, which is the database.

   Progressive by design. Every one of these surfaces is inert HTML until this file runs,
   so a failed request or a blocked script costs a reader nothing but the feature. Love
   counts are public and render for signed-out readers; only the act of loving needs an
   account, because a like anyone can cast a thousand times is not a signal. */
(function () {
  var ME = null, LOADED = false, WAIT = [];

  function api(path, body) {
    return fetch(path, body
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      : { credentials: 'same-origin' })
      .then(function (r) { return r.json().then(function (j) { return r.ok ? j : Promise.reject(j); }); });
  }

  function whenMe(fn) { LOADED ? fn(ME) : WAIT.push(fn); }

  function setMe(u) {
    ME = u; LOADED = true;
    window.CV = window.CV || {}; window.CV.me = u;
    document.documentElement.classList.toggle('signed-in', !!u);
    WAIT.splice(0).forEach(function (f) { f(u); });
    document.dispatchEvent(new CustomEvent('cv:me', { detail: u }));
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ---------------------------------------------------------- header chip -- */

  function chip() {
    var host = document.querySelector('[data-account-chip]');
    if (!host) return;
    if (ME) {
      var initial = (ME.name || ME.email || '?').trim().charAt(0).toUpperCase();
      host.innerHTML = '<a class="acct-chip in" href="/account/" aria-label="Your account">' +
        '<span class="acct-av">' + esc(initial) + '</span>' +
        '<span class="acct-nm">' + esc((ME.name || ME.email).split(' ')[0]) + '</span></a>';
    } else {
      host.innerHTML = '<a class="acct-chip" href="/login/?next=' +
        encodeURIComponent(location.pathname) + '">Sign in</a>';
    }
  }

  /* ------------------------------------------------- preference migration -- */

  /* Everything the reader built up before they had an account — the garage, the star
     ratings, the country override — lives in localStorage. On first sign-in it is pushed
     to the account once, so signing up never feels like starting over. */
  function migratePrefs() {
    if (!ME) return;
    var local = {};
    try { local = JSON.parse(localStorage.getItem('cv_prefs') || '{}'); } catch (e) { return; }
    try {
      var geo = localStorage.getItem('cv_geo_override');
      if (geo && !local.geo) local.geo = geo;
    } catch (e) {}
    if (!Object.keys(local).length) return;
    var server = ME.prefs || {};
    var merged = Object.assign({}, local, server);
    merged.garage = (server.garage || []).concat(
      (local.garage || []).filter(function (g) {
        return !(server.garage || []).some(function (s) { return s.u === g.u; });
      }));
    merged.recent = (server.recent || []).concat(
      (local.recent || []).filter(function (r) {
        return !(server.recent || []).some(function (s) { return s.u === r.u; });
      })).slice(0, 12);
    // Star ratings are owner responses in the account database, never a second set of
    // local-only scores. Drop the retired local bucket after its other preferences merge.
    delete merged.ratings;
    // Hydrate account surfaces immediately; the API round-trip should not make a saved
    // garage look empty for a moment after sign-in.
    ME.prefs = merged;
    api('/api/prefs', { prefs: merged }).then(function (r) {
      ME.prefs = r.prefs;
      try { localStorage.setItem('cv_prefs', JSON.stringify(r.prefs)); } catch (e) {}
    }).catch(function () {});
  }

  /* ------------------------------------------------------------ love button -- */

  /* One engagement row per car: the heart (a vote) and the reader's own 1–5 star rating
     (an owner response) side by side, both account-backed, both from the same database.
     The star row writes the "overall" field of the owner survey below it, so a quick tap
     and the full form are one record, not two rating systems. */
  var RATING = {};   // item -> {mine: overall|null, n, avg}

  function quickStars(item) {
    var r = RATING[item] || {};
    var mine = r.mine || 0, out = '';
    for (var i = 1; i <= 5; i++) out += '<button type="button" data-quick-star="' + i + '" class="' +
      (i <= mine ? 'on' : '') + '" aria-label="Rate ' + i + ' out of 5" aria-pressed="' +
      (i === mine ? 'true' : 'false') + '">★</button>';
    var summary = r.n >= MIN_RESPONSES
      ? '<b>' + (r.avg || 0).toFixed(1) + '</b>/5 · ' + r.n + ' owners'
      : (r.n ? r.n + ' owner' + (r.n > 1 ? 's' : '') + ' rated it' : (mine ? 'Your rating' : 'Rate it'));
    return '<span class="quick-rate" data-quick-rate="' + esc(item) + '"><span class="stars" role="group" aria-label="Your rating">' +
      out + '</span><small>' + summary + '</small></span>';
  }

  function loveMarkup(n, mine) {
    return '<button class="love' + (mine ? ' on' : '') + '" data-love-btn' +
      ' aria-pressed="' + (mine ? 'true' : 'false') + '" title="Love this car">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7.5-4.7-9.5-9C1 8.6 2.6 5 6.2 5 8.4 5 10 6.3 12 8.6 14 6.3 15.6 5 17.8 5c3.6 0 5.2 3.6 3.7 7-2 4.3-9.5 9-9.5 9z"/></svg>' +
      '<span class="love-n" data-love-n>' + (n || 0) + '</span>' +
      '<span class="love-lbl">' + (mine ? 'Loved' : 'Love it') + '</span></button>';
  }

  function loveInit() {
    var hosts = [].slice.call(document.querySelectorAll('[data-love]'));
    if (!hosts.length) return;
    var items = hosts.map(function (h) { return h.getAttribute('data-love'); });
    function paint(h, n, mine) {
      var id = h.getAttribute('data-love');
      h.innerHTML = '<div class="engage-row">' + loveMarkup(n, mine) + quickStars(id) + '</div>';
    }
    hosts.forEach(function (h) { paint(h, 0, false); });

    fetch('/api/love?items=' + encodeURIComponent(items.join(',')), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        hosts.forEach(function (h) {
          var id = h.getAttribute('data-love');
          h.setAttribute('data-love-n', (j.counts || {})[id] || 0);
          h.setAttribute('data-love-mine', (j.mine || []).indexOf(id) > -1 ? '1' : '');
          paint(h, (j.counts || {})[id] || 0, (j.mine || []).indexOf(id) > -1);
        });
      }).catch(function () {});

    // Ratings summary for the same items, from the owner-response rollups.
    document.addEventListener('cv:rating', function (e) {
      hosts.forEach(function (h) {
        if (h.getAttribute('data-love') !== e.detail.item) return;
        paint(h, +h.getAttribute('data-love-n') || 0, !!h.getAttribute('data-love-mine'));
      });
    });

    document.addEventListener('click', function (e) {
      var star = e.target.closest('[data-quick-star]');
      if (!star) return;
      var host = star.closest('[data-love]');
      var id = host.getAttribute('data-love');
      if (!ME) {
        location.href = '/login/?next=' + encodeURIComponent(location.pathname) + '&why=survey';
        return;
      }
      var v = +star.getAttribute('data-quick-star');
      var prev = (RATING[id] && RATING[id].mineRow) || {};
      api('/api/survey', {
        item: id, overall: v,
        reliability: prev.reliability || v, running_cost: prev.running_cost || v,
        years_owned: prev.years_owned || 0, would_buy_again: prev.would_buy_again ? true : v >= 4,
        comment: prev.comment || '',
      }).then(function (j) {
        var r = j.rollup || {};
        RATING[id] = { mine: v, n: r.n || 0, avg: r.o || r.overall || 0,
                       mineRow: Object.assign({}, prev, { overall: v }) };
        document.dispatchEvent(new CustomEvent('cv:rating', { detail: { item: id } }));
        document.dispatchEvent(new CustomEvent('cv:survey-saved', { detail: { item: id } }));
      }).catch(function () {});
    });

    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-love-btn]');
      if (!btn) return;
      var host = btn.closest('[data-love]');
      var id = host.getAttribute('data-love');
      if (!ME) {
        location.href = '/login/?next=' + encodeURIComponent(location.pathname) + '&why=love';
        return;
      }
      btn.disabled = true;
      api('/api/love', {
        item: id, name: host.getAttribute('data-love-name') || document.title, url: location.pathname,
      }).then(function (j) {
        host.setAttribute('data-love-n', j.count);
        host.setAttribute('data-love-mine', j.loved ? '1' : '');
        paint(host, j.count, j.loved);
      }).catch(function () { btn.disabled = false; });
    });
  }

  /* ----------------------------------------------------------- owner survey -- */

  /* The satisfaction data the site publishes has to come from somewhere, and the only
     honest somewhere is owners. Averages appear once five owners have answered — below
     that a mean is noise wearing a number's clothes, and publishing it would undo the
     whole point of a data site. */
  var MIN_RESPONSES = 5;

  function surveyInit() {
    [].slice.call(document.querySelectorAll('[data-survey]')).forEach(surveyOne);
  }

  function surveyOne(host) {
    var item = host.getAttribute('data-survey');
    var name = host.getAttribute('data-survey-name') || 'this car';

    function render(j) {
      var r = j.rollup || { n: 0 };
      RATING[item] = { mine: j.mine ? +j.mine.overall : 0, n: r.n || 0, avg: r.overall || 0, mineRow: j.mine || null };
      document.dispatchEvent(new CustomEvent('cv:rating', { detail: { item: item } }));
      var head;
      if (r.n >= MIN_RESPONSES) {
        head = '<div class="sv-scores">' +
          score('Overall', r.overall) + score('Reliability', r.reliability) +
          score('Running cost', r.running_cost) +
          '<div class="sv-score"><b>' + Math.round(r.again_pct) + '%</b><span>would buy it again</span></div>' +
          '</div><p class="sv-n">' + r.n + ' owners have answered. Averages update as more come in.</p>';
      } else if (r.n) {
        head = '<p class="sv-n">' + r.n + ' owner' + (r.n > 1 ? 's have' : ' has') +
          ' answered so far. Averages appear once ' + MIN_RESPONSES +
          ' owners have answered — below that an average is noise.</p>';
      } else {
        head = '<p class="sv-n"><b>No responses yet.</b> Own this car? Your account-backed rating can start the evidence.</p>';
      }
      var comments = (j.comments || []).length
        ? '<div class="sv-comments"><h4>What owners wrote</h4>' + j.comments.map(function (c) {
            return '<blockquote>' + esc(c.comment) +
              '<cite>owner' + (c.years_owned ? ', ' + c.years_owned + ' year' + (c.years_owned > 1 ? 's' : '') : '') +
              ' · rated ' + c.overall + '/5</cite></blockquote>';
          }).join('') + '</div>'
        : '';
      var form = ME
        ? formHtml(j.mine)
        : '<p class="sv-cta"><a class="btn" href="/login/?next=' +
          encodeURIComponent(location.pathname) + '&why=survey">Sign in to rate ' + esc(name) + '</a>' +
          '<small>One response per owner — that is the only way the averages mean anything.</small></p>';
      host.innerHTML = '<h2>Owner satisfaction</h2>' + head + comments + form;
      if (ME) bindForm(item, host);
    }

    function score(label, v) {
      var pct = Math.max(0, Math.min(100, (v || 0) / 5 * 100));
      return '<div class="sv-score"><b>' + (v ? v.toFixed(1) : '–') + '<small>/5</small></b>' +
        '<span>' + label + '</span><i class="sv-bar"><u style="width:' + pct + '%"></u></i></div>';
    }

    function stars(nm, label, mine) {
      var chosen = mine ? +mine[nm] : 5;
      var buttons = '';
      for (var i = 1; i <= 5; i++) buttons += '<button type="button" data-star data-star-name="' + nm +
        '" data-star-value="' + i + '" class="' + (i <= chosen ? 'on' : '') + '" aria-label="' +
        i + ' out of 5" aria-pressed="' + (i === chosen ? 'true' : 'false') + '">★</button>';
      return '<div class="star-field"><span>' + label + '</span><input type="hidden" name="' + nm +
        '" value="' + chosen + '"><div class="stars" role="radiogroup" aria-label="' + label +
        '">' + buttons + '</div></div>';
    }

    function formHtml(mine) {
      return '<form class="sv-form" data-sv-form>' +
        '<p>' + (mine ? 'You have rated this car. Change anything and save again.' : 'Own one? Rate it.') + '</p>' +
        '<div class="sv-grid">' +
        stars('overall', 'Overall', mine) +
        stars('reliability', 'Reliability', mine) +
        stars('running_cost', 'Running cost', mine) +
        '<label>Years owned<input type="number" name="years_owned" min="0" max="40" value="' +
          (mine ? (mine.years_owned || 0) : '') + '"></label>' +
        '<label class="sv-check"><input type="checkbox" name="would_buy_again"' +
          (mine && mine.would_buy_again ? ' checked' : '') + '> I would buy it again</label>' +
        '</div>' +
        '<textarea name="comment" rows="3" maxlength="900" placeholder="What should the next buyer know?">' +
          esc(mine ? mine.comment : '') + '</textarea>' +
        '<button class="btn" type="submit">Save my answer</button>' +
        '<span class="sv-msg" data-sv-msg></span></form>';
    }

    function bindForm(itemId, root) {
      var f = root.querySelector('[data-sv-form]');
      if (!f) return;
      f.addEventListener('click', function (e) {
        var b = e.target.closest('[data-star]');
        if (!b) return;
        var nm = b.getAttribute('data-star-name'), value = +b.getAttribute('data-star-value');
        f.querySelector('[name="' + nm + '"]').value = value;
        f.querySelectorAll('[data-star-name="' + nm + '"]').forEach(function (x) {
          var selected = +x.getAttribute('data-star-value') <= value;
          x.classList.toggle('on', selected);
          x.setAttribute('aria-pressed', +x.getAttribute('data-star-value') === value ? 'true' : 'false');
        });
      });
      f.addEventListener('submit', function (e) {
        e.preventDefault();
        var d = new FormData(f);
        var msg = f.querySelector('[data-sv-msg]');
        msg.textContent = 'Saving…';
        api('/api/survey', {
          item: itemId,
          overall: d.get('overall'), reliability: d.get('reliability'),
          running_cost: d.get('running_cost'), years_owned: d.get('years_owned'),
          would_buy_again: !!d.get('would_buy_again'), comment: d.get('comment'),
        }).then(function () {
          msg.textContent = 'Saved — thank you.';
          load();
        }).catch(function (err) { msg.textContent = (err && err.error) || 'Could not save.'; });
      });
    }

    function load() {
      fetch('/api/survey?item=' + encodeURIComponent(item), { credentials: 'same-origin' })
        .then(function (r) { return r.json(); }).then(render).catch(function () {
          host.innerHTML = '<h2>Owner satisfaction</h2><p class="sv-n"><b>No responses yet.</b> ' +
            'Ratings could not be loaded right now; the form returns when the connection does.</p>';
        });
    }
    document.addEventListener('cv:survey-saved', function (e) { if (e.detail.item === item) load(); });
    whenMe(load);
  }

  /* -------------------------------------------------------------- sign-in -- */

  function loginPage() {
    var host = document.getElementById('login-app');
    if (!host) return;
    var params = new URLSearchParams(location.search);
    var next = params.get('next') || '/account/';
    var why = { love: 'Sign in to love a car and keep the list.',
                survey: 'Sign in to rate a car you own.',
                garage: 'Sign in and your garage follows you to every device.' }[params.get('why')];
    var errs = { state: 'That sign-in attempt expired. Try again.',
                 token: 'The provider did not complete the sign-in. Try again.',
                 denied: 'The provider did not share an email address, so no account could be made.',
                 unconfigured: 'That sign-in method is not switched on yet. Use email and password.' };
    var err = errs[params.get('e')] || '';

    // If the provider probe fails the page must still offer email and password, not an
    // empty box: a sign-in form that renders only on a successful API call has one more
    // way to be broken than it needs.
    fetch('/api/auth/providers')
      .then(function (r) { return r.json(); })
      .catch(function () { return { email: true, google: false, apple: false }; })
      .then(function (p) {
      var social = '';
      if (p.google && p.google_client_id) {
        // Google Identity Services: the official button, then the credential is posted
        // to the Worker, which verifies the signature and sets the session cookie.
        social += '<div class="oauth-gis" data-gis-host><div id="gis-btn"></div></div>';
      } else if (p.google) social += '<a class="oauth g" href="/api/auth/google?next=' + encodeURIComponent(next) + '">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3z"/><path fill="#34A853" d="M12 22c2.7 0 5-.9 6.6-2.5l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.7-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22z"/><path fill="#FBBC05" d="M6.4 13.9a6 6 0 0 1 0-3.8V7.5H3.1a10 10 0 0 0 0 9z"/><path fill="#EA4335" d="M12 6.1c1.5 0 2.8.5 3.8 1.5l2.8-2.8A10 10 0 0 0 3.1 7.5l3.3 2.6C7.2 7.8 9.4 6.1 12 6.1z"/></svg>' +
        'Continue with Google</a>';
      if (p.apple) social += '<a class="oauth a" href="/api/auth/apple?next=' + encodeURIComponent(next) + '">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.4 12.7c0-2.3 1.9-3.4 2-3.5-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9-.7 0-1.8-.9-3-.8-1.5 0-2.9.9-3.7 2.3-1.6 2.7-.4 6.8 1.1 9 .8 1.1 1.7 2.3 2.9 2.2 1.2 0 1.6-.7 3-.7s1.8.7 3 .7c1.2 0 2-1.1 2.8-2.2.9-1.3 1.2-2.5 1.2-2.6 0 0-2.4-.9-2.4-3.5zM14.2 5.5c.6-.8 1-1.9.9-3-.9 0-2 .6-2.7 1.4-.6.7-1.1 1.8-.9 2.9 1 .1 2-.5 2.7-1.3z"/></svg>' +
        'Continue with Apple</a>';
      if (social) social = '<div class="oauth-row">' + social + '</div><div class="or"><span>or</span></div>';

      host.innerHTML =
        (why ? '<p class="login-why">' + esc(why) + '</p>' : '') +
        (err ? '<p class="login-err">' + esc(err) + '</p>' : '') +
        social +
        '<form data-login-form>' +
        '<div class="tabs"><button type="button" class="on" data-mode="login">Sign in</button>' +
        '<button type="button" data-mode="signup">Create account</button></div>' +
        '<label data-name-row hidden>Name<input name="name" autocomplete="name"></label>' +
        '<label>Email<input name="email" type="email" required autocomplete="email"></label>' +
        '<label>Password<input name="password" type="password" required minlength="8" autocomplete="current-password"></label>' +
        '<button class="btn wide" type="submit" data-submit>Sign in</button>' +
        '<p class="login-msg" data-msg></p>' +
        '<p class="login-fine">We store your email, your list and your preferences — nothing else, ' +
        'and nothing is sold. <a href="/privacy/">Privacy</a>.</p>' +
        '</form>';

      if (p.google && p.google_client_id) gisButton(p.google_client_id, next, host);

      var f = host.querySelector('[data-login-form]');
      var mode = 'login';
      host.querySelectorAll('[data-mode]').forEach(function (b) {
        b.addEventListener('click', function () {
          mode = b.getAttribute('data-mode');
          host.querySelectorAll('[data-mode]').forEach(function (x) { x.classList.toggle('on', x === b); });
          host.querySelector('[data-name-row]').hidden = mode !== 'signup';
          host.querySelector('[data-submit]').textContent = mode === 'signup' ? 'Create my account' : 'Sign in';
          f.querySelector('[name=password]').setAttribute('autocomplete',
            mode === 'signup' ? 'new-password' : 'current-password');
        });
      });
      f.addEventListener('submit', function (e) {
        e.preventDefault();
        var d = new FormData(f), msg = host.querySelector('[data-msg]');
        msg.textContent = 'Working…'; msg.className = 'login-msg';
        api('/api/auth/' + mode, {
          email: d.get('email'), password: d.get('password'), name: d.get('name') || '',
        }).then(function () { location.href = next.charAt(0) === '/' ? next : '/account/'; })
          .catch(function (err) {
            msg.textContent = (err && err.error) || 'That did not work.';
            msg.className = 'login-msg bad';
          });
      });
    });
  }

  function gisButton(clientId, next, host) {
    function onCredential(resp) {
      var msg = host.querySelector('[data-msg]');
      if (msg) { msg.textContent = 'Signing you in with Google…'; msg.className = 'login-msg'; }
      api('/api/auth/google/token', { credential: resp.credential })
        .then(function () { location.href = next.charAt(0) === '/' ? next : '/account/'; })
        .catch(function (err) {
          if (msg) { msg.textContent = (err && err.error) || 'Google sign-in did not complete.'; msg.className = 'login-msg bad'; }
        });
    }
    function render() {
      if (!window.google || !google.accounts || !google.accounts.id) return false;
      google.accounts.id.initialize({ client_id: clientId, callback: onCredential, ux_mode: 'popup',
        auto_select: false, itp_support: true });
      var el = document.getElementById('gis-btn');
      if (el) google.accounts.id.renderButton(el, { theme: 'outline', size: 'large', width: 320,
        text: 'continue_with', shape: 'pill', logo_alignment: 'left' });
      return true;
    }
    if (render()) return;
    var sc = document.createElement('script');
    sc.src = 'https://accounts.google.com/gsi/client'; sc.async = true; sc.defer = true;
    sc.onload = function () {
      if (!render()) {
        var h = host.querySelector('[data-gis-host]');
        if (h) h.innerHTML = '<a class="oauth g" href="/api/auth/google?next=' + encodeURIComponent(next) + '">Continue with Google</a>';
      }
    };
    sc.onerror = function () {
      var h = host.querySelector('[data-gis-host]');
      if (h) h.innerHTML = '<p class="login-msg">Google sign-in could not load (a content blocker?). Email and password still work.</p>';
    };
    document.head.appendChild(sc);
  }

  /* ------------------------------------------------------------- account -- */

  function accountPage() {
    var host = document.getElementById('account-app');
    if (!host) return;
    whenMe(function (u) {
      if (!u) {
        host.innerHTML = '<p>You are signed out. <a class="btn" href="/login/">Sign in</a></p>';
        return;
      }
      var likes = (u.likes || []);
      var garage = (u.prefs && u.prefs.garage) || [];
      var recent = (u.prefs && u.prefs.recent) || [];
      var ratings = u.ratings || [];
      host.innerHTML =
        '<div class="acct-head"><span class="acct-av big">' +
          esc((u.name || u.email).charAt(0).toUpperCase()) + '</span>' +
        '<div><h2>' + esc(u.name || u.email) + '</h2>' +
        '<p>' + esc(u.email) + ' · signed in with ' + esc(u.provider) + '</p></div>' +
        '<button class="btn ghost" data-signout>Sign out</button></div>' +
        '<section><h2>Cars you love <span class="cnt">' + likes.length + '</span></h2>' +
        (likes.length
          ? '<div class="acct-grid">' + likes.map(function (l) {
              return '<a class="acct-card" href="' + esc(l.url || '/') + '"><b>' + esc(l.name || l.item) + '</b></a>';
            }).join('') + '</div>'
          : '<p class="muted">Nothing yet. The heart on any car page adds it here.</p>') +
        '</section>' +
        '<section><h2>Your garage <span class="cnt">' + garage.length + '</span></h2>' +
        (garage.length
          ? '<div class="acct-grid">' + garage.map(function (g) {
              return '<a class="acct-card" href="' + esc(g.u || '/') + '"><b>' + esc(g.n || g.t || 'Saved car') + '</b></a>';
            }).join('') + '</div>'
          : '<p class="muted">Add a car from any model page and it follows you to every device.</p>') +
        '</section>' +
        '<section><h2>Your ratings <span class="cnt">' + ratings.length + '</span></h2>' +
        (ratings.length
          ? '<div class="acct-grid">' + ratings.map(function (r) {
              return '<div class="acct-card"><b>' + esc(r.item) + '</b><small>' + r.overall + '/5 overall</small></div>';
            }).join('') + '</div>'
          : '<p class="muted">No ratings yet. Ratings are saved to your account and follow you across devices.</p>') +
        '</section>' +
        '<section><h2>Recently viewed <span class="cnt">' + recent.length + '</span></h2>' +
        (recent.length
          ? '<div class="acct-grid">' + recent.slice(0, 12).map(function (r) {
              return '<a class="acct-card" href="' + esc(r.u || '/') + '"><b>' + esc(r.t || 'Viewed car') + '</b></a>';
            }).join('') + '</div>'
          : '<p class="muted">Cars you inspect will appear here and follow you across signed-in devices.</p>') +
        '</section>';
      host.querySelector('[data-signout]').addEventListener('click', function () {
        api('/api/auth/logout', {}).then(function () { location.href = '/'; });
      });
    });
  }

  /* ---------------------------------------------------------------- boot -- */

  fetch('/api/auth/me', { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(function (j) { setMe(j.user || null); })
    .catch(function () { setMe(null); })
    .then(function () {
      chip();
      migratePrefs();
      accountPage();
    });

  loveInit();
  surveyInit();
  loginPage();
})();
