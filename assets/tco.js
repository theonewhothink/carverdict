/* tco.js — the price card's live recalculation.

   The published figures are class-level estimates. The moment a reader types the price
   they are actually being asked to pay, every derived number should follow it: the resale
   value in five years, the depreciation, the five-year total and the cost per mile. That
   is the difference between a page that shows a number and a page that answers a question.

   Depreciation is scaled, not recomputed: the retained-value ratio for this car's age
   already lives in the published pair (price today, worth in five years), so a different
   purchase price moves the whole curve proportionally. */
(function () {
  var box = document.querySelector('[data-tco]');
  if (!box) return;
  var input = document.querySelector('[data-price-input]');
  if (!input) return;

  var base = +box.getAttribute('data-price') || 0;
  var dep5 = +box.getAttribute('data-dep5') || 0;
  var run5 = +box.getAttribute('data-run5') || 0;
  var ins = +box.getAttribute('data-ins') || 0;
  var fuel = +box.getAttribute('data-fuel') || 0;
  if (!base) return;
  var resale0 = Math.max(0, base - dep5);

  function fx() {
    var g = window.CV_GEO || {};
    return { m: (g.fx || 1), sym: (g.sym || '$'), car: (g.car_idx || g.maint_idx || 1),
             ins: (g.ins_idx || 1), maint: (g.maint_idx || 1),
             fuelR: (g.fuel_usd_l ? g.fuel_usd_l / 0.91 : 1) };
  }
  function fmt(usd, idx) {
    var g = fx();
    var v = usd * (idx || 1) * g.m;
    return g.sym + Math.round(v).toLocaleString();
  }
  function set(sel, usd, kind) {
    var el = box.querySelector(sel);
    if (!el) return;
    // the generator wraps the figure in a geo-aware span; write to that one so the two
    // layers stay in agreement about what the underlying dollar figure is
    var tgt = el.querySelector('[data-usd]') || el;
    var g = fx();
    tgt.textContent = fmt(usd, kind === 'car' ? g.car : kind === 'ins' ? g.ins : 1);
    tgt.setAttribute('data-usd', Math.round(usd));
  }

  function draw() {
    var price = +input.value;
    if (!isFinite(price) || price < 200) price = base;
    var scale = price / base;
    var dep = dep5 * scale;
    var resale = resale0 * scale;
    var g = fx();
    // running cost is a fuel/parts mix and is re-priced the way the rest of the page is
    var runLocal = fuel * 5 * g.fuelR + Math.max(0, run5 - fuel * 5) * g.maint;
    var totalLocal = dep * g.car + ins * 5 * g.ins + runLocal;

    set('[data-tco-dep]', dep, 'car');
    set('[data-tco-resale]', resale, 'car');
    var t = box.querySelector('[data-tco-total]');
    if (t) t.textContent = g.sym + Math.round(totalLocal * g.m).toLocaleString();
    var pm = box.querySelector('[data-tco-mile]');
    if (pm) {
      var perMile = totalLocal / (5 * 12000) * g.m;
      var metric = (window.CV_GEO && window.CV_GEO.units === 'metric');
      pm.textContent = g.sym + (metric ? (perMile / 1.60934).toFixed(2) : perMile.toFixed(2));
      var lbl = pm.parentNode.querySelector('span');
      if (lbl) lbl.textContent = metric
        ? 'Per kilometre driven, at 19,300 km a year'
        : 'Per mile driven, at 12,000 miles a year';
    }
    box.classList.toggle('edited', Math.abs(scale - 1) > 0.001);
  }

  input.addEventListener('input', draw);
  document.addEventListener('cv:geo', draw);
  if (window.CV_GEO) draw();
})();
