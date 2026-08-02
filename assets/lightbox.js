/* lightbox.js — photos NEVER navigate off-site.
   Any element carrying data-lb (or an .ph / .photo wrapper) opens an in-page viewer with the
   full image + attribution text. Attribution stays visible (CC requirement) but the click
   target is internal. Esc / backdrop / X closes. Keyboard accessible. */
(function () {
  var box, imgEl, capEl;

  function build() {
    box = document.createElement('div');
    box.className = 'lb';
    box.setAttribute('hidden', '');
    box.innerHTML =
      '<div class="lb-bd"></div>' +
      '<figure class="lb-fig">' +
      '<button class="lb-x" aria-label="Close">&times;</button>' +
      '<img alt="">' +
      '<figcaption></figcaption></figure>';
    document.body.appendChild(box);
    imgEl = box.querySelector('img');
    capEl = box.querySelector('figcaption');
    box.querySelector('.lb-bd').addEventListener('click', close);
    box.querySelector('.lb-x').addEventListener('click', close);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  }

  function open(src, title, credit) {
    if (!box) build();
    imgEl.src = src;
    imgEl.alt = title || '';
    capEl.innerHTML = '<b>' + (title || '') + '</b><span>' + (credit || 'Photo: Wikimedia Commons (CC)') + '</span>';
    box.removeAttribute('hidden');
    document.body.style.overflow = 'hidden';
  }
  function close() {
    if (!box) return;
    box.setAttribute('hidden', '');
    imgEl.src = '';
    document.body.style.overflow = '';
  }

  // full-size version of a Commons thumb URL
  function big(src) {
    return src.replace(/([?&])width=\d+/, '$1width=1400');
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest('a.ph, a.photo, [data-lb]');
    if (!a) return;
    var img = a.querySelector('img') || (a.tagName === 'IMG' ? a : null);
    if (!img || !img.src) return;
    e.preventDefault();          // never leave the site
    var card = a.closest('.lib-card, .hero-art, figure');
    var title = (card && card.querySelector('b') ? card.querySelector('b').textContent : img.alt) || img.alt;
    var credit = a.getAttribute('data-credit') || 'Photo: Wikimedia Commons · CC licence';
    open(big(img.src), title, credit);
  });
})();
