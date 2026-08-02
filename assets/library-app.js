/* localized library renderer — builds the same brand grid + A-Z from shared JSON */
(function () {
  var el = document.getElementById('lib-app');
  if (!el) return;
  var S = JSON.parse(el.getAttribute('data-i18n'));
  function thumb(f, w) { return 'https://commons.wikimedia.org/wiki/Special:FilePath/' + encodeURIComponent(f.replace(/ /g, '_')) + '?width=' + w; }
  fetch('/assets/library-data.json').then(function (r) { return r.json(); }).then(function (j) {
    var brands = Object.keys(j);
    var html = '<h2 class="sec">' + S.lib_top_brands + '</h2><div class="brand-grid">';
    brands.slice(0, 24).forEach(function (b) {
      html += '<a class="brand-tile" href="/library/' + j[b].s + '/"><b>' + b + '</b><small>' + j[b].m.length + ' ' + S.lib_models + '</small></a>';
    });
    html += '</div><h2 class="sec">' + S.lib_all_brands + '</h2><div class="az"><div class="az-group">';
    brands.sort().forEach(function (b) {
      html += '<a href="/library/' + j[b].s + '/">' + b + ' <span>' + j[b].m.length + '</span></a>';
    });
    html += '</div></div>';
    el.innerHTML = html;
  });
})();
