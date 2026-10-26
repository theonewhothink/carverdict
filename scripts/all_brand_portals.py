"""The Porsche portal design, adapted to every exact catalogue marque.

Original catalogue exploration is distinguished from checked historical writing.
No invented history, substituted models, video IDs or image permissions.
"""
import hashlib
import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from prepare_brand_media import selected_rows

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
esc = html.escape


def media_records():
    result = json.loads((ROOT / 'data/photo_credits.json').read_text())
    extra = ROOT / 'data/brand_media_credits.json'
    if extra.exists():
        result.update(json.loads(extra.read_text()))
    return result


def photographs(entries, credits):
    from build_library import commons_page, commons_thumb
    result = []
    for row in selected_rows(entries, credits):
        filename = row['p'].replace('_', ' ')
        record = dict(credits.get(filename, {}))
        licence_url = record.get('licence_url', '')
        if licence_url.startswith(('http://creativecommons.org/', 'http://www.gnu.org/', 'http://commons.wikimedia.org/')):
            record['licence_url'] = 'https://' + licence_url[len('http://'):]
        if not all(record.get(key) for key in ('author', 'licence', 'licence_url', 'checked_at')):
            continue
        if not record['licence_url'].startswith('https://'):
            continue
        # Use the exact API-provided image URL, including resolved Commons redirects.
        src = record.get('thumb', '').split('?')[0] or commons_thumb(row['p'])
        if not src.startswith('https://'):
            continue
        year = str(row.get('y') or '')
        group = str(int(year) // 10 * 10) + 's' if re.fullmatch(r'(18|19|20)\d{2}', year) else 'Undated records'
        result.append(dict(record, id=row['q'], name=row['n'], model=row['n'], file=row['p'],
                           url=row['u'], page=record.get('page') or commons_page(row['p']),
                           src=src, small=src, large=record.get('original_url') or src,
                           group=group, caption='Catalogue photograph of ' + row['n'] +
                           '. The exact vehicle year and trim are not independently verified.'))
    return result


def heading(number, label, title, intro=''):
    return f'<div class="bp-section-head"><p class="bp-kicker"><span>{number}</span> {esc(label)}</p><h2>{esc(title)}</h2>' + (f'<p class="bp-intro">{esc(intro)}</p>' if intro else '') + '</div>'


def write_assets():
    output = {}
    for name in ('brand-portal.css', 'brand-portal.mjs'):
        content = (ROOT / 'assets' / name).read_text()
        stem, suffix = name.rsplit('.', 1)
        filename = stem + '.' + hashlib.sha256(content.encode()).hexdigest()[:10] + '.' + suffix
        (SITE / 'assets' / filename).write_text(content)
        output[suffix] = '/assets/' + filename
    return output


def make_story(brand, entries, photos, editorial):
    if editorial:
        return editorial['intro'], editorial['sections']
    names = [row['n'] for row in entries]
    illustrated = [photo['name'] for photo in photos]
    years = sorted({str(row['y']) for row in entries if re.fullmatch(r'(18|19|20)\d{2}', str(row.get('y') or ''))})
    if len(entries) == 1:
        intro = f"Start with {names[0]}. A single surviving catalogue entry can be a better invitation than a wall of famous badges. Look at the photograph, follow its source and decide what you want to know next." if photos else f"Start with {names[0]}. This small archive keeps a place for a name that could easily disappear between the famous badges. Open the surviving catalogue record and follow the evidence behind it."
        sections = [('One name. A closer look.', f"Our {brand} file currently contains one distinct identity: {names[0]}. That is the extent of this catalogue snapshot, rather than a claim that the maker produced only one car. The entry keeps its original destination so that saved links still lead to the same vehicle identity.")]
    else:
        lead = ' and '.join(illustrated[:2] or names[:2])
        intro = f"Start with {lead}. Then take a detour. This {brand} collection brings {len(entries):,} named entries into one place, so a familiar favourite can lead you to something you have never stopped to examine."
        middle = names[len(names) // 2]
        sections = [('Take the scenic route through the names.', f"There is more than one way into {brand}. You might begin with {names[0]}, pause at {middle}, or jump straight to {names[-1]}. These are different records in the current directory, not a popularity ranking. Follow the actual car names rather than assuming every variant represents a separate model generation."),
                    ('Read the shape before the badge.', f"A photograph is a good reason to become curious about {illustrated[0] if illustrated else names[0]}. Compare the cabin, wheel placement and body proportions with another entry. Treat what you see as a question to investigate: a reference image cannot establish an engine specification, a precise model year or a car's condition.")]
    if years:
        sections.append(('A timeline with its limits left in.', f"Dated records in this {brand} snapshot extend from {years[0]} to {years[-1]}. The timeline below follows those recorded catalogue years. It does not establish the company's founding date, uninterrupted production, or every market's model years; undated identities remain in the complete directory."))
    return intro, sections


def build_one(write, brand, entries, credits, editorial, assets):
    from build_library import slug
    from brand_portals import hero_slideshow, figure, film_card
    entries = sorted(entries, key=lambda row: row['n'].casefold())
    path = '/library/' + slug(brand) + '/'
    file = SITE / path.strip('/') / 'index.html'
    previous = file.read_text() if file.exists() else ''
    held = bool(re.search(r'<meta\s+name=["\']robots["\'][^>]*noindex', previous, re.I)) or not previous
    photos = photographs(entries, credits)
    preferred = (editorial or {}).get('featured', [])
    photos.sort(key=lambda p: (next((i for i, n in enumerate(preferred) if n.casefold() == p['name'].casefold()), len(preferred)), p['name'].casefold()))
    intro, sections = make_story(brand, entries, photos, editorial)
    films = (editorial or {}).get('films', [])
    sources = (editorial or {}).get('sources', [])
    years = sorted({str(r['y']) for r in entries if re.fullmatch(r'(18|19|20)\d{2}', str(r.get('y') or ''))})
    title = brand + ': cars, photographs & stories'
    description = f'Explore {brand}: {len(entries):,} catalogue entries' + (f', {len(photos)} credited photographs' if photos else '') + ', original reading notes and a complete model directory.'
    tag = (editorial or {}).get('tagline', 'Follow a name. Find a car. Keep exploring.')
    body = f'<div class="brand-portal" data-brand-portal data-brand-name="{esc(brand,quote=True)}" data-full-directory><nav class="bp-breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><span>/</span><a href="/library/">Car collection</a><span>/</span><span aria-current="page">{esc(brand)}</span></nav><section class="bp-masthead"><div class="bp-edition"><p class="bp-kicker">The MotorJury marque files</p><span>{len(entries):,} catalogue entries · an independent collection</span></div><div class="bp-title-row"><h1 class="bp-brand-title">{esc(brand)}<span>.</span></h1><div><p>{esc(tag)}</p><a href="#story">Explore the marque ↓</a></div></div>'
    if len(photos) > 1:
        body += hero_slideshow(photos[:6], brand)
    elif photos:
        body += figure(photos[0], 'bp-single-hero', eager=True)
    else:
        body += f'<div class="bp-archive-cover"><span>The marque file</span><p>{esc(entries[0]["n"])}</p><a href="#models">Open the {len(entries):,}-entry directory →</a></div>'
    provenance = 'Original, AI-assisted archive research and catalogue exploration' if editorial else 'Original, AI-assisted catalogue exploration'
    body += f'<div class="bp-opening"><p>{esc(intro)}</p><div class="bp-issue-meta"><b>An independent MotorJury feature</b><span>{provenance}</span>'
    if editorial:
        body += f'<span>Archive sources checked <time datetime="{editorial["checked_at"]}">{editorial["checked_at"]}</time></span>'
    body += '</div></div></section><nav class="bp-jump" aria-label="Explore the brand portal"><a href="#story">The story</a>'
    if years:
        body += '<a href="#timeline">Through the years</a>'
    if photos:
        body += f'<a href="#gallery">{len(photos)} photographs</a>'
    if films:
        body += '<a href="#films">Watch &amp; listen</a>'
    body += f'<a href="#models">All {len(entries):,} entries</a><a href="#sources">Sources</a></nav><section id="story" class="bp-section">' + heading('01', 'The story', (editorial or {}).get('headline', 'A badge is only the beginning.'))
    body += '<div class="bp-story-grid"><article class="bp-story">'
    for index, (name, text) in enumerate(sections):
        body += f'<h3>{esc(name)}</h3><p'+(' class="bp-dropcap"' if index == 0 else '')+'>'+esc(text)+'</p>'
    if sources:
        body += '<p class="bp-footnote">History references: ' + ' · '.join(f'<a href="{esc(url,quote=True)}">{esc(label)}</a>' for label, url, _ in sources) + '</p>'
    body += '</article><aside class="bp-story-aside">' + ''.join(figure(photo) for photo in photos[1:3]) + '</aside></div></section>'
    # Distribute real films throughout the feature, in the same way as Porsche.
    if films:
        body += '<section id="films" class="bp-feature-film bp-section">' + film_card(films[0]) + '</section>'
    if years:
        chosen = [years[round(i * (len(years) - 1) / max(min(8, len(years)) - 1, 1))] for i in range(min(8, len(years)))]
        body += '<section id="timeline" class="bp-section">' + heading('02', 'Through the years', 'Different years. Different starting points.', 'Recorded catalogue years, not a complete corporate chronology or a verified production range.') + '<div class="bp-timeline">'
        for year in chosen:
            matches = [r for r in entries if str(r.get('y')) == year]
            row = matches[0]
            body += f'<article><div class="bp-milestone-heading"><span>{year}</span><h3><a href="{esc(row["u"],quote=True)}">{esc(row["n"])}</a></h3></div><p>{len(matches)} catalogue '+('entry carries' if len(matches) == 1 else 'entries carry')+f' this recorded year. <a href="https://www.wikidata.org/wiki/{row["q"]}">Inspect the source record ↗</a></p></article>'
        body += '</div></section>'
    if len(films) > 1:
        body += '<section class="bp-feature-film bp-section">' + film_card(films[1]) + '</section>'
    if photos:
        body += '<section id="gallery" class="bp-section">' + heading('03', 'The visual archive', 'Find the one you keep looking at.', 'Open a car for its record, or enlarge a photograph. Individual attribution stays with every image.')
        body += f'<div class="bp-gallery-filters" role="group" aria-label="Filter {esc(brand,quote=True)} photographs" hidden><button type="button" data-photo-filter="All" aria-pressed="true">All {len(photos)}</button>'
        for group in dict.fromkeys(p['group'] for p in photos):
            body += f'<button type="button" data-photo-filter="{esc(group,quote=True)}" aria-pressed="false">{esc(group)}</button>'
        body += f'</div><p class="bp-gallery-status" role="status" data-gallery-status>{len(photos)} photographs · individual credits below each image</p><div class="bp-gallery">'
        for i, photo in enumerate(photos):
            body += f'<div class="bp-gallery-item" data-photo-group="{esc(photo["group"],quote=True)}">{figure(photo)}<button type="button" class="bp-enlarge" data-photo-open="{i}" aria-label="Enlarge {esc(photo["name"],quote=True)}" hidden>Enlarge ↗</button></div>'
        body += '</div></section>'
    if len(films) > 2:
        body += '<section id="screening" class="bp-section">' + heading('04', 'Watch & listen', 'Another way into the story.', 'Films from the named publisher. Select a real thumbnail to watch; the player loads only when requested.') + '<div class="bp-films">'
        body += ''.join(film_card(film) for film in films[2:])
        body += '</div><p class="bp-footnote">Manufacturer films are primary accounts, not independent testing. YouTube availability, advertising and regional restrictions can vary; direct video links remain available.</p></section>'
    body += '<section id="models" class="bp-section">' + heading('05', 'Keep exploring', f'Your {brand} rabbit hole.', f'All {len(entries):,} catalogue identities, including entries without a reviewed photograph. This is not a list of models currently on sale.')
    body += f'<form action="/library/" class="bp-model-search" data-portal-model-form role="search" aria-label="{esc(brand,quote=True)} model directory"><label for="brand-model-search">Find a {esc(brand)} in the directory</label><div><input type="search" id="brand-model-search" name="q" placeholder="Search the {esc(brand,quote=True)} collection" autocomplete="off"><input type="hidden" name="brand" value="{esc(brand,quote=True)}"><button>Find a model →</button></div></form><p class="bp-gallery-status" role="status" data-model-status>{len(entries):,} catalogue entries</p><ul class="bp-model-list" data-portal-roster>'
    ids = set()
    for row in entries:
        anchor = row['u'].partition('#')[2] or 'm-' + slug(row['n'])
        if anchor in ids:
            anchor += '-' + hashlib.sha256(row['n'].encode()).hexdigest()[:8]
        ids.add(anchor)
        body += f'<li id="{esc(anchor,quote=True)}" data-model-name="{esc(row["n"],quote=True)}"><a href="{esc(row["u"],quote=True)}">{esc(row["n"])}</a></li>'
    body += '</ul><button class="bp-more-models" type="button" data-more-models hidden>Show the complete directory</button><p class="bp-no-models" data-no-models hidden>No matching entry. Try a shorter name.</p></section>'
    body += '<section id="sources" class="bp-section bp-sources">' + heading('06', 'Behind the collection', 'Follow the evidence.') + '<p>MotorJury’s original reading notes are separate from the underlying catalogue facts. Entries are derived from Wikidata; photographs are credited to their named creators under the linked licences. The collection can contain prototypes, regional names, variants and incomplete records. It does not establish global historical completeness.</p><div class="bp-research-notes"><h3>Sources &amp; archive notes</h3><ol>'
    for label, url, scope in sources:
        body += f'<li><a href="{esc(url,quote=True)}">{esc(label)}</a><span>{esc(scope)}</span></li>'
    for row in entries[:3]:
        body += f'<li><a href="https://www.wikidata.org/wiki/{row["q"]}">{esc(row["n"])} · source record</a><span>Structured catalogue data; statements and source history can change.</span></li>'
    body += '</ol></div><p class="bp-footnote">Catalogue dates are not independently verified production dates. Photo permission checks carry their own dates in the source snapshot. No road test, interview, manufacturer affiliation or specialist endorsement is claimed. <a href="/catalogue-notes/">Coverage and photography</a> · <a href="/editorial-policy/">Editorial policy</a> · <a href="/contact/">Suggest a correction</a></p></section><div class="bp-end"><p>One badge. Another discovery.</p><a href="/library/">Explore another marque →</a><a href="#models">Back to the complete directory ↑</a></div></div>'
    origin = os.environ.get('SITE_ORIGIN', 'https://motorjury.com').rstrip('/')
    schema = [{'@context': 'https://schema.org', '@type': 'CollectionPage', '@id': origin + path + '#portal',
               'name': title, 'description': description, 'url': origin + path,
               'about': {'@type': 'Thing' if brand == 'Independent & coachbuilders' else 'Brand', 'name': brand}},
              {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
                  {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': origin + '/'},
                  {'@type': 'ListItem', 'position': 2, 'name': 'Car collection', 'item': origin + '/library/'},
                  {'@type': 'ListItem', 'position': 3, 'name': brand, 'item': origin + path}]}]
    public = [{key: p[key] for key in ('name','caption','src','large','page','author','licence','licence_url','url')} for p in photos]
    script = f'<script type="module" src="{assets["mjs"]}"></script><script type="application/json" id="bp-photo-data">' + json.dumps(public, ensure_ascii=False).replace('<', '\\u003c') + '</script>'
    write(path, title, body, script, description=description, jsonld=schema)
    text = file.read_text().replace('</head>', f'<link rel="stylesheet" href="{assets["css"]}">' + ('<meta name="robots" content="noindex,follow">' if held else '') + '</head>', 1)
    if photos:
        text = re.sub(r'(<meta property="og:image" content=")[^"]+', lambda m: m.group(1) + esc(photos[0]['src'], quote=True), text)
        text = re.sub(r'(<meta property="og:image:alt" content=")[^"]+', lambda m: m.group(1) + esc(photos[0]['name'] + ' — ' + brand + ' portal', quote=True), text)
        # The generic default-card dimensions need not describe a Commons photograph.
        text = re.sub(r'<meta property="og:image:(?:width|height)"[^>]*>', '', text)
    file.write_text(text)
    return {'brand': brand, 'path': path, 'entries': len(entries), 'photographs': len(photos),
            'films': len(films), 'history_reviewed': bool(editorial), 'previous_noindex_preserved': held}


def build_all(write, all_rows):
    groups = defaultdict(list)
    for row in all_rows:
        groups[row['b']].append(row)
    path = ROOT / 'data/brand_portal_stories.json'
    stories = json.loads(path.read_text()) if path.exists() else {}
    credits, assets = media_records(), write_assets()
    results = []
    for brand, entries in sorted(groups.items()):
        if brand != 'Porsche':
            results.append(build_one(write, brand, entries, credits, stories.get(brand), assets))
    results.append({'brand': 'Porsche', 'path': '/library/porsche/', 'entries': len(groups['Porsche']),
                    'photographs': 24, 'films': 6, 'history_reviewed': True, 'previous_noindex_preserved': False})
    (SITE / 'assets/brand-portals.json').write_text(json.dumps(results, ensure_ascii=False, separators=(',', ':')))
    print(f'BRAND PORTALS: {len(results)} marque files; {sum(r["entries"] for r in results)} exact identities retained; {sum(r["photographs"] for r in results)} credited gallery photographs')
