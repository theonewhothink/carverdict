/* An ownership total built only from the published running-cost band and reader inputs. */
(function () {
  function money(n) { return '$' + Math.round(n).toLocaleString(); }
  document.querySelectorAll('[data-ownership-planner]').forEach(function (root) {
    var form = root.querySelector('form'), result = root.querySelector('[data-ownership-result]');
    function calculate(event) {
      if (event) event.preventDefault();
      var data = new FormData(form);
      var values = ['purchase', 'resale', 'insurance', 'repairs', 'years'].map(function (key) {
        var raw = String(data.get(key) == null ? '' : data.get(key)).trim();
        return raw === '' ? NaN : Number(raw);
      });
      if (values.some(function (v) { return !Number.isFinite(v) || v < 0; }) || values[4] < 1) {
        result.textContent = 'Enter the four actual money inputs and a holding period to calculate a total.';
        return;
      }
      var purchase = values[0], resale = values[1], insurance = values[2], repairs = values[3], years = values[4];
      var depreciation = purchase - resale;
      var low = depreciation + years * (+root.dataset.runningLow + insurance + repairs);
      var high = depreciation + years * (+root.dataset.runningHigh + insurance + repairs);
      result.innerHTML = '<b>' + money(low) + '–' + money(high) + ' total</b><span>' +
        money(low / (years * 12)) + '–' + money(high / (years * 12)) + '/month over ' + years +
        ' year' + (years === 1 ? '' : 's') + '</span><small>Depreciation from your purchase and resale inputs: ' +
        money(depreciation) + '. Negative values mean your resale assumption exceeds the purchase price.</small>';
    }
    form.addEventListener('submit', calculate);
    form.addEventListener('input', function () { if (form.checkValidity()) calculate(); });
  });
})();
