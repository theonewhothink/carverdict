/* lightbox.js — photos NEVER navigate off-site.
   Any element carrying data-lb (or an .ph / .photo wrapper) opens an in-page viewer with
   the full image + attribution. The viewer is a gallery: every data-lb image on the page
   joins one sequence, browsable with on-screen arrows, the keyboard (← → Esc) and touch
   swipe, so it works identically on desktop and mobile. Attribution stays visible
   (CC requirement) but the click target is internal. */
(function () {
  var box, imgEl, capEl, cntEl, items = [], idx = 0;

  function build() {
    box = document.createElement('div');
    box.className = 'lb';
    box.setAttribute('hidden', '');
    box.innerHTML =
      '<div class="lb-bd"></div>' +
      '<figure class="lb-fig">' +
      '<button class="lb-x" aria-label="Close">&times;</button>' +
      '<button class="lb-nav lb-prev" aria-label="Previous photo">&#8249;</button>' +
      '<button class="lb-nav lb-next" aria-label="Next photo">&#8250;</button>' +
      '<img alt="">' +
      '<figcaption></figcaption>' +
      '<span class="lb-count"></span></figure>';
    document.body.appendChild(box);
    imgEl = box.querySelector('img');
    capEl = box.querySelector('figcaption');
    cntEl = box.querySelector('.lb-count');
    box.querySelector('.lb-bd').addEventListener('click', close);
    box.querySelector('.lb-x').addEventListener('click', close);
    box.querySelector('.lb-prev').addEventListener('click', function (e) { e.stopPropagation(); step(-1); });
    box.querySelector('.lb-next').addEventListener('click', function (e) { e.stopPropagation(); step(1); });
    document.addEventListener('keydown', function (e) {
      if (box.hasAttribute('hidden')) return;
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowLeft') step(-1);
      else if (e.key === 'ArrowRight') step(1);
    });
    // touch swipe — horizontal drag of 40px+ moves the sequence
    var x0 = null, y0 = null;
    box.addEventListener('touchstart', function (e) {
      if (e.touches.length !== 1) return;
      x0 = e.touches[0].clientX; y0 = e.touches[0].clientY;
    }, { passive: true });
    box.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      var dy = e.changedTouches[0].clientY - y0;
      x0 = y0 = null;
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) step(dx < 0 ? 1 : -1);
    }, { passive: true });
  }

  // full-size version of a Commons thumb URL
  function big(src) {
    return src.replace(/([?&])width=\d+/, '$1width=1400');
  }

  function collect() {
    items = [];
    document.querySelectorAll('a.ph, a.photo, [data-lb]').forEach(function (a) {
      var img = a.querySelector('img') || (a.tagName === 'IMG' ? a : null);
      if (!img || !img.src) return;
      var card = a.closest('.lib-card, .hero-art, figure');
      items.push({
        src: big(img.src),
        title: (card && card.querySelector('b') ? card.querySelector('b').textContent : img.alt) || img.alt,
        credit: a.getAttribute('data-credit') || 'Photo: Wikimedia Commons · CC licence',
        el: a
      });
    });
  }

  function show() {
    var it = items[idx];
    if (!it) return;
    imgEl.src = it.src;
    imgEl.alt = it.title || '';
    capEl.innerHTML = '<b>' + (it.title || '') + '</b><span>' + it.credit + '</span>';
    cntEl.textContent = items.length > 1 ? (idx + 1) + ' / ' + items.length : '';
    var nav = items.length > 1 ? '' : 'none';
    box.querySelector('.lb-prev').style.display = nav;
    box.querySelector('.lb-next').style.display = nav;
    // pre-load the neighbours so a swipe feels instant
    [idx + 1, idx - 1].forEach(function (i) {
      var n = items[(i + items.length) % items.length];
      if (n) { var pre = new Image(); pre.src = n.src; }
    });
  }

  function step(d) {
    if (!items.length) return;
    idx = (idx + d + items.length) % items.length;
    show();
  }

  function open() {
    if (!box) build();
    show();
    box.removeAttribute('hidden');
    document.body.style.overflow = 'hidden';
  }
  function close() {
    if (!box) return;
    box.setAttribute('hidden', '');
    imgEl.src = '';
    document.body.style.overflow = '';
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest('a.ph, a.photo, [data-lb]');
    if (!a) return;
    var img = a.querySelector('img') || (a.tagName === 'IMG' ? a : null);
    if (!img || !img.src) return;
    e.preventDefault();          // never leave the site
    collect();                   // galleries load late; rebuild the sequence per click
    idx = 0;
    for (var i = 0; i < items.length; i++) if (items[i].el === a) { idx = i; break; }
    open();
  });
})();
