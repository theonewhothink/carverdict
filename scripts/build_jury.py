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
        if not row['t'].startswith('https://upload.wikimedia.org/wikipedia/commons/thumb/') or not row['lu'].startswith('https://'):
            raise ValueError('Jury photograph must be a licensed Commons file: ' + row['n'])
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
    return 'https://commons.wikimedia.org/wiki/File:' + row['p'].replace(' ', '_')


def credit(row):
    author = esc(row['a']) if row['a'] else 'the author named on the file page'
    return (f'<span data-photo-attribution><a href="{esc(commons(row), quote=True)}" rel="noopener">{esc(row["n"])} photo</a> '
            f'by {author}, <a href="{esc(row["lu"], quote=True)}" rel="noopener license">{esc(row["l"])}</a></span>')


def home_block():
    """Front-door invitation; two fixed, credited photographs so the page works without JavaScript."""
    by_name = {r['n']: r for r in cars()}
    pair = [by_name[n] for n in ('Ferrari F40', 'Lamborghini Countach') if n in by_name]
    photos = ''.join(f'<img src="{esc(r["t"].replace("/960px-", "/330px-"), quote=True)}" alt="{esc(r["n"])} · reference photograph" '
                     f'width="330" height="206" loading="lazy" decoding="async" referrerpolicy="no-referrer">' for r in pair)
    credits = ' · '.join(credit(r) for r in pair)
    return ('<section class="jury-home"><div><p class="eyebrow">New · the world’s car jury</p><h2>Two cars. One verdict. Yours.</h2>'
            f'<p>Pick the car you would rather have, again and again. Your picks fill a ten-bay dream garage you can share, '
            f'and every verdict counts toward a world ranking of {len(cars())} cars.</p>'
            '<a class="button" href="/jury/">Start judging →</a></div>'
            f'<div><div class="jury-home-photos">{photos}</div><small>Photos: {credits}</small></div></section>')


FAQ = [
    ('How does the car jury work?',
     'You are shown two cars and pick the one you would rather have. Each winner is parked in your garage until its ten bays are full. '
     'After that, parking a new car means releasing one. On a keyboard, the left and right arrow keys pick a car. Every pick is also counted as one anonymous verdict toward the world ranking.'),
    ('Which cars are in the jury?',
     'A reviewed list of {n} cars from {b} marques, from the Ford Model T to current electric cars. A car enters only when its photograph '
     'has a recorded author and a licence that allows reuse. The full MotorJury catalogue is larger; the jury list grows as photographs are checked.'),
    ('How is the world ranking calculated?',
     'Each car has a count of showings and a count of wins. A car is ranked after five showings. The order uses the lower bound of a 95% '
     'confidence interval on its win rate, so a car picked twice out of two cannot outrank one picked eight hundred times out of a thousand. '
     'The ranking measures which car visitors would rather have. It is not a measure of quality, reliability or value.'),
    ('What is “Today’s ten”?',
     'Ten pairings that are the same for every visitor on a given day. When you finish, you see how often you sided with the majority, '
     'and you can share the result. A new ten arrive at midnight, Coordinated Universal Time.'),
    ('What do you store about me?',
     'Your garage is saved in this browser only. The server receives the two car numbers of each verdict and counts them. It records the '
     'country your request came from as a total per car, and uses a scrambled form of your network address only to limit abuse. '
     'No account is needed and no verdict is stored with your identity.'),
]


def main(write):
    rows = cars()
    script = assets()
    brands = len({r['b'] for r in rows})
    faq = ''.join(f'<h3>{esc(q)}</h3><p>{esc(a.format(n=len(rows), b=brands))}</p>' for q, a in FAQ)
    body = (
        '<section class="collection-hero compact jury-hero"><p class="eyebrow">The world’s car jury</p><h1>Two cars. One verdict.</h1>'
        f'<p class="lede">Pick the car you would rather have. Your picks fill a ten-bay dream garage and count toward the world ranking of {len(rows)} cars.</p></section>'
        '<section class="jury-shared card" data-jury-shared hidden><p class="eyebrow">A garage shared with you</p><h2>Ten bays, someone else’s taste.</h2>'
        '<p class="note" data-jury-shared-taste></p><ol class="jury-bays" data-jury-shared-grid></ol><a class="button" href="/jury/">Build my own garage →</a></section>'
        '<section class="jury-arena" data-jury aria-label="Pick one of two cars">'
        '<div class="jury-mode" role="group" aria-label="Game mode"><button type="button" data-jury-mode="free" aria-pressed="true">Free play</button>'
        '<button type="button" data-jury-mode="daily" aria-pressed="false">Today’s ten</button></div>'
        '<p class="jury-progress" role="status" data-jury-progress>Loading the jury…</p>'
        '<div class="jury-pair" data-jury-pair></div><p class="jury-credits" data-jury-credits></p>'
        '<div class="actions"><button type="button" class="secondary" data-jury-skip>Skip this pair</button></div>'
        '<div class="jury-result" data-jury-result hidden></div>'
        '<noscript><p>The jury needs JavaScript. The <a href="/library/">car collection</a> and the <a href="/all-cars/">complete A–Z list</a> work without it.</p></noscript></section>'
        '<section class="jury-garage" data-jury-garage aria-label="Your garage"><h2>Your ten-bay garage <span data-jury-count></span></h2>'
        '<p class="note" data-jury-taste></p><div class="jury-swap" data-jury-swap hidden></div><ol class="jury-bays" data-jury-bays></ol>'
        '<div class="actions"><button type="button" data-jury-share>Share my garage</button><button type="button" class="secondary" data-jury-copy>Copy garage link</button>'
        '<button type="button" class="secondary" data-jury-empty>Empty garage</button></div><p role="status" data-jury-status></p>'
        '<details><summary>Photo credits for your garage</summary><ul data-jury-garage-credits></ul></details>'
        '<p class="note">Saved in this browser only. No account needed. Clearing browser data empties the garage.</p></section>'
        '<section class="card"><h2>The world’s verdict so far</h2><p data-jury-top-status>Counting…</p><ol data-jury-top-list></ol>'
        '<a href="/jury/ranking/">See the full world ranking →</a></section>'
        f'<section class="card"><h2>Questions about the jury</h2>{faq}'
        '<p class="note">Reference photographs may show a different generation or trim from the one you have in mind. '
        'Every photograph is credited beside the car; <a href="/catalogue-notes/">catalogue and photo notes</a>.</p></section>')
    write('/jury/', 'Car Jury: pick one of two cars and build your dream garage', body, script,
          description=f'Pick the car you would rather have, two at a time. Fill a ten-bay dream garage, share it, play today’s ten and see the world ranking of {len(rows)} cars.')
    ranking = (
        '<section class="collection-hero compact"><p class="eyebrow">The world’s car jury</p><h1>The cars the world would rather have.</h1>'
        '<p class="lede">A live ranking from anonymous pick-one-of-two verdicts. It measures desire, not quality or reliability.</p></section>'
        '<section class="card" data-jury-ranking><label for="jury-country">Show verdicts from</label> <select id="jury-country" data-jury-country></select>'
        '<p role="status" data-jury-ranking-status>Counting…</p><ol class="jury-ranking-list" data-jury-ranking-list></ol>'
        '<noscript><p>The live ranking needs JavaScript.</p></noscript><a class="button" href="/jury/">Add my verdicts →</a></section>')
    write('/jury/ranking/', 'World car ranking from the MotorJury car jury', ranking, script,
          description='A live ranking of the cars visitors would rather have, from anonymous pick-one-of-two verdicts. Filter by country.')
    # The ranking is rendered in the browser from live counts, so it stays out of search
    # until it can be served as text. shortcut: client-rendered; upgrade to Worker-rendered
    # HTML once the ranking has enough verdicts to be worth citing.
    f = SITE / 'jury/ranking/index.html'
    f.write_text(f.read_text().replace('</head>', '<meta name="robots" content="noindex,follow"></head>', 1))
    print(f'JURY: {len(rows)} licensed cars from {brands} marques; game, garage, daily round and ranking built')
