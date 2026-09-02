/* gallery.js — pulls extra photographs of this model from its Wikimedia Commons category,
   scored by resolution, aspect and detail so the best press-style shots lead the grid.

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
          .filter(function (f) { return /\.(jpe?g|png|webp|webm|ogv|mp4)$/i.test(f); });
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
      // Score every candidate instead of taking the category's first files. 50 titles is
      // the API ceiling for one imageinfo call, and one call is all the scoring costs.
      files = files.slice(0, 50);
      if (!files.length) throw new Error('empty');
      return jsonp('action=query&prop=imageinfo&iiprop=extmetadata|url|size|mime&iiurlwidth=640&titles=' +
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
          page: ii.descriptionurl || ('https://commons.wikimedia.org/wiki/' + encodeURIComponent(p.title)),
          w: ii.width || 0, h: ii.height || 0, bytes: ii.size || 0,
          url: ii.url || '', mime: ii.mime || '', video: /^video\//.test(ii.mime || '') || /\.(webm|ogv|mp4)$/i.test(p.title)
        };
      });

      // Press-style shot preference: high resolution, landscape framing, real detail.
      // Sharpness is approximated by JPEG bytes per pixel - a soft or heavily
      // compressed frame carries measurably fewer bytes than a crisp one.
      function score(m) {
        if (!m || !m.w || !m.h) return 0;
        if (m.w < 640 || m.h < 400) return 0;              // below hero quality
        var res = Math.min(m.w, 2400) / 2400;              // resolution, capped
        var r = m.w / m.h, asp;
        if (r >= 1.2 && r <= 1.9) asp = 1;                 // classic press landscape
        else if (r > 1.9) asp = Math.max(0.4, 1 - (r - 1.9) / 2); // panorama
        else if (r >= 1) asp = 0.75;                       // near-square
        else asp = 0.35;                                   // portrait
        var bpp = m.bytes ? m.bytes / (m.w * m.h) : 0;
        var sharp = bpp ? 0.8 + Math.min(bpp / 0.5, 1) * 0.2 : 0.85;
        return res * asp * sharp;
      }
      var videos = res.files.filter(function (f) { return meta[f] && meta[f].video; });
      var ranked = res.files.filter(function (f) { return !(meta[f] && meta[f].video); })
        .map(function (f) { return { f: f, s: score(meta[f]) }; })
        .filter(function (x) { return x.s > 0; })
        .sort(function (a, b) { return b.s - a.s; })
        .slice(0, MAX)
        .map(function (x) { return x.f; });
      // If Commons returned no usable size metadata, fall back to the old behaviour
      // rather than an empty gallery.
      var images = ranked.length ? ranked : res.files.filter(function (f) {
        return !(meta[f] && meta[f].video);
      }).slice(0, MAX);
      res.files = images.concat(videos.slice(0, 3)).slice(0, MAX);

      function cell(f, w, cls) {
        var name = f.replace(/^File:/, '').replace(/\.[^.]+$/, '');
        if ((meta[f] || {}).video) {
          return '<div class="' + cls + ' media-video"><video controls preload="metadata" playsinline poster="' +
            thumb(f, w) + '"><source src="' + ((meta[f] || {}).url || thumb(f, w)) + '" type="' +
            ((meta[f] || {}).mime || 'video/webm') + '">Video: ' + name.replace(/</g, '&lt;') + '</video></div>';
        }
        return '<button type="button" class="' + cls + ' lb-trigger" data-lb aria-label="Enlarge ' +
          name.replace(/"/g, '&quot;') + '" data-credit="' +
          ((meta[f] || {}).artist || '') + ' · ' + ((meta[f] || {}).licence || '') + '">' +
          '<img loading="lazy" referrerpolicy="no-referrer" src="' + thumb(f, w) + '" alt="' +
          name.replace(/"/g, '&quot;') + '">' + '</button>';
      }

      // Weave the strongest shots through the article first: every
      // <figure data-gal-slot> in the biography takes one photograph, the rest
      // fill the grid at the end. One sequence, one lightbox.
      // The hero must never be empty while the article has photographs. Three cases:
      // the catalogue had no photo (figure.noimg); the catalogue photo failed to load
      // (img.naturalWidth 0 after load, or onerror already marked the .ph); or it fails
      // later - an error listener swaps the first gallery shot in either way.
      var hero = document.querySelector('[data-model-hero]');
      var heroFile = null;
      function heroBroken() {
        if (!hero) return false;
        if (hero.classList.contains('noimg')) return true;
        var im = hero.querySelector('img');
        if (!im) return true;
        if (im.complete && im.naturalWidth === 0) return true;
        return !!hero.querySelector('.ph.noimg');
      }
      function promoteHero() {
        if (!hero || !images.length) return;
        heroFile = images[0];
        hero.classList.remove('noimg');
        hero.innerHTML = cell(heroFile, 1100, 'hero-from-gallery');
      }
      if (heroBroken()) promoteHero();
      else if (hero) {
        var him = hero.querySelector('img');
        if (him) him.addEventListener('error', function () { if (!heroFile) promoteHero(); });
      }
      // Put motion after two stills when Commons has it: a video belongs in the story,
      // not in a disconnected media bin at the bottom of the page.
      var sequence = images.filter(function (f) { return f !== heroFile; });
      videos.slice(0, 3).forEach(function (f, i) { sequence.splice(Math.min(2 + i * 3, sequence.length), 0, f); });
      var slots = document.querySelectorAll('figure[data-gal-slot]');
      var used = 0;
      slots.forEach(function (slot) {
        if (used >= sequence.length) return;
        var f = sequence[used++];
        slot.innerHTML = cell(f, 900, 'bio-shot') +
          '<figcaption>' + ((meta[f] || {}).artist || 'Wikimedia Commons') +
          ' · ' + ((meta[f] || {}).licence || 'CC') + '</figcaption>';
        slot.removeAttribute('hidden');
      });
      var rest = sequence.slice(used);
      if (rest.length) {
        grid.innerHTML = rest.map(function (f) { return cell(f, 520, 'gal-cell'); }).join('');
      } else {
        grid.closest('.card').style.display = 'none';
      }

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

// An in-article slot that nothing filled (site not yet approved, blocked, or no demand)
// must not sit in the story as a 280px hole. AdSense marks these data-ad-status="unfilled"
// on approved sites; on unapproved ones it marks nothing, so the check is "no iframe yet".
setTimeout(function () {
  document.querySelectorAll('ins.adsbygoogle.bio-ad').forEach(function (el) {
    if (!el.querySelector('iframe') || el.getAttribute('data-ad-status') === 'unfilled') el.style.display = 'none';
  });
}, 8000);
