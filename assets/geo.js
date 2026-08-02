/* geo.js — auto-international cost layer + preference memory.
   Country: Cloudflare edge (/cdn-cgi/trace) — no third-party API, no PII stored.
   Prices: /assets/geo-prices.json (labeled estimates, CI-refreshed from public retail series).
   User can override country; choice is remembered locally. */
(function () {
  var KEY = 'cv_geo', OV = 'cv_geo_override', TABLE = null, GEO = null;

  function money(usd, g) {
    var v = usd * (g.fx || 1);
    var s = v >= 1000 ? Math.round(v).toLocaleString() : v.toFixed(v < 10 ? 2 : 0);
    return (g.sym || '$') + s;
  }

  function recalc(g) {
    document.querySelectorAll('[data-usd]').forEach(function (el) {
      var usd = parseFloat(el.getAttribute('data-usd'));
      var kind = el.getAttribute('data-kind') || '';
      var idx = kind === 'ins' ? (g.ins_idx || 1) : kind === 'maint' ? (g.maint_idx || 1) : 1;
      var fuelAdj = kind === 'fuel' ? (g.fuel_usd_l / 0.91) : 1;
      el.textContent = money(usd * idx * fuelAdj, g);
    });
    var t = document.getElementById('geo-total');
    if (t) {
      var base = parseFloat(t.getAttribute('data-usd') || '0');
      var fuelShare = parseFloat(t.getAttribute('data-fuel-usd') || '0');
      var rest = base - fuelShare;
      t.textContent = money(fuelShare * (g.fuel_usd_l / 0.91) + rest * (g.maint_idx || 1), g);
    }
  }

  function chip(g) {
    document.querySelectorAll('[data-geo-chip]').forEach(function (h) {
      var opts = Object.keys(TABLE).filter(function (k) { return k[0] !== '_'; }).sort().map(function (cc) {
        return '<option value="' + cc + '"' + (cc === g.cc ? ' selected' : '') + '>' + TABLE[cc].flag + ' ' + TABLE[cc].name + '</option>';
      }).join('');
      h.innerHTML =
        '<div class="geo-chip" title="Regional cost reference — estimates, refreshed nightly. See methodology.">' +
        '<span class="geo-flag">' + g.flag + '</span>' +
        '<select id="geo-sel" aria-label="Country">' + opts + '</select>' +
        '<span class="geo-facts">' + g.cur + ' · fuel ' + (g.sym || '$') + (g.fuel_usd_l * (g.fx || 1)).toFixed(2) +
        '/L · ' + (g.sym || '$') + (g.kwh_usd * (g.fx || 1)).toFixed(2) + '/kWh</span></div>';
      var sel = h.querySelector('#geo-sel');
      sel.addEventListener('change', function () {
        try { localStorage.setItem(OV, sel.value); } catch (e) {}
        GEO = Object.assign({ cc: sel.value }, TABLE[sel.value]);
        chip(GEO); recalc(GEO);
      });
    });
  }

  function apply(g) {
    if (!g) return;
    GEO = g;
    document.documentElement.setAttribute('data-cc', g.cc);
    window.CV_GEO = g;
    chip(g); recalc(g);
    document.dispatchEvent(new CustomEvent('cv:geo', { detail: g }));
  }

  fetch('/assets/geo-prices.json').then(function (r) { return r.json(); }).then(function (tbl) {
    TABLE = tbl;
    var ov = null, cached = null;
    try { ov = localStorage.getItem(OV); cached = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) {}
    if (ov && TABLE[ov]) return apply(Object.assign({ cc: ov }, TABLE[ov]));
    if (cached && Date.now() - cached.ts < 864e5 && TABLE[cached.cc]) return apply(Object.assign({ cc: cached.cc }, TABLE[cached.cc]));
    fetch('/cdn-cgi/trace').then(function (r) { return r.text(); }).catch(function () { return ''; }).then(function (txt) {
      var m = /loc=([A-Z]{2})/.exec(txt || '');
      var cc = (m && TABLE[m[1]]) ? m[1] : 'US';
      try { localStorage.setItem(KEY, JSON.stringify({ ts: Date.now(), cc: cc })); } catch (e) {}
      apply(Object.assign({ cc: cc }, TABLE[cc]));
    });
  });
})();
