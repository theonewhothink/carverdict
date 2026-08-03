/* rate.js — "Rate your love": a 5-star rating on every car page.

   Stored on the device (no account, no personal data), and mirrored into a rollup the
   Garage and the most-loved list read. A shared, cross-visitor leaderboard needs a
   write endpoint — the site is static assets today — so this is deliberately honest:
   it shows YOUR rating and the count of cars you have rated, and never invents a
   community average it cannot measure. */
(function () {
  var host = document.querySelector('[data-rate]');
  if (!host) return;
  var qid = host.getAttribute('data-rate');
  var name = host.getAttribute('data-rate-name') || '';
  var box = host.querySelector('[data-stars]');
  var note = host.querySelector('[data-rate-note]');
  var KEY = 'cv_prefs';

  function prefs() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
  }
  function save(p) { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch (e) {} }

  var p = prefs();
  p.ratings = p.ratings || {};
  var mine = p.ratings[qid] ? p.ratings[qid].r : 0;

  function star(i, filled) {
    return '<button class="star' + (filled ? ' on' : '') + '" data-v="' + i +
      '" role="radio" aria-checked="' + (filled ? 'true' : 'false') +
      '" aria-label="' + i + ' out of 5">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.6l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.4 6.2 20.5l1.1-6.5L2.6 9.4l6.5-.9z"/></svg>' +
      '</button>';
  }

  function draw(v, justSet) {
    var out = '';
    for (var i = 1; i <= 5; i++) out += star(i, i <= v);
    box.innerHTML = out;
    box.querySelectorAll('.star').forEach(function (b) {
      b.addEventListener('mouseenter', function () { paint(+b.dataset.v); });
      b.addEventListener('focus', function () { paint(+b.dataset.v); });
      b.addEventListener('click', function () { set(+b.dataset.v); });
    });
    box.addEventListener('mouseleave', function () { paint(mine); });
    if (note) {
      var total = Object.keys(p.ratings).length;
      note.textContent = v
        ? (justSet ? 'Saved — you rated the ' + name + ' ' + v + '/5.' : 'You rated this ' + v + '/5.') +
          (total > 1 ? ' ' + total + ' cars rated on this device.' : '')
        : 'Tap a star. Ratings are kept on your device and feed your most-loved list.';
    }
  }

  function paint(v) {
    box.querySelectorAll('.star').forEach(function (b) {
      b.classList.toggle('on', +b.dataset.v <= v);
    });
  }

  function set(v) {
    mine = v;
    p = prefs();
    p.ratings = p.ratings || {};
    p.ratings[qid] = { r: v, n: name, u: location.pathname, t: Date.now() };
    save(p);
    draw(v, true);
  }

  draw(mine, false);
})();
