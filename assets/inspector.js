/* /vin-check/ — free NHTSA VIN decoder and recall report. */
(function () {
  var form = document.getElementById('vin-form');
  var input = document.getElementById('vin');
  var out = document.getElementById('vin-result');
  if (!form || !input || !out) return;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function facts(vehicle) {
    var rows = [
      ['Year', vehicle.year], ['Make', vehicle.make], ['Model', vehicle.model],
      ['Trim / series', vehicle.trim], ['Body', vehicle.body], ['Engine', vehicle.engine],
      ['Fuel', vehicle.fuel], ['Drive', vehicle.drive], ['Built in', vehicle.plant_country],
    ].filter(function (row) { return row[1]; });
    return '<dl class="vin-facts">' + rows.map(function (row) {
      return '<div><dt>' + esc(row[0]) + '</dt><dd>' + esc(row[1]) + '</dd></div>';
    }).join('') + '</dl>';
  }

  function recall(row) {
    return '<article class="vin-recall' + (row.severe ? ' severe' : '') + '">' +
      '<div class="vin-recall-head"><b>' + esc(row.component || 'Recall campaign') + '</b>' +
      (row.severe ? '<span class="tag v-AVOID">safety-critical signal</span>' : '') + '</div>' +
      '<p><strong>Campaign ' + esc(row.campaign || '—') + '</strong>' +
      (row.report_date ? ' · ' + esc(row.report_date) : '') + '</p>' +
      (row.summary ? '<p>' + esc(row.summary) + '</p>' : '') +
      (row.consequence ? '<details><summary>Risk</summary><p>' + esc(row.consequence) + '</p></details>' : '') +
      (row.remedy ? '<details><summary>Remedy</summary><p>' + esc(row.remedy) + '</p></details>' : '') +
      '</article>';
  }

  function render(data) {
    var v = data.vehicle;
    var name = [v.year, v.make, v.model, v.trim].filter(Boolean).join(' ');
    var q = encodeURIComponent([v.year, v.make, v.model].join(' '));
    var nhtsa = 'https://www.nhtsa.gov/recalls?vin=' + encodeURIComponent(data.vin);
    var status = data.recall_count
      ? '<div class="vin-status bad"><b>' + data.recall_count + ' recall campaign' + (data.recall_count === 1 ? '' : 's') + ' found</b>' +
        '<span>' + (data.severe_count ? data.severe_count + ' includes a safety-critical signal. ' : '') + 'Ask a dealer to verify completion by VIN.</span></div>'
      : '<div class="vin-status good"><b>No campaigns returned for this year, make and model</b>' +
        '<span>This is not proof that every VIN-specific repair is complete. Verify on NHTSA before buying.</span></div>';
    out.innerHTML = '<section class="card vin-report"><p class="vin-eyebrow">Decoded by NHTSA</p>' +
      '<h2>' + esc(name) + '</h2>' + facts(v) + status +
      '<div class="hh-cta"><a class="btn" href="/search/?q=' + q + '">See MotorJury costs & verdicts</a>' +
      '<a class="btn ghost" href="' + nhtsa + '" target="_blank" rel="noopener">Verify on NHTSA</a></div></section>' +
      (data.recalls.length ? '<section class="card"><h2>Recall details</h2><div class="vin-recalls">' +
        data.recalls.map(recall).join('') + '</div>' +
        (data.recall_count > data.recalls.length
          ? '<p class="src-note">Showing the first ' + data.recalls.length + ' campaigns. Use the NHTSA link above for the complete record.</p>'
          : '') + '</section>' : '');
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var vin = input.value.toUpperCase().replace(/[\s-]+/g, '');
    input.value = vin;
    out.innerHTML = '<div class="card vin-loading">Checking NHTSA records…</div>';
    form.querySelector('button').disabled = true;
    fetch('/api/vin?vin=' + encodeURIComponent(vin), { credentials: 'same-origin' })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) throw new Error(data.error || 'Could not check this VIN.');
          return data;
        });
      })
      .then(render)
      .catch(function (error) {
        out.innerHTML = '<div class="card vin-error"><b>Could not complete the check</b><p>' + esc(error.message) + '</p></div>';
      })
      .finally(function () { form.querySelector('button').disabled = false; });
  });
})();
