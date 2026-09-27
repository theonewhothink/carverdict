/* genius.js — Car Genius, the site's chat assistant, and the AI Brief button.

   Three ways in, one conversation:
     - the AI Brief button in the page tools bar: opens the panel with the bottom line of
       the page the reader is on; they can close it or keep asking
     - the Car Genius button in the corner of every page
     - the full page at /ask/ (also /ask/?q=… — a question someone shared)

   The conversation lives in sessionStorage, so it follows the reader from page to page in
   the same tab. Every question is sent with the path of the page the reader is on, so "is
   this year a good buy?" means this page's car. Answers stream from /api/genius.

   Nothing renders until /api/genius/status says the assistant is switched on, so a site
   without the key shows no dead buttons. */
(function () {
  var L = {
    en: { brief: 'AI Brief', ask: 'Ask Car Genius', ph: 'Ask about any car, year or cost…', send: 'Send',
          newc: 'New chat', close: 'Close', copy: 'Copy', copied: 'Copied', share: 'Share',
          think: 'Thinking…', look: 'Checking the records…', guide: 'Reading the guides…', pages: 'Finding pages…',
          briefq: 'AI Brief of this page', err: 'Something went wrong. Try again.', stop: 'Stop',
          note: 'Answers come from MotorJury data. AI can be wrong — check the linked page.',
          hi: 'Ask me which years to avoid, what breaks, what a car costs to own, or how two cars compare.' },
    pt: { brief: 'Resumo IA', ask: 'Perguntar ao Car Genius', ph: 'Pergunte sobre qualquer carro, ano ou custo…', send: 'Enviar',
          newc: 'Nova conversa', close: 'Fechar', copy: 'Copiar', copied: 'Copiado', share: 'Partilhar',
          think: 'A pensar…', look: 'A consultar os registos…', guide: 'A ler os guias…', pages: 'A procurar páginas…',
          briefq: 'Resumo IA desta página', err: 'Algo correu mal. Tente novamente.', stop: 'Parar',
          note: 'Respostas com dados MotorJury. A IA pode errar — confirme na página indicada.',
          hi: 'Pergunte que anos evitar, o que avaria, quanto custa ter um carro ou como dois carros se comparam.' },
    es: { brief: 'Resumen IA', ask: 'Pregunta a Car Genius', ph: 'Pregunta por cualquier coche, año o coste…', send: 'Enviar',
          newc: 'Nuevo chat', close: 'Cerrar', copy: 'Copiar', copied: 'Copiado', share: 'Compartir',
          think: 'Pensando…', look: 'Consultando los registros…', guide: 'Leyendo las guías…', pages: 'Buscando páginas…',
          briefq: 'Resumen IA de esta página', err: 'Algo salió mal. Inténtalo de nuevo.', stop: 'Detener',
          note: 'Respuestas con datos de MotorJury. La IA puede equivocarse: revisa la página enlazada.',
          hi: 'Pregúntame qué años evitar, qué se avería, cuánto cuesta tener un coche o cómo se comparan dos.' },
    fr: { brief: 'Résumé IA', ask: 'Demander à Car Genius', ph: 'Une question sur une voiture, une année, un coût…', send: 'Envoyer',
          newc: 'Nouvelle discussion', close: 'Fermer', copy: 'Copier', copied: 'Copié', share: 'Partager',
          think: 'Réflexion…', look: 'Consultation des données…', guide: 'Lecture des guides…', pages: 'Recherche de pages…',
          briefq: 'Résumé IA de cette page', err: 'Une erreur est survenue. Réessayez.', stop: 'Arrêter',
          note: "Réponses tirées des données MotorJury. L'IA peut se tromper — vérifiez la page citée.",
          hi: 'Demandez quelles années éviter, ce qui casse, ce que coûte une voiture ou comment deux modèles se comparent.' },
    de: { brief: 'KI-Kurzfassung', ask: 'Car Genius fragen', ph: 'Frag nach jedem Auto, Baujahr oder Kosten…', send: 'Senden',
          newc: 'Neuer Chat', close: 'Schließen', copy: 'Kopieren', copied: 'Kopiert', share: 'Teilen',
          think: 'Denke nach…', look: 'Prüfe die Daten…', guide: 'Lese die Ratgeber…', pages: 'Suche Seiten…',
          briefq: 'KI-Kurzfassung dieser Seite', err: 'Etwas ist schiefgelaufen. Bitte erneut versuchen.', stop: 'Stopp',
          note: 'Antworten aus MotorJury-Daten. KI kann irren — prüfe die verlinkte Seite.',
          hi: 'Frag, welche Baujahre man meiden sollte, was kaputtgeht, was ein Auto kostet oder wie zwei Autos abschneiden.' },
    he: { brief: 'תקציר AI', ask: 'שאלו את Car Genius', ph: 'שאלו על כל רכב, שנה או עלות…', send: 'שליחה',
          newc: 'שיחה חדשה', close: 'סגירה', copy: 'העתקה', copied: 'הועתק', share: 'שיתוף',
          think: 'חושב…', look: 'בודק את הנתונים…', guide: 'קורא את המדריכים…', pages: 'מחפש עמודים…',
          briefq: 'תקציר AI של העמוד', err: 'משהו השתבש. נסו שוב.', stop: 'עצירה',
          note: 'התשובות מבוססות על נתוני MotorJury. בינה מלאכותית עלולה לטעות — בדקו בעמוד המקושר.',
          hi: 'שאלו אילו שנים להימנע מהן, מה מתקלקל, כמה עולה להחזיק רכב או איך שני רכבים משתווים.' }
  };
  var lang = (document.documentElement.lang || 'en').slice(0, 2);
  var T = L[lang] || L.en;
  var PATH = location.pathname;
  var ON_ASK = /^\/ask\/?$/.test(PATH);
  var KEY = 'mj-genius-v1';

  var SPARK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11 2.5c.3 0 .5.2.6.5l1.2 3.7a4 4 0 0 0 2.5 2.5l3.7 1.2c.6.2.6 1 0 1.2l-3.7 1.2a4 4 0 0 0-2.5 2.5l-1.2 3.7c-.2.6-1 .6-1.2 0L9.2 15.3a4 4 0 0 0-2.5-2.5L3 11.6c-.6-.2-.6-1 0-1.2l3.7-1.2a4 4 0 0 0 2.5-2.5L10.4 3c.1-.3.3-.5.6-.5zm7.5 12c.2 0 .3.1.4.3l.5 1.4c.2.5.6.9 1.1 1.1l1.4.5c.4.1.4.6 0 .8l-1.4.5c-.5.2-.9.6-1.1 1.1l-.5 1.4c-.1.4-.6.4-.8 0l-.5-1.4a1.8 1.8 0 0 0-1.1-1.1l-1.4-.5c-.4-.1-.4-.6 0-.8l1.4-.5c.5-.2.9-.6 1.1-1.1l.5-1.4c.1-.2.2-.3.4-.3z"/></svg>';
  var SEND = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3.4 20.4 21 12 3.4 3.6l-.1 6.5L15 12 3.3 13.9z"/></svg>';

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  /* ---------- markdown, the small safe subset the answers use ---------- */
  function safeHref(u) {
    u = String(u).trim();
    if (/^\/(?!\/)/.test(u)) return u;
    if (/^https:\/\/(www\.)?motorjury\.com\//i.test(u)) return u.replace(/^https:\/\/(www\.)?motorjury\.com/i, '');
    if (/^https:\/\/([a-z0-9-]+\.)*(nhtsa\.gov|fueleconomy\.gov|epa\.gov)\//i.test(u)) return u;
    return null;
  }
  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>');
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (m, t, u) {
      var h = safeHref(u.replace(/&amp;/g, '&'));
      if (!h) return t;
      var ext = /^https:/.test(h);
      return '<a href="' + esc(h) + '"' + (ext ? ' target="_blank" rel="noopener"' : '') + '>' + t + '</a>';
    });
    return s;
  }
  function md(src) {
    var lines = String(src).replace(/\r/g, '').split('\n'), out = [], i = 0;
    while (i < lines.length) {
      var ln = lines[i];
      if (/^\s*$/.test(ln)) { i++; continue; }
      var h = /^(#{1,4})\s+(.*)$/.exec(ln);
      if (h) { out.push('<h4>' + inline(h[2]) + '</h4>'); i++; continue; }
      if (/^\s*\|.*\|\s*$/.test(ln) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        var head = ln.trim().replace(/^\||\|$/g, '').split('|');
        var rows = []; i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(lines[i].trim().replace(/^\||\|$/g, '').split('|')); i++; }
        out.push('<div class="g-tw"><table><thead><tr>' + head.map(function (c) { return '<th>' + inline(c.trim()) + '</th>'; }).join('') +
          '</tr></thead><tbody>' + rows.map(function (r) { return '<tr>' + r.map(function (c) { return '<td>' + inline(c.trim()) + '</td>'; }).join('') + '</tr>'; }).join('') +
          '</tbody></table></div>');
        continue;
      }
      if (/^\s*([-*•]|\d+[.)])\s+/.test(ln)) {
        var ordered = /^\s*\d/.test(ln), items = [];
        while (i < lines.length && /^\s*([-*•]|\d+[.)])\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*([-*•]|\d+[.)])\s+/, '')); i++; }
        var tag = ordered ? 'ol' : 'ul';
        out.push('<' + tag + '>' + items.map(function (x) { return '<li>' + inline(x) + '</li>'; }).join('') + '</' + tag + '>');
        continue;
      }
      var para = [];
      while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^(#{1,4})\s/.test(lines[i]) &&
             !/^\s*([-*•]|\d+[.)])\s+/.test(lines[i]) && !/^\s*\|.*\|\s*$/.test(lines[i])) { para.push(lines[i]); i++; }
      if (para.length) out.push('<p>' + para.map(inline).join('<br>') + '</p>');
      else i++;
    }
    return out.join('');
  }

  /* ---------- state ---------- */
  function load() {
    try { var s = JSON.parse(sessionStorage.getItem(KEY) || 'null'); if (s && Array.isArray(s.m)) return s; } catch (e) {}
    return { m: [], open: false };
  }
  var state = load();
  function save() { try { sessionStorage.setItem(KEY, JSON.stringify({ m: state.m.slice(-30), open: state.open })); } catch (e) {} }

  /* ---------- ui ---------- */
  var panel = null, list, input, sendBtn, busy = false, aborter = null, inline_ = false;

  function suggestions() {
    var s;
    if (/^\/cars\/[^/]+\/[^/]+\/\d{4}\/$/.test(PATH)) s = ['Is this year a good buy?', 'What breaks most on this car?', 'Is the year before or after better?'];
    else if (/^\/cars\/[^/]+\/[^/]+\/$/.test(PATH)) s = ['Which years should I avoid?', 'What is the best year to buy?', 'What does it cost to own?'];
    else if (/^\/guides\//.test(PATH)) s = ['Summarise this guide', 'Which year is the safest buy here?'];
    else s = ['Which used SUVs have the fewest complaints?', 'Honda CR-V: which years to avoid?', 'Toyota Camry vs Honda Accord, 2015-2018'];
    return lang === 'en' ? s : [];
  }

  function build(host) {
    panel = document.createElement('section');
    panel.className = 'genius' + (host ? ' genius-inline' : '');
    panel.setAttribute('aria-label', 'Car Genius');
    if (!host) { panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'false'); }
    panel.innerHTML =
      '<header class="g-hd"><span class="g-logo">' + SPARK + '</span><b>Car Genius</b>' +
      '<button type="button" class="g-ic g-new" data-g-new title="' + esc(T.newc) + '">' + esc(T.newc) + '</button>' +
      (host ? '' : '<button type="button" class="g-ic g-x" data-g-close aria-label="' + esc(T.close) + '">×</button>') + '</header>' +
      '<div class="g-list" aria-live="polite"></div>' +
      '<form class="g-form"><textarea rows="1" maxlength="1500" placeholder="' + esc(T.ph) + '" aria-label="' + esc(T.ph) + '"></textarea>' +
      '<button type="submit" class="g-send" aria-label="' + esc(T.send) + '">' + SEND + '</button></form>' +
      '<p class="g-note">' + esc(T.note) + '</p>';
    (host || document.body).appendChild(panel);
    list = panel.querySelector('.g-list');
    input = panel.querySelector('textarea');
    sendBtn = panel.querySelector('.g-send');
    panel.querySelector('form').addEventListener('submit', function (e) { e.preventDefault(); submit(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
    });
    input.addEventListener('input', grow);
    panel.addEventListener('click', function (e) {
      var t;
      if (e.target.closest('[data-g-close]')) { close(); return; }
      if (e.target.closest('[data-g-new]')) { if (aborter) aborter.abort(); state.m = []; save(); render(); input.focus(); return; }
      if ((t = e.target.closest('[data-g-sug]'))) { input.value = t.textContent; submit(); return; }
      if ((t = e.target.closest('[data-g-copy]'))) { copyMsg(t); return; }
      if ((t = e.target.closest('[data-g-share]'))) { shareMsg(t); return; }
    });
    if (!host) document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && panel.classList.contains('open')) close(); });
    render();
  }

  function grow() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 160) + 'px'; }

  function render() {
    if (!state.m.length) {
      list.innerHTML = '<div class="g-empty"><span class="g-logo g-big">' + SPARK + '</span><p>' + esc(T.hi) + '</p>' +
        '<div class="g-sugs">' + suggestions().map(function (s) { return '<button type="button" data-g-sug>' + esc(s) + '</button>'; }).join('') + '</div></div>';
      return;
    }
    list.innerHTML = state.m.map(function (m, i) { return bubble(m, i); }).join('');
    list.scrollTop = list.scrollHeight;
  }

  function bubble(m, i) {
    if (m.role === 'user') return '<div class="g-msg g-u"><div class="g-b" dir="auto">' + esc(m.label || m.content) + '</div></div>';
    var tools = m.content && !m.pending ? '<div class="g-act"><button type="button" data-g-copy="' + i + '">' + esc(T.copy) +
      '</button><button type="button" data-g-share="' + i + '">' + esc(T.share) + '</button></div>' : '';
    return '<div class="g-msg g-a' + (m.error ? ' g-err' : '') + '"><div class="g-b" dir="auto">' +
      (m.content ? md(m.content) : '') + (m.pending ? '<span class="g-status">' + esc(m.status || T.think) + '</span>' : '') +
      '</div>' + tools + '</div>';
  }

  function updateLast() {
    var nodes = list.querySelectorAll('.g-msg');
    var i = state.m.length - 1, node = nodes[nodes.length - 1];
    if (!node) { render(); return; }
    var stick = list.scrollHeight - list.scrollTop - list.clientHeight < 80;
    var tmp = document.createElement('div');
    tmp.innerHTML = bubble(state.m[i], i);
    node.replaceWith(tmp.firstChild);
    if (stick) list.scrollTop = list.scrollHeight;
  }

  function setBusy(b) {
    busy = b;
    sendBtn.disabled = false;
    sendBtn.classList.toggle('g-stop', b);
    sendBtn.setAttribute('aria-label', b ? T.stop : T.send);
    sendBtn.innerHTML = b ? '<span class="g-sq"></span>' : SEND;
  }

  function copyMsg(btn) {
    var m = state.m[+btn.getAttribute('data-g-copy')];
    if (!m || !navigator.clipboard) return;
    navigator.clipboard.writeText(m.content).then(function () {
      btn.textContent = T.copied; setTimeout(function () { btn.textContent = T.copy; }, 1800);
    });
  }
  function shareMsg(btn) {
    var i = +btn.getAttribute('data-g-share'), m = state.m[i], q = state.m[i - 1];
    if (!m) return;
    var question = q && !q.brief ? q.content : '';
    var url = question ? location.origin + '/ask/?q=' + encodeURIComponent(question.slice(0, 300))
                       : location.origin + PATH;
    var d = { url: url, title: question ? 'Car Genius: ' + question : document.title,
              text: m.content.replace(/[#*|`[\]]/g, '').replace(/\(\/[^)]*\)/g, '').slice(0, 280) };
    if (window.MJShare) window.MJShare.open(d);
    else if (navigator.share) navigator.share(d).catch(function () {});
  }

  function open() {
    if (!panel) build();
    if (inline_) { input.focus(); return; }
    panel.classList.add('open');
    document.documentElement.classList.add('genius-open');
    state.open = true; save();
    setTimeout(function () { input.focus(); }, 60);
  }
  function close() {
    if (!panel || inline_) return;
    panel.classList.remove('open');
    document.documentElement.classList.remove('genius-open');
    state.open = false; save();
    var fab = document.querySelector('.genius-fab');
    if (fab) fab.focus();
  }

  function submit() {
    if (busy) { if (aborter) aborter.abort(); return; }
    var q = input.value.trim();
    if (!q) return;
    input.value = ''; grow();
    state.m.push({ role: 'user', content: q });
    ask('chat');
  }

  function brief() {
    open();
    if (busy) return;
    state.m.push({ role: 'user', content: T.briefq, label: T.briefq, brief: true });
    ask('brief');
  }

  var STATUS = { search_cars: T.look, get_model_history: T.look, search_guides: T.guide, read_guide: T.guide, search_pages: T.pages };

  function ask(mode) {
    var history = state.m.filter(function (m) { return !m.error && m.content; })
      .map(function (m) { return { role: m.role, content: m.content }; });
    var a = { role: 'assistant', content: '', pending: true };
    state.m.push(a);
    render();
    setBusy(true);
    aborter = window.AbortController ? new AbortController() : null;
    fetch('/api/genius', {
      method: 'POST', credentials: 'same-origin', signal: aborter ? aborter.signal : undefined,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: mode, page: ON_ASK ? null : PATH, messages: history })
    }).then(function (res) {
      if (!res.body || !res.body.getReader) return res.text().then(function (t) { feed(t, a); });
      var reader = res.body.getReader(), dec = new TextDecoder(), buf = '';
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) { if (buf) feed(buf, a); return; }
          buf += dec.decode(r.value, { stream: true });
          var cut = buf.lastIndexOf('\n\n');
          if (cut >= 0) { feed(buf.slice(0, cut), a); buf = buf.slice(cut + 2); }
          return pump();
        });
      }
      return pump();
    }).catch(function (e) {
      if (!(e && e.name === 'AbortError') && !a.content) { a.content = T.err; a.error = true; }
    }).then(function () {
      a.pending = false;
      if (!a.content) { a.content = T.err; a.error = true; }
      setBusy(false); save(); updateLast();
    });
  }

  function feed(chunk, a) {
    chunk.split('\n\n').forEach(function (ev) {
      var line = ev.replace(/^data: ?/, '').trim();
      if (!line) return;
      var o; try { o = JSON.parse(line); } catch (e) { return; }
      if (o.t === 'text') { a.content += o.d; a.status = ''; }
      else if (o.t === 'status') { a.status = STATUS[String(o.d).split(',')[0]] || T.think; }
      else if (o.t === 'error') { if (!a.content) a.error = true; a.content += (a.content ? '\n\n' : '') + o.d; }
      updateLast();
    });
  }

  /* ---------- boot ---------- */
  function enable() {
    document.documentElement.classList.add('genius-on');
    document.querySelectorAll('[data-genius-brief]').forEach(function (b) {
      b.hidden = false;
      var s = b.querySelector('span'); if (s) s.textContent = T.brief;
      b.addEventListener('click', brief);
    });
    var host = document.querySelector('[data-genius-page]');
    if (host) {
      inline_ = true;
      build(host);
      var q = new URLSearchParams(location.search).get('q');
      if (q && !busy) { input.value = q.slice(0, 1500); history.replaceState(null, '', location.pathname); submit(); }
      return;
    }
    var fab = document.createElement('button');
    fab.type = 'button';
    fab.className = 'genius-fab';
    fab.setAttribute('aria-label', T.ask);
    fab.innerHTML = SPARK + '<span>Car Genius</span>';
    fab.addEventListener('click', function () { panel && panel.classList.contains('open') ? close() : open(); });
    document.body.appendChild(fab);
    if (state.open && state.m.length && window.innerWidth >= 900) open();
  }

  function unavailable() {
    var host = document.querySelector('[data-genius-page]');
    if (host) host.innerHTML = '<div class="card"><p>Car Genius is not available right now. Every figure it would give you is on the ' +
      '<a href="/cars/">car pages</a> and in the <a href="/guides/">guides</a>.</p></div>';
  }

  var cached = null;
  try { cached = JSON.parse(sessionStorage.getItem('mj-genius-status') || 'null'); } catch (e) {}
  if (cached && Date.now() - cached.at < 300000) { cached.enabled ? enable() : unavailable(); return; }
  fetch('/api/genius/status', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : { enabled: false }; })
    .then(function (j) {
      try { sessionStorage.setItem('mj-genius-status', JSON.stringify({ enabled: !!j.enabled, at: Date.now() })); } catch (e) {}
      j.enabled ? enable() : unavailable();
    }).catch(unavailable);
})();
