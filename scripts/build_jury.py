"""The car jury: pick one of two cars, fill a ten-bay garage, see the world's verdict.

Only cars with a checked author and licence for their photograph enter the jury
(data/jury_cars.json). The game runs in the browser; verdicts are counted by the Worker.
"""
import hashlib
import html
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
esc = html.escape
REQUIRED = ('id', 'n', 'b', 'u', 'p', 't', 'l', 'lu')


@lru_cache(maxsize=1)
def cars():
    rows = json.loads((ROOT / 'data/jury_cars.json').read_text())
    ids = set()
    for row in rows:
        if not all(row.get(k) for k in REQUIRED) or 'a' not in row:
            raise ValueError('Jury car lacks a checked photograph record: ' + str(row.get('n')))
        if row['id'] in ids:
            raise ValueError('Duplicate jury car: ' + row['id'])
        flickr = row['t'].startswith('https://live.staticflickr.com/') and row.get('s', '').startswith('https://www.flickr.com/photos/')
        if not (row['t'].startswith('https://upload.wikimedia.org/wikipedia/commons/thumb/') or flickr) or not row['lu'].startswith('https://'):
            raise ValueError('Jury photograph must be a licensed Commons or Flickr file: ' + row['n'])
        ids.add(row['id'])
    return rows


@lru_cache(maxsize=1)
def assets():
    out = SITE / 'assets'
    out.mkdir(parents=True, exist_ok=True)
    data = json.dumps(cars(), ensure_ascii=False, separators=(',', ':'))
    (out / 'jury-data.json').write_text(data)
    version = hashlib.sha256(data.encode()).hexdigest()[:10]

    def emit(name, text):
        stem, suffix = name.rsplit('.', 1)
        hashed = stem + '.' + hashlib.sha256(text.encode()).hexdigest()[:10] + '.' + suffix
        (out / hashed).write_text(text)
        return hashed
    core = emit('jury-core.mjs', (ROOT / 'assets/jury-core.mjs').read_text())
    app = emit('jury.mjs', (ROOT / 'assets/jury.mjs').read_text().replace('./jury-core.mjs', './' + core).replace('__JURY_VERSION__', version))
    return '<script type="module" src="/assets/' + app + '"></script>'


def commons(row):
    return row.get('s') or 'https://commons.wikimedia.org/wiki/File:' + row['p'].replace(' ', '_')


def small(url):
    return url.replace('/960px-', '/330px-').replace('_b.jpg', '_n.jpg')


def credit(row):
    author = esc(row['a']) if row['a'] else 'the author named on the file page'
    return (f'<span data-photo-attribution><a href="{esc(commons(row), quote=True)}" rel="noopener">{esc(row["n"])} photo</a> '
            f'by {author}, <a href="{esc(row["lu"], quote=True)}" rel="noopener license">{esc(row["l"])}</a></span>')


def home_block():
    """Front-door invitation; two fixed, credited photographs so the page works without JavaScript."""
    by_name = {r['n']: r for r in cars()}
    pair = [by_name[n] for n in ('Ferrari F40', 'Lamborghini Countach') if n in by_name]
    photos = ''.join(f'<img src="{esc(small(r["t"]), quote=True)}" alt="{esc(r["n"])} · reference photograph" '
                     f'width="330" height="206" loading="lazy" decoding="async" referrerpolicy="no-referrer">' for r in pair)
    credits = ' · '.join(credit(r) for r in pair)
    return ('<section class="jury-home"><div><p class="eyebrow">New · the world’s car jury</p><h2>Two cars. One verdict. Yours.</h2>'
            f'<p>Pick the car you would rather have, again and again. Your picks fill a ten-bay dream garage you can share, '
            f'and every verdict counts toward a world ranking of {len(cars())} cars.</p>'
            '<a class="button" href="/jury/">Start judging →</a></div>'
            f'<div><div class="jury-home-photos">{photos}</div><small>Photos: {credits}</small></div></section>')


def page_body(lang, rows, brands):
    from jury_i18n import PAGE, JS, LANGS, NAMES, path
    P = PAGE[lang]
    home = path(lang)
    login = '/login/?next=' + home
    n, b = len(rows), brands
    faq = ''.join(f'<h3>{esc(q)}</h3><p>{esc(a.format(n=n, b=b))}</p>' for q, a in P['faq'])
    strings = dict(JS['en'], **JS[lang])
    data = json.dumps({'lang': lang, 'path': home, 's': strings}, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    switch = ' · '.join(f'<a href="{path(l)}" hreflang="{l}" lang="{l}"' + (' aria-current="page"' if l == lang else '') + f'>{NAMES[l]}</a>' for l in LANGS)
    return (
        f'<script type="application/json" data-jury-i18n>{data}</script>'
        f'<section class="collection-hero compact jury-hero"><p class="eyebrow">{esc(P["eyebrow"])}</p><h1>{esc(P["h1"])}</h1>'
        f'<p class="lede">{esc(P["lede"].format(n=n))}</p></section>'
        f'<section class="jury-shared card" data-jury-shared hidden><p class="eyebrow">{esc(P["shared_eyebrow"])}</p><h2>{esc(P["shared_h2"])}</h2>'
        f'<p class="note" data-jury-shared-taste></p><ol class="jury-bays" data-jury-shared-grid></ol><a class="button" href="{home}">{esc(P["build_own"])}</a></section>'
        f'<section class="jury-arena" data-jury aria-label="{esc(P["arena_aria"], quote=True)}">'
        f'<div class="jury-mode" role="group" aria-label="{esc(P["mode_aria"], quote=True)}"><button type="button" data-jury-mode="free" aria-pressed="true">{esc(P["mode_free"])}</button>'
        f'<button type="button" data-jury-mode="daily" aria-pressed="false">{esc(P["mode_daily"])}</button><button type="button" data-jury-mode="quiz" aria-pressed="false">{esc(P["mode_quiz"])}</button></div>'
        f'<p class="jury-progress" role="status" data-jury-progress>{esc(P["loading"])}</p>'
        '<div class="jury-pair" data-jury-pair></div><p class="jury-credits" data-jury-credits></p>'
        '<p class="jury-verdict" role="status" data-jury-verdict></p>'
        f'<div class="jury-signin" data-jury-signin hidden><p><b>{esc(P["signin_b"])}</b> {esc(P["signin_text"])}</p>'
        f'<div class="actions"><a class="button" href="{login}">{esc(P["signin_btn"])}</a><button type="button" class="secondary" data-jury-later>{esc(P["not_now"])}</button></div></div>'
        f'<div class="actions"><button type="button" class="secondary" data-jury-skip>{esc(P["skip"])}</button></div>'
        f'<details class="jury-talk" data-jury-talk><summary>{esc(P["talk_summary"])}</summary><ul data-jury-talk-list></ul><p class="note" role="status" data-jury-talk-status></p>'
        f'<form hidden><label for="jury-say">{esc(P["your_view"])}</label><textarea id="jury-say" maxlength="300" rows="2" required placeholder="{esc(P["talk_ph"], quote=True)}"></textarea><div class="actions"><button>{esc(P["post"])}</button></div><p class="note" data-jury-talk-as></p></form>'
        f'<p class="note" data-jury-talk-gate><a href="{login}">{esc(P["talk_gate_link"])}</a> {esc(P["talk_gate"])}</p></details>'
        '<div class="jury-result" data-jury-result hidden></div>'
        f'<noscript><p>{P["noscript"]}</p></noscript></section>'
        f'<section class="jury-garage" data-jury-garage aria-label="{esc(P["garage_aria"], quote=True)}"><h2>{esc(P["garage_h2"])} <span data-jury-count></span></h2>'
        '<p class="note" data-jury-taste></p><div class="jury-swap" data-jury-swap hidden></div><ol class="jury-bays" data-jury-bays></ol>'
        f'<div class="actions"><button type="button" data-jury-share>{esc(P["share"])}</button><button type="button" class="secondary" data-jury-copy>{esc(P["copy"])}</button>'
        f'<button type="button" class="secondary" data-jury-empty>{esc(P["empty"])}</button></div><p role="status" data-jury-status></p>'
        f'<details><summary>{esc(P["garage_credits"])}</summary><ul data-jury-garage-credits></ul></details>'
        f'<p class="note">{esc(P["saved_note"])}</p></section>'
        f'<section class="card"><h2>{esc(P["verdict_h2"])}</h2><p data-jury-top-status>{esc(P["counting"])}</p><progress class="jury-bar" data-jury-top-bar hidden aria-label="{esc(P["bar_aria"], quote=True)}"></progress><ol data-jury-top-list></ol>'
        f'<a href="{path(lang, "/jury/ranking/")}">{esc(P["full_ranking"])}</a></section>'
        f'<section class="card"><h2>{esc(P["faq_h2"])}</h2>{faq}'
        f'<p class="note">{esc(P["photo_note"])} <a href="/catalogue-notes/">{esc(P["photo_note_link"])}</a>.</p></section>'
        f'<nav class="jury-langs" aria-label="{esc(P["languages"], quote=True)}">{esc(P["languages"])}: {switch}</nav>'), data


def ranking_body(lang, data):
    from jury_i18n import PAGE, path
    P = PAGE[lang]
    return (f'<script type="application/json" data-jury-i18n>{data}</script>'
            f'<section class="collection-hero compact"><p class="eyebrow">{esc(P["eyebrow"])}</p><h1>{esc(P["r_h1"])}</h1>'
            f'<p class="lede">{esc(P["r_lede"])}</p></section>'
            f'<section class="card" data-jury-ranking><label for="jury-country">{esc(P["show_from"])}</label> <select id="jury-country" data-jury-country></select>'
            f'<p role="status" data-jury-ranking-status>{esc(P["counting"])}</p><progress class="jury-bar" data-jury-ranking-bar hidden aria-label="{esc(P["bar_aria"], quote=True)}"></progress><ol class="jury-ranking-list" data-jury-ranking-list></ol>'
            f'<noscript><p>{esc(P["r_noscript"])}</p></noscript><a class="button" href="{path(lang)}">{esc(P["add_verdicts"])}</a></section>')


def app_schema(lang, n):
    from jury_i18n import PAGE
    P = PAGE[lang]
    return [{'@context': 'https://schema.org', '@type': 'WebApplication', 'name': P['title'].split(':')[0].strip(),
             'description': P['description'].format(n=n), 'applicationCategory': 'GameApplication', 'operatingSystem': 'Any',
             'browserRequirements': 'Requires JavaScript', 'inLanguage': lang, 'isAccessibleForFree': True,
             'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'}}]


def main(write):
    from jury_i18n import LANGS, PAGE, path
    rows = cars()
    script = assets()
    brands = len({r['b'] for r in rows})
    for lang in LANGS:
        P = PAGE[lang]
        body, data = page_body(lang, rows, brands)
        write(path(lang), P['title'], body, script, description=P['description'].format(n=len(rows)), jsonld=app_schema(lang, len(rows)))
        write(path(lang, '/jury/ranking/'), P['r_title'], ranking_body(lang, data), script, description=P['r_description'])
        # The ranking is rendered in the browser from live counts, so it stays out of search
        # until it can be served as text. shortcut: client-rendered; upgrade to Worker-rendered
        # HTML once the ranking has enough verdicts to be worth citing.
        f = SITE / path(lang, '/jury/ranking/').strip('/') / 'index.html'
        f.write_text(f.read_text().replace('</head>', '<meta name="robots" content="noindex,follow"></head>', 1))
    print(f'JURY: {len(rows)} licensed cars from {brands} marques in {len(LANGS)} languages; game, garage, daily round and ranking built')
