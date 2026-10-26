"""One accessible, progressively enhanced search box across all public shells."""
import hashlib
import html
import json
import re
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def prepare():
    assets = ROOT / 'site/assets'
    assets.mkdir(parents=True, exist_ok=True)
    from build_library import slug
    rows = json.loads((assets / 'catalogue-data.json').read_text())
    brands = sorted({row['b'] for row in rows})
    index = {'brands': [{'n': brand, 'u': '/library/' + slug(brand) + '/'} for brand in brands],
             'cars': [{key: row[key] for key in ('n', 'b', 'u')} for row in rows]}
    text = json.dumps(index, ensure_ascii=False, separators=(',', ':'))
    revision = hashlib.sha256(text.encode()).hexdigest()[:10]
    (assets / 'header-search-index.json').write_text(text)
    names = []
    for name in ('header-search.css', 'header-search.mjs'):
        text = (ROOT / 'assets' / name).read_text().replace('__SEARCH_VERSION__', revision)
        stem, suffix = name.rsplit('.', 1)
        hashed = stem + '.' + hashlib.sha256(text.encode()).hexdigest()[:10] + '.' + suffix
        (assets / hashed).write_text(text)
        names.append(hashed)
    return names


def enhance(text):
    if '<header' not in text or 'data-header-search' in text:
        return text
    css, script = prepare()
    form = '''<form class="mj-header-search" action="/library/" method="get" role="search" aria-label="Site search" data-header-search>
<label class="mj-sr-only" for="header-car-search">Search cars and brands</label>
<div class="mj-search-input"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></svg><input id="header-car-search" name="q" type="search" placeholder="Search cars &amp; brands" autocomplete="off" maxlength="120"><button type="submit" aria-label="Search cars and brands">Search <span aria-hidden="true">→</span></button></div>
<div class="mj-search-results" id="header-search-results" role="listbox" aria-label="Search suggestions" hidden></div><span class="mj-sr-only" role="status" data-header-search-status></span></form>'''
    # All modern shells share this logo. Legacy shells get a separate wrapper.
    logo = re.search(r'<a\b[^>]*class="logo"[^>]*>.*?</a>', text, re.S)
    if logo:
        text = text[:logo.end()] + form + text[logo.end():]
    else:
        text = text.replace('</header>', '<div class="wrap">' + form + '</div></header>', 1)
    text = re.sub(r'<header(\s[^>]*)?>', lambda m: m.group(0).replace('>', ' data-site-search-header>'), text, count=1)
    tags = f'<link rel="stylesheet" href="/assets/{html.escape(css)}"><script type="module" src="/assets/{html.escape(script)}"></script>'
    return text.replace('</head>', tags + '</head>', 1)
