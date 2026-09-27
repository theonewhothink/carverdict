/* share.js — the share sheet behind every Share button on the site.

   Every page carries two ways in: the Share button in the page tools bar at the top of the
   content, and the one in the footer. Both open one sheet: WhatsApp, X, Facebook, LinkedIn,
   Telegram, Reddit, email, copy link, and the device's own share sheet where there is one.

   No third-party share widget: those are tracking scripts that happen to draw buttons, they
   cost a page ~40KB and they leak the reader's URL to whoever wrote them. These are plain
   links to each network's public share URL, opened only when the reader taps one.

   window.MJShare.open({url, title, text}) lets other scripts (Car Genius answers) reuse it. */
(function () {
  var L = {
    en: ['Share', 'Share this page', 'Copy link', 'Link copied', 'Copy failed', 'More options', 'Email', 'Close'],
    pt: ['Partilhar', 'Partilhar esta página', 'Copiar link', 'Link copiado', 'Falha ao copiar', 'Mais opções', 'Email', 'Fechar'],
    es: ['Compartir', 'Compartir esta página', 'Copiar enlace', 'Enlace copiado', 'No se pudo copiar', 'Más opciones', 'Correo', 'Cerrar'],
    fr: ['Partager', 'Partager cette page', 'Copier le lien', 'Lien copié', 'Échec de la copie', "Plus d'options", 'E-mail', 'Fermer'],
    de: ['Teilen', 'Diese Seite teilen', 'Link kopieren', 'Link kopiert', 'Kopieren fehlgeschlagen', 'Weitere Optionen', 'E-Mail', 'Schließen'],
    he: ['שיתוף', 'שיתוף העמוד', 'העתקת קישור', 'הקישור הועתק', 'ההעתקה נכשלה', 'אפשרויות נוספות', 'אימייל', 'סגירה']
  };
  var lang = (document.documentElement.lang || 'en').slice(0, 2);
  var T = L[lang] || L.en;

  var ICON = {
    share: 'M18 16.1c-.8 0-1.5.3-2 .8l-7.1-4.2c.1-.2.1-.5.1-.7s0-.5-.1-.7L16 7.1c.5.5 1.2.8 2 .8a2.9 2.9 0 1 0-2.9-2.9c0 .2 0 .5.1.7L8.1 9.9a2.9 2.9 0 1 0 0 4.2l7.2 4.2c0 .2-.1.4-.1.6a2.8 2.8 0 1 0 2.8-2.8z',
    whatsapp: 'M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.3-.5.1-1 .1-1.7-.1-.4-.1-.9-.3-1.5-.6-2.7-1.2-4.4-3.9-4.6-4.1-.1-.2-1.1-1.5-1.1-2.8s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.3 0 .5l-.3.5-.4.4c-.1.1-.3.3-.1.6.1.3.7 1.1 1.5 1.8 1 .9 1.8 1.2 2.1 1.3.3.1.4.1.6-.1l.8-1c.2-.3.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.7-.1 1.3z',
    x: 'M17.8 3h3.1l-6.8 7.7L22 21h-6.2l-4.9-6.4L5.3 21H2.2l7.3-8.3L2 3h6.4l4.4 5.8L17.8 3zm-1.1 16.2h1.7L7.4 4.7H5.6l11.1 14.5z',
    facebook: 'M13.5 21v-8h2.7l.4-3.1h-3.1V7.9c0-.9.3-1.5 1.6-1.5h1.6V3.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4 1.4-4 4.1v2.3H7.5V13h2.8v8h3.2z',
    linkedin: 'M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.75h4v11H3v-11zm6.5 0h3.8v1.5h.1c.5-1 1.8-1.9 3.7-1.9 4 0 4.7 2.6 4.7 6v5.4h-4v-4.8c0-1.2 0-2.6-1.6-2.6s-1.9 1.2-1.9 2.5v4.9h-4v-11z',
    telegram: 'M21.9 4.3 18.7 19.4c-.2 1-.9 1.3-1.7.8l-4.8-3.5-2.3 2.2c-.3.3-.5.5-1 .5l.3-4.9 8.9-8c.4-.3-.1-.5-.6-.2L6.6 13.2 1.9 11.8c-1-.3-1-1 .2-1.5L20.6 3.2c.9-.3 1.6.2 1.3 1.1z',
    reddit: 'M22 12.1a2.2 2.2 0 0 0-3.7-1.6 10.7 10.7 0 0 0-5.7-1.8l1-4.6 3.2.7a1.6 1.6 0 1 0 .2-1l-3.6-.8a.5.5 0 0 0-.6.4l-1.1 5.3a10.8 10.8 0 0 0-5.8 1.8A2.2 2.2 0 1 0 3.5 14a4.3 4.3 0 0 0 0 .6c0 3.3 3.8 5.9 8.5 5.9s8.5-2.6 8.5-5.9a4.3 4.3 0 0 0 0-.6 2.2 2.2 0 0 0 1.5-1.9zM7.5 13.6a1.5 1.5 0 1 1 1.5 1.5 1.5 1.5 0 0 1-1.5-1.5zm8.4 4c-1 .8-2.4 1.2-3.9 1.2s-2.9-.4-3.9-1.2a.4.4 0 0 1 .6-.6c.8.6 2 1 3.3 1s2.5-.4 3.3-1a.4.4 0 1 1 .6.6zm-.4-2.5a1.5 1.5 0 1 1 1.5-1.5 1.5 1.5 0 0 1-1.5 1.5z',
    mail: 'M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm9 7.2L4 7.3V17h16V7.3l-8 4.9zM4.5 7l7.5 4.6L19.5 7h-15z',
    link: 'M10.6 13.4a1 1 0 0 1 0-1.4l3.5-3.5a1 1 0 1 1 1.4 1.4L12 13.4a1 1 0 0 1-1.4 0zM8.5 19.5a4.5 4.5 0 0 1-3.2-7.7l2.5-2.5a1 1 0 0 1 1.4 1.4l-2.5 2.5a2.5 2.5 0 0 0 3.5 3.5l2.5-2.5a1 1 0 0 1 1.4 1.4l-2.5 2.5a4.5 4.5 0 0 1-3.1 1.4zm7.8-5.4a1 1 0 0 1-.7-1.7l2.5-2.5a2.5 2.5 0 0 0-3.5-3.5l-2.5 2.5a1 1 0 0 1-1.4-1.4l2.5-2.5a4.5 4.5 0 0 1 6.3 6.3L17 13.8a1 1 0 0 1-.7.3z',
    more: 'M6 10.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm6 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm6 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z'
  };
  function svg(d) { return '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="' + d + '"/></svg>'; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function current() {
    var canon = document.querySelector('link[rel=canonical]');
    var url = location.href.split('#')[0];
    // share the canonical address when it is this same page, so every share counts once
    if (canon && canon.href && new URL(canon.href).pathname === location.pathname) url = canon.href;
    return {
      url: url,
      title: document.title,
      text: (document.querySelector('meta[name=description]') || {}).content || document.title
    };
  }

  function targets(d) {
    var u = encodeURIComponent(d.url), t = encodeURIComponent(d.title), tx = encodeURIComponent(d.text || d.title);
    return [
      ['whatsapp', 'WhatsApp', 'https://wa.me/?text=' + encodeURIComponent((d.title ? d.title + ' ' : '') + d.url)],
      ['x', 'X', 'https://twitter.com/intent/tweet?text=' + t + '&url=' + u],
      ['facebook', 'Facebook', 'https://www.facebook.com/sharer/sharer.php?u=' + u],
      ['linkedin', 'LinkedIn', 'https://www.linkedin.com/sharing/share-offsite/?url=' + u],
      ['telegram', 'Telegram', 'https://t.me/share/url?url=' + u + '&text=' + t],
      ['reddit', 'Reddit', 'https://www.reddit.com/submit?url=' + u + '&title=' + t],
      ['mail', T[6], 'mailto:?subject=' + t + '&body=' + tx + '%0A%0A' + u]
    ];
  }

  var sheet = null, lastFocus = null, data = null;

  function close() {
    if (!sheet) return;
    sheet.classList.remove('open');
    document.removeEventListener('keydown', onKey);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  function onKey(e) { if (e.key === 'Escape') close(); }

  function open(d) {
    data = d || current();
    lastFocus = document.activeElement;
    if (!sheet) {
      sheet = document.createElement('div');
      sheet.className = 'mj-share';
      sheet.innerHTML = '<div class="mj-share-scrim" data-share-close></div>' +
        '<div class="mj-share-box" role="dialog" aria-modal="true" aria-labelledby="mj-share-h"></div>';
      document.body.appendChild(sheet);
      sheet.addEventListener('click', function (e) {
        if (e.target.closest('[data-share-close]')) { close(); return; }
        var c = e.target.closest('[data-share-copy]');
        if (c) { copy(c); return; }
        if (e.target.closest('[data-share-native]')) {
          navigator.share({ title: data.title, text: data.text, url: data.url }).then(close, function () {});
          return;
        }
        if (e.target.closest('a.mj-share-t')) setTimeout(close, 300);
      });
    }
    var box = sheet.querySelector('.mj-share-box');
    box.innerHTML = '<div class="mj-share-hd"><h2 id="mj-share-h">' + esc(T[1]) + '</h2>' +
      '<button type="button" class="mj-share-x" data-share-close aria-label="' + esc(T[7]) + '">×</button></div>' +
      '<p class="mj-share-title">' + esc(data.title) + '</p>' +
      '<div class="mj-share-grid">' + targets(data).map(function (t) {
        return '<a class="mj-share-t mj-' + t[0] + '" href="' + esc(t[2]) + '" target="_blank" rel="noopener noreferrer">' +
          '<span class="mj-share-ic">' + svg(ICON[t[0]]) + '</span><span>' + esc(t[1]) + '</span></a>';
      }).join('') +
      (navigator.share ? '<button type="button" class="mj-share-t mj-more" data-share-native><span class="mj-share-ic">' +
        svg(ICON.more) + '</span><span>' + esc(T[5]) + '</span></button>' : '') +
      '</div>' +
      '<div class="mj-share-copy"><input readonly value="' + esc(data.url) + '" aria-label="Link">' +
      '<button type="button" class="btn" data-share-copy>' + svg(ICON.link) + '<span>' + esc(T[2]) + '</span></button></div>';
    sheet.classList.add('open');
    document.addEventListener('keydown', onKey);
    var first = box.querySelector('.mj-share-t');
    if (first) first.focus();
  }

  function copy(btn) {
    var lbl = btn.querySelector('span');
    var done = function (ok) {
      lbl.textContent = ok ? T[3] : T[4];
      setTimeout(function () { lbl.textContent = T[2]; }, 2200);
    };
    if (navigator.clipboard) navigator.clipboard.writeText(data.url).then(function () { done(true); }, function () { fallback(); });
    else fallback();
    function fallback() {
      var inp = sheet.querySelector('.mj-share-copy input');
      inp.select();
      try { done(document.execCommand('copy')); } catch (e) { done(false); }
    }
  }

  // the footer host keeps its place and becomes a button that opens the sheet
  document.querySelectorAll('[data-share]').forEach(function (h) {
    h.innerHTML = '<button class="soc soc-share" type="button" data-share-open title="' + esc(T[1]) + '" aria-label="' +
      esc(T[1]) + '">' + svg(ICON.share) + '<span>' + esc(T[0]) + '</span></button>';
  });
  document.querySelectorAll('[data-share-label]').forEach(function (s) { s.textContent = T[0]; });

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-share-open]')) { e.preventDefault(); open(); }
  });

  window.MJShare = { open: open };
})();
