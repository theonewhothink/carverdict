/* gallery.js — pulls extra photographs of this model from its Wikimedia Commons category.

   Why client-side: there are ~17,000 model pages and Commons allows one category listing
   per request. Doing it at build time would add roughly an hour to every deploy. Fetching
   on view costs the build nothing, and the gallery is always current.

   Attribution: each image's photographer and licence are read from Commons and printed
   once, under the grid. That is what CC-BY / CC-BY-SA require, and it keeps the credit off
   the photographs themselves. Nothing is copied — every file is hotlinked from Commons. */
(function () {
  var card = document.querySelector('[data-commons-cat]');
  if (!card) return;
  var cat = card.getAttribute('data-commons-cat');
  var grid = card.querySelector('[data-gal]');
  var creditEl = card.querySelector('[data-gal-credits]');
  var API = 'https://commons.wikimedia.org/w/api.php?origin=*&format=json&formatversion=2';
  var MAX = 12;

  function jsonp(params) {
    return fetch(API + '&' + params).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }

  function thumb(title, w) {
    return 'https://commons.wikimedia.org/wiki/Special:FilePath/' +
      encodeURIComponent(title.replace(/^File:/, '').replace(/ /g, '_')) + '?width=' + w;
  }

  function strip(html) {
    var d = document.createElement('div');
    d.innerHTML = html || '';
    return (d.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  }

  function fail(msg) {
    card.querySelector('h2').insertAdjacentHTML('afterend',
      '<p class="muted">' + msg + '</p>');
    grid.remove();
    if (creditEl) creditEl.remove();
  }

  function listFiles(title, limit) {
    return jsonp('action=query&list=categorymembers&cmtype=file&cmlimit=' + limit +
                 '&cmtitle=' + encodeURIComponent(title))
      .then(function (j) {
        return ((j.query || {}).categorymembers || [])
          .map(function (x) { return x.title; })
          .filter(function (f) { return /\.(jpe?g|png|webp)$/i.test(f); });
      })
      .catch(function () { return []; });
  }

  // Commons usually files photographs in per-generation subcategories, so the parent
  // category alone returns almost nothing. Top up from subcategories when it is thin.
  listFiles('Category:' + cat, 40)
    .then(function (files) {
      if (files.length >= MAX) return files;
      return jsonp('action=query&list=categorymembers&cmtype=subcat&cmlimit=6&cmtitle=' +
                   encodeURIComponent('Category:' + cat))
        .then(function (j) {
          var subs = ((j.query || {}).categorymembers || []).map(function (x) { return x.title; });
          if (!subs.length) return files;
          return Promise.all(subs.map(function (s) { return listFiles(s, 8); }))
            .then(function (lists) {
              lists.forEach(function (l) {
                l.forEach(function (f) { if (files.indexOf(f) < 0) files.push(f); });
              });
              return files;
            });
        })
        .catch(function () { return files; });
    })
    .then(function (files) {
      files = files.slice(0, MAX);
      if (!files.length) throw new Error('empty');
      return jsonp('action=query&prop=imageinfo&iiprop=extmetadata|url&iiurlwidth=640&titles=' +
                   encodeURIComponent(files.join('|')))
        .then(function (info) { return { files: files, info: info }; });
    })
    .then(function (res) {
      var pages = ((res.info.query || {}).pages) || [];
      var meta = {};
      pages.forEach(function (p) {
        var ii = (p.imageinfo || [])[0] || {};
        var ex = ii.extmetadata || {};
        meta[p.title] = {
          artist: strip((ex.Artist || {}).value) || 'Unknown photographer',
          licence: strip((ex.LicenseShortName || {}).value) || 'see file page',
          page: ii.descriptionurl || ('https://commons.wikimedia.org/wiki/' + encodeURIComponent(p.title))
        };
      });

      grid.innerHTML = res.files.map(function (f) {
        var name = f.replace(/^File:/, '').replace(/\.[^.]+$/, '');
        return '<a class="gal-cell" href="#" data-lb data-credit="' +
          ((meta[f] || {}).artist || '') + ' · ' + ((meta[f] || {}).licence || '') + '">' +
          '<img loading="lazy" src="' + thumb(f, 520) + '" alt="' +
          name.replace(/"/g, '&quot;') + '"></a>';
      }).join('');

      if (creditEl) {
        var seen = {}, credits = [];
        res.files.forEach(function (f) {
          var m = meta[f]; if (!m) return;
          var key = m.artist + '|' + m.licence;
          if (seen[key]) return;
          seen[key] = 1;
          credits.push(m.artist + ' (' + m.licence + ')');
        });
        creditEl.innerHTML = 'Photographs via Wikimedia Commons — ' +
          credits.join(' · ') +
          '. Images are hotlinked from Commons, not copied. <a href="/methodology/">Sources</a>.';
      }
    })
    .catch(function () {
      fail('No additional free photographs are catalogued for this model yet.');
    });
})();
