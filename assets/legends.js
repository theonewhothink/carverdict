/* legends.js — renders the home-page Legends row from /assets/legends.json.

   Rendered client-side on purpose: the home page is the most-rebuilt file on the site and
   the roster changes on its own cadence. If the feed is missing (a build where the people
   harvest failed), the whole section removes itself rather than leaving an empty hole. */
(function () {
  var sec = document.querySelector('[data-legends]');
  if (!sec) return;
  var grid = sec.querySelector('[data-legends-grid]');
  var SHOW = 12;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  fetch('/assets/legends.json')
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (all) {
      if (!all || !all.length) throw new Error('empty');
      // one from each group first, so the row reads as a cross-section rather than
      // twelve racing drivers in a row
      var byGroup = {}, order = [], pick = [];
      all.forEach(function (p) {
        if (!byGroup[p.g]) { byGroup[p.g] = []; order.push(p.g); }
        byGroup[p.g].push(p);
      });
      var i = 0;
      while (pick.length < SHOW) {
        var added = false;
        for (var g = 0; g < order.length && pick.length < SHOW; g++) {
          var list = byGroup[order[g]];
          if (list[i]) { pick.push(list[i]); added = true; }
        }
        if (!added) break;
        i++;
      }
      grid.innerHTML = pick.map(function (p) {
        var meta = [p.y, p.d].filter(Boolean).join(' · ').slice(0, 70);
        var ph = p.i
          ? '<span class="pp-ph"><img loading="lazy" src="' + esc(p.i) + '" alt="' + esc(p.n) + '"></span>'
          : '<span class="pp-ph pp-noimg"></span>';
        return '<a class="pp-card" href="/legends/' + esc(p.s) + '/">' + ph +
          '<b>' + esc(p.n) + '</b><small>' + esc(meta) + '</small></a>';
      }).join('');
    })
    .catch(function () { sec.remove(); });
})();
