/* share.js — one share control, in every footer.

   Uses the operating system's own share sheet where there is one (which on a phone is
   every app the reader already has, including the three the site publishes to), and falls
   back to copying the link. No third-party share widget: those are tracking scripts that
   happen to draw buttons, they cost a page ~40KB and they leak the reader's URL to whoever
   wrote them. */
(function () {
  var hosts = document.querySelectorAll('[data-share]');
  if (!hosts.length) return;

  function label(txt) {
    return '<button class="soc soc-share" data-share-btn title="Share this page" aria-label="Share this page">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18 16.1c-.8 0-1.5.3-2 .8l-7.1-4.2c.1-.2.1-.5.1-.7s0-.5-.1-.7L16 7.1c.5.5 1.2.8 2 .8a2.9 2.9 0 1 0-2.9-2.9c0 .2 0 .5.1.7L8.1 9.9a2.9 2.9 0 1 0 0 4.2l7.2 4.2c0 .2-.1.4-.1.6a2.8 2.8 0 1 0 2.8-2.8z"/></svg>' +
      '<span>' + txt + '</span></button>';
  }

  hosts.forEach(function (h) { h.innerHTML = label('Share'); });

  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-share-btn]');
    if (!b) return;
    var data = {
      title: document.title,
      text: (document.querySelector('meta[name=description]') || {}).content || document.title,
      url: location.href,
    };
    if (navigator.share) {
      navigator.share(data).catch(function () {});
      return;
    }
    var done = function (ok) {
      b.parentNode.innerHTML = label(ok ? 'Link copied' : 'Copy failed');
      setTimeout(function () { b.parentNode.innerHTML = label('Share'); }, 2500);
    };
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(function () { done(true); },
      function () { done(false); });
    else done(false);
  });
})();
