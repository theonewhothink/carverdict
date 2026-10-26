"""The Porsche editorial feature and shared portal components.

No external harvest at build time; other marques use their own catalogue and research.
The complete identity roster and its existing fragment targets remain intact.
"""
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
PATH = '/library/porsche/'
esc = html.escape


def load():
    data = json.loads((ROOT / 'data/porsche_portal.json').read_text())
    credits = json.loads((ROOT / 'data/photo_credits.json').read_text())
    for photo in data['photographs']:
        if photo.get('credit_key'):
            photo.update(credits[photo['credit_key']])
        photo.setdefault('checked_at', data['reviewed_at'])
        filename = photo['file'].replace(' ', '_')
        encoded = quote(filename, safe='')
        digest = hashlib.md5(filename.encode()).hexdigest()
        base = f'https://thumb.wikimedia.org/wikipedia/commons/thumb/{digest[0]}/{digest[:2]}/{encoded}/'
        photo['page'] = 'https://commons.wikimedia.org/wiki/File:' + encoded
        # Commons' supported thumbnail steps; small originals must not be upscaled.
        photo['src'] = photo.get('thumb', '').split('?')[0] or base + '960px-' + encoded
        if photo.get('original_width', 9999) < 960:
            photo['src'] = f'https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{encoded}'
        photo['small'] = base + '330px-' + encoded
        photo['large'] = photo['src'] if photo.get('original_width', 9999) < 1280 else base + '1280px-' + encoded
    return data


def credit(photo):
    more = f' · <a href="{esc(photo["attribution_url"], quote=True)}">{esc(photo["attribution_label"])}</a>' if photo.get('attribution_url') else ''
    return f'<span data-photo-attribution><a href="{esc(photo["page"],quote=True)}">{esc(photo["author"])}</a> · <a href="{esc(photo["licence_url"],quote=True)}">{esc(photo["licence"])}</a>{more}</span>'


def image(photo, eager=False):
    sizes = '(max-width: 620px) 100vw, (max-width: 960px) 50vw, 420px'
    srcset = f'{photo["small"]} 330w, {photo["src"]} {min(960,photo.get("original_width",960))}w'
    return f'<img src="{esc(photo["src"],quote=True)}" srcset="{esc(srcset,quote=True)}" sizes="{sizes if not eager else "(max-width:1280px) 100vw, 1240px"}" width="960" height="540" alt="{esc(photo["name"],quote=True)}" {"fetchpriority=high" if eager else "loading=lazy"} decoding="async" referrerpolicy="no-referrer">'


def figure(photo, cls='', eager=False):
    return f'<figure class="bp-photo {cls}"><a class="bp-photo-link" href="{esc(photo["url"],quote=True)}">{image(photo,eager)}</a><figcaption><b>{esc(photo["name"])}</b><span>{esc(photo["caption"])}</span><small>{credit(photo)} · Display cropped.</small></figcaption></figure>'


def hero_slideshow(photos, brand='Porsche'):
    slides, credits = [], []
    for i, photo in enumerate(photos):
        hidden = ' hidden' if i else ''
        slides.append(f'<a class="bp-hero-slide" data-hero-slide data-hero-name="{esc(photo["name"],quote=True)}" href="{esc(photo["url"],quote=True)}" aria-label="Explore {esc(photo["name"],quote=True)}"{hidden}>{image(photo,i==0)}</a>')
        credits.append(f'<span data-hero-credit{hidden}>{credit(photo)} · Display cropped.</span>')
    return (f'<figure class="bp-hero" data-hero-carousel data-hero-interval="2000" aria-roledescription="carousel" aria-label="{esc(brand,quote=True)} photo slideshow"><div class="bp-hero-frames">'
            + ''.join(slides) + f'<div class="bp-hero-tag"><span>One marque. Many obsessions.</span><b data-hero-label>{esc(photos[0]["name"])}</b></div>'
            + f'<div class="bp-hero-controls" hidden><span data-hero-count aria-live="off">1 / {len(photos)}</span><button type="button" data-hero-previous aria-label="Previous hero photograph">←</button><button type="button" data-hero-toggle aria-label="Pause hero slideshow">Pause</button><button type="button" data-hero-next aria-label="Next hero photograph">→</button></div>'
            + '</div><figcaption>' + ''.join(credits) + '</figcaption></figure>')


def film_card(film):
    title, video_id = esc(film['name']), film['id']
    url = 'https://www.youtube.com/watch?v=' + video_id
    return f'''<article class="bp-film" aria-labelledby="film-{video_id}"><div class="bp-film-stage" data-video-slot><a class="bp-film-thumbnail" href="{url}" target="_blank" rel="noopener noreferrer" aria-label="Watch {esc(film['name'],quote=True)} on YouTube"><img src="https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" width="480" height="360" alt="Video thumbnail: {esc(film['name'],quote=True)}" loading="lazy" decoding="async" referrerpolicy="no-referrer"></a><button class="bp-film-play" type="button" data-video="{video_id}" aria-label="Play {esc(film['name'],quote=True)}" hidden><svg viewBox="0 0 32 32" aria-hidden="true"><path d="M11 6 27 16 11 26Z" fill="currentColor"/></svg></button><span class="bp-film-duration">{esc(film['duration'])}</span></div><div class="bp-film-copy"><p class="bp-kicker">{esc(film.get('kicker','Porsche films'))}</p><h3 id="film-{video_id}">{title}</h3><p>{esc(film['description'])}</p><a href="{url}" target="_blank" rel="noopener noreferrer">Watch on YouTube ↗</a></div></article>'''


def build(write, all_rows):
    from build_library import slug
    data = load()
    entries = sorted((row for row in all_rows if row['b'] == 'Porsche'), key=lambda row: row['n'].casefold())
    by_name = {row['n']: row for row in entries}
    photos = data['photographs']
    for photo in photos:
        photo['url'] = by_name[photo['model']]['u']
    by_id = {photo['id']: photo for photo in photos}
    sources = {row[0]: row for row in data['sources']}
    featured_films = {film['placement']: film for film in data['films'] if film.get('placement') != 'screening'}

    def featured_film(placement):
        film = featured_films[placement]
        return f'<section class="bp-feature-film bp-section" aria-label="{esc(film["name"],quote=True)}">{film_card(film)}</section>'

    def cite(key, label='Archive note'):
        return f'<a class="bp-cite" href="{esc(sources[key][2],quote=True)}">{esc(label)} ↗</a>'

    def heading(number, kicker, title, introduction=''):
        return f'<div class="bp-section-head"><p class="bp-kicker"><span>{number}</span> {kicker}</p><h2>{title}</h2>'+ (f'<p class="bp-intro">{introduction}</p>' if introduction else '')+'</div>'

    hero = by_id['992']
    body = f'''<div class="brand-portal" data-brand-portal>
<nav class="bp-breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">/</span><a href="/library/">Car collection</a><span aria-hidden="true">/</span><span aria-current="page">Porsche</span></nav>
<section class="bp-masthead" aria-labelledby="porsche-title"><div class="bp-edition"><p class="bp-kicker">The MotorJury marque files <span>№ 01</span></p><span>Stuttgart, Germany · Sports cars since 1948</span></div>
<div class="bp-title-row"><h1 id="porsche-title">Porsche<span>.</span></h1><div><p>The art of changing<br>without starting over.</p><a href="#story">Get to know the obsession <span aria-hidden="true">↓</span></a></div></div>
{hero_slideshow([by_id[key] for key in data['hero_slides']])}
<div class="bp-opening"><p>A 911 can look familiar enough to draw from memory. Porsche's history is much less predictable: desert racers, front-engined grand tourers, an SUV and a battery-powered saloon. Follow the arguments that made the cars.</p><div class="bp-issue-meta"><b>An independent MotorJury feature</b><span>Original, AI-assisted archive research</span><span>Sources checked <time datetime="2026-10-26">26 October 2026</time></span></div></div>
</section>
<nav class="bp-jump" aria-label="Explore the Porsche portal"><a href="#story">The story</a><a href="#timeline">Turning points</a><a href="#911">911 generations</a><a href="#gallery">24 photographs</a><a href="#films">Watch &amp; listen</a><a href="#models">All {len(entries)} entries</a></nav>
<section id="story" class="bp-section">
{heading('01','The story','Beautifully stubborn.<br>Occasionally, brilliantly unfaithful.')}
<div class="bp-story-grid"><article class="bp-story"><p class="bp-dropcap">The easy version of Porsche history goes like this: a family builds a small sports car, puts the engine at the back and spends the next few decades making it faster. It is an appealing story. It also leaves out most of the interesting decisions.</p>
<p>The first Porsche-badged car, the 356 No. 1 Roadster, actually placed its engine ahead of the rear axle. The production 356 moved it behind. Even the founding idea was open to revision. That little detail is a useful way into the whole company: continuity matters here, but it has never meant mechanical immobility. {cite('beginnings')}</p>
<h3>First, a better small car.</h3><p>On 8 June 1948, the No. 1 Roadster received its operating permit in Austria. Ferry Porsche's team was turning an engineering business into a sports-car maker. The early formula made something special out of modest ingredients: a light body, compact dimensions and hardware with Volkswagen ancestry. The attraction was the way the pieces worked together. More power was only one route to a better car. {cite('beginnings','Where the first car began')}</p>
<h3>Then, a shape that refused to leave.</h3><p>The 356's successor appeared as the 901 in 1963. Peugeot objected to the designation; in 1964, Porsche changed it to 911. An administrative nuisance became one of motoring's most recognisable names. Under the descending roof sat a rear-mounted flat-six. That layout became the enduring conversation between Porsche's engineers and its customers: how much can you change while keeping the car recognisably itself? {cite('901','The 901 becomes the 911')}</p>
<h3>The 911 was never the only answer.</h3><p>The 924 arrived in 1976 and the V8-powered 928 followed in 1977. Engines at the front; a very different outlook. The 944 joined in 1982. Look at these cars together and the supposed straight line of Porsche history becomes a fork in the road. The company was willing to explore another kind of sports car even while the 911 carried on. {cite('history','The front-engined chapter')}</p>
<h3>Changing the sound of the argument.</h3><p>The 993 closed the air-cooled 911 era in 1998. The 996, introduced in 1997, made water cooling part of the next chapter. It also shared components with the Boxster: the romance had to coexist with production costs, emissions and safety requirements. A recognisable silhouette did not exempt Porsche from the realities of manufacturing. Our reading is that the 996's significance lies as much in that industrial reset as in its controversial headlights. {cite('993','The last air-cooled generation')} {cite('996','Why the 996 changed')}</p>
<h3>The roadster that widened the invitation.</h3><p>The Boxster concept appeared at Detroit in 1993; production began in August 1996. With an engine between the seats and the rear axle, it revived an older Porsche idea in an approachable new shape. Think of the two sports-car families as two answers to a good afternoon: the 911 carries a long conversation forward; the Boxster starts with the roof down. That is an editorial distinction, rather than a claim from a road test. {cite('boxster')}</p>
</article><aside class="bp-story-aside">{figure(by_id['356'])}<div class="bp-margin-note"><span>Look closer</span><h3>The first Porsche wasn't a rear-engined 911 in miniature.</h3><p>No. 1 was mid-engined. Its production relatives moved the engine behind the rear axle. A badge can stay put while an idea moves.</p></div>{figure(by_id['928'])}</aside></div>
<div class="bp-double-story"><article><p class="bp-kicker">The business decision</p><h3>The family car that changed the family.</h3><p>The Cayenne went into production in 2002. An SUV made the badge relevant to people whose lives did not fit inside a two-door sports car. Porsche's own account describes it as a central part of the company's subsequent success. The lesson is more interesting than a purity argument: a specialist can broaden its business without requiring every product to solve the same problem. {cite('cayenne')}</p></article><article><p class="bp-kicker">The next question</p><h3>What survives when the engine disappears?</h3><p>The Taycan's 2019 debut removed the combustion engine altogether. Its 800-volt electrical system was a major part of Porsche's technical pitch. The identity question became impossible to dodge: does a Porsche have to sound a particular way, or can its proportions, controls and engineering intent carry the name? The hardware supplies facts. The answer belongs to the person looking at the car. {cite('taycan')}</p></article></div>
<section class="bp-history-note" aria-labelledby="porsche-history-note"><h3 id="porsche-history-note">The history also has a darker chapter.</h3><p>Ferdinand Porsche founded the engineering office in 1931. Its work under National Socialism included military projects, and the business exploited forced labour during the Second World War. Porsche's published account of historical research acknowledges this. Enjoying the later cars does not require turning their manufacturer's past into a spotless origin story. {cite('past','Read the historical research')}</p></section>
</section>
{featured_film('story')}
<section id="timeline" class="bp-section bp-timeline-section">{heading('02','The turning points','Eight moments.<br>A very different company.','The dates that changed the cars, and the company behind them.')}
<div class="bp-timeline">'''
    milestones = [
        ('1931', 'Before the badge', 'Ferdinand Porsche establishes an engineering office in Stuttgart. The business comes before the sports-car marque.', 'past'),
        ('1948', 'A first car, in Austria', 'The 356 No. 1 Roadster receives its permit on 8 June. Mid-engine first, rear-engine production cars next.', 'beginnings'),
        ('1963', 'Hello, 901', 'The successor to the 356 makes its debut. The 911 name follows in 1964 after Peugeot objects.', '901'),
        ('1970', 'Le Mans, outright', 'Hans Herrmann and Richard Attwood win in the 917 KH. Porsche steps beyond class honours to its first overall victory.', 'racing'),
        ('1986', 'The desert answers', 'The 959 rally cars finish first, second and sixth at Paris-Dakar. This is a very different test from a tidy race circuit.', 'dakar'),
        ('1996', 'A mid-engine invitation', 'The production Boxster arrives three years after its concept. A new roadster becomes a second sports-car path.', 'boxster'),
        ('2002', 'A bigger brief', 'The Cayenne brings Porsche into the SUV market. More seats, more uses and a much wider customer base.', 'cayenne'),
        ('2019', 'Electric, unmistakably ambitious', 'The Taycan premieres on 4 September. Its 800-volt architecture gives the new era a concrete engineering centrepiece.', 'taycan'),
    ]
    for year, title, text, key in milestones:
        body += f'<article><div class="bp-milestone-heading"><span>{year}</span><h3>{esc(title)}</h3></div><p>{esc(text)}</p>{cite(key,"Check this milestone")}</article>'
    body += '</div></section>'
    body += f'''<section id="911" class="bp-section">{heading("03","The enduring idea","Same family.<br>Eight distinct personalities.","Choose a generation. Years below refer to introductions, rather than every market's model-year range.")}<div class="bp-generation-tabs" role="tablist" aria-label="Porsche 911 generations" hidden>'''
    generations = [
        ('original', 'Original', '1963', 'The outline arrives.', 'Slim pillars, a descending roof and a rear flat-six. The 901 debut establishes the idea that becomes the 911.', '901'),
        ('gseries', 'G-series', '1973', 'A tougher-looking classic.', 'Prominent impact bumpers define the next long chapter. The Turbo joins the story during this generation.', 'generations'),
        ('964', '964', '1988', 'The familiar goes modern.', 'The Carrera 4 brings all-wheel drive to the 911 family. Integrated bumpers visually smooth the transition.', 'generations'),
        ('993', '993', '1993', 'The air-cooled farewell.', 'A new rear suspension helps move the chassis forward. This generation also closes the air-cooled chapter in 1998.', '993'),
        ('996', '996', '1997', 'A necessary reinvention.', 'Water cooling, a new body and component sharing with the Boxster. A substantial engineering and manufacturing reset.', '996'),
        ('997', '997', '2004', 'Round lights, modern bones.', 'The round-headlamp face returns. The later generation also introduces PDK to the 911 story.', 'generations'),
        ('991', '991', '2011', 'A longer stride.', 'A longer wheelbase and a new body make this a substantial redesign. The family resemblance remains immediate.', 'generations'),
        ('992', '992', '2018', 'The idea, sharpened again.', 'The eighth generation premieres in Los Angeles. A wider-looking stance carries the recognisable 911 profile into another era.', '992'),
    ]
    for i, (key, name, year, title, text, source) in enumerate(generations):
        body += f'<button type="button" id="bp-tab-{i}" role="tab" aria-controls="bp-gen-{i}" aria-selected="{str(i==0).lower()}" tabindex="{0 if i==0 else -1}" data-generation="{i}"><span>{name}</span><small>{year}</small></button>'
    body += '</div><div class="bp-generations">'
    for i, (key, name, year, title, text, source) in enumerate(generations):
        body += f'<section class="bp-generation" id="bp-gen-{i}" aria-label="{name} generation"><div>{figure(by_id[key])}</div><div class="bp-generation-copy"><p class="bp-kicker">{name} / Introduced {year}</p><h3>{title}</h3><p>{text}</p>{cite(source,"Explore the archive")}<a class="bp-text-link" href="{by_id[key]["url"]}">Open the catalogue entry →</a></div></section>'
    body += '</div></section>' + featured_film('generations')
    body += f'''<section class="bp-racing bp-section">{heading('04','Beyond the road','The racing story has dirt under its nails.')}<div class="bp-racing-columns"><p>A 356 SL won its class on Porsche's Le Mans debut in 1951. The 917 KH delivered an outright win in 1970. Those are different achievements, and the gap between them matters: a small sports-car maker had become an overall contender. {cite('racing')}</p><p>The desert adds a useful twist. The 959's 1986 Dakar result was a one-two, with the service car sixth. When Porsche later recommissioned one of those cars, its team preserved wear and traces of the original event. A race car's scars can tell you more than another spotless plinth. {cite('dakar')}</p></div><p class="bp-racing-line">Circuits. Rally stages. A desert.<br>The badge has never had just one playground.</p></section>
{featured_film('racing')}
<section id="gallery" class="bp-section">{heading('05','The visual archive','Find the one<br>you keep looking at.','24 selected photographs. Open a car for its catalogue entry, or use Enlarge to browse the gallery.')}
<div class="bp-gallery-filters" role="group" aria-label="Filter Porsche photographs" hidden><button type="button" data-photo-filter="All" aria-pressed="true">All 24</button>'''
    groups = list(dict.fromkeys(photo['group'] for photo in photos))
    for group in groups:
        body += f'<button type="button" data-photo-filter="{esc(group)}" aria-pressed="false">{esc(group)}</button>'
    body += '</div><p class="bp-gallery-status" role="status" data-gallery-status>24 photographs · individual credits below each image</p><div class="bp-gallery">'
    for i, photo in enumerate(photos):
        body += f'<div class="bp-gallery-item" data-photo-group="{esc(photo["group"],quote=True)}">'+figure(photo)+f'<button type="button" class="bp-enlarge" data-photo-open="{i}" aria-label="Enlarge {esc(photo["name"],quote=True)}" hidden>Enlarge <span aria-hidden="true">↗</span></button></div>'
    body += '</div><p class="bp-footnote">Photographs illustrate the named cars; they do not verify an individual vehicle’s condition or every trim detail. Cropped displays retain the licences linked with each photograph.</p></section>'
    body += f'''<section id="films" class="bp-section">{heading("06","The screening room","Let the people<br>who were there talk.","Porsche's archive, on film. Choose a thumbnail to watch.")}<div class="bp-films">'''
    for film in data['films']:
        if film.get('placement') == 'screening':
            body += film_card(film)
    body += '</div><p class="bp-footnote">Official manufacturer films are presented as primary accounts. Playback may include YouTube advertising and may be restricted by region or embedding settings. External links remain available.</p></section>'
    body += f'''<section class="bp-surprise"><div><p class="bp-kicker">The unexpected footnote</p><h2>Yes, they tried<br>a Cayenne convertible.</h2></div><div><p>After the first Cayenne arrived, Porsche explored a convertible version and built a full-size study. It stayed a one-off. The next time someone insists Porsche never experiments, imagine the meeting where that roof came off.</p>{cite('surprise','Meet the one that never reached the showroom')}</div></section>
<section id="models" class="bp-section">{heading('07','Keep exploring',f'Your Porsche rabbit hole.<br>All {len(entries)} catalogue entries.','Road cars, prototypes, racers and historical oddities. These catalogue identities are a directory, not a list of models currently on sale.')}
<form action="/library/" class="bp-model-search" data-portal-model-form role="search" aria-label="Porsche model directory"><label for="porsche-model-search">Find a Porsche in the directory</label><div><input type="search" id="porsche-model-search" name="q" placeholder="Try 959, Boxster, Taycan…" autocomplete="off"><input type="hidden" name="brand" value="Porsche"><button>Find a model →</button></div></form>
<p class="bp-gallery-status" role="status" data-model-status>{len(entries)} catalogue entries</p><ul class="bp-model-list" data-portal-roster>'''
    for row in entries:
        body += f'<li id="m-{slug(row["n"])}" data-model-name="{esc(row["n"],quote=True)}"><a href="{esc(row["u"],quote=True)}">{esc(row["n"])}</a></li>'
    body += '</ul><button class="bp-more-models" type="button" data-more-models hidden>Show the complete directory</button><p class="bp-no-models" data-no-models hidden>No matching entry. Try a shorter name.</p></section>'
    body += f'<section id="sources" class="bp-section bp-sources">{heading("08","Behind the story","Good stories should<br>leave a paper trail.")}<p>Written for MotorJury from the primary material below. Narrative judgements are our interpretation; historical dates and engineering claims link to their sources. This is AI-assisted desk research, without a claimed road test, interview or specialist endorsement. MotorJury is independent of Porsche AG.</p><div class="bp-research-notes"><h3>Research notes &amp; primary sources · {len(sources)}</h3><ol>'
    for key, title, url, scope in data['sources']:
        body += f'<li><a href="{esc(url,quote=True)}">{esc(title)}</a><span>{esc(scope)}</span></li>'
    body += f'</ol></div><p class="bp-footnote">Research checked <time datetime="{data["reviewed_at"]}">26 October 2026</time>. Introduction dates may differ from production or market-specific model years. The model directory preserves the current catalogue’s naming and coverage limits. <a href="/catalogue-notes/">Catalogue notes</a> · <a href="/editorial-policy/">Editorial policy</a> · <a href="/contact/">Suggest a correction</a></p></section><div class="bp-end"><p>Still thinking about one of them?</p><a href="#gallery">One more look at the photographs ↑</a><a href="/library/">Explore another marque →</a></div></div>'

    for name in ('brand-portal.css', 'brand-portal.mjs'):
        text = (ROOT / 'assets' / name).read_text()
        stem, suffix = name.rsplit('.', 1)
        hashed = stem + '.' + hashlib.sha256(text.encode()).hexdigest()[:10] + '.' + suffix
        (SITE / 'assets' / hashed).write_text(text)
        if suffix == 'css':
            style = f'<link rel="stylesheet" href="/assets/{hashed}">'
        else:
            script = f'<script type="module" src="/assets/{hashed}"></script>'
    public_photos = [{key: photo[key] for key in ('name', 'caption', 'src', 'large', 'page', 'author', 'licence', 'licence_url', 'url')} for photo in photos]
    photo_json = json.dumps(public_photos, ensure_ascii=False).replace('<', '\\u003c')
    script += f'<script type="application/json" id="bp-photo-data">{photo_json}</script>'
    import os
    origin = os.environ.get('SITE_ORIGIN', 'https://motorjury.com').rstrip('/')
    schema = [
        {'@context': 'https://schema.org', '@type': 'CollectionPage', '@id': origin + PATH + '#portal',
         'name': data['title'], 'url': origin + PATH, 'description': data['description'],
         'about': {'@type': 'Brand', 'name': 'Porsche', 'url': 'https://www.porsche.com/'},
         'inLanguage': 'en', 'dateModified': data['reviewed_at']},
        {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': origin + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Car collection', 'item': origin + '/library/'},
            {'@type': 'ListItem', 'position': 3, 'name': 'Porsche', 'item': origin + PATH}]},
    ]
    write(PATH, data['title'], body, script, description=data['description'], jsonld=schema)
    file = SITE / PATH.strip('/') / 'index.html'
    text = file.read_text().replace('</head>', style + '</head>', 1)
    text = re.sub(r'(<meta property="og:image" content=")[^"]+', lambda m: m.group(1)+esc(hero['large'],quote=True), text)
    text = re.sub(r'(<meta property="og:image:alt" content=")[^"]+', lambda m: m.group(1)+'Porsche 992 Carrera S — the MotorJury Porsche portal', text)
    file.write_text(text)
    print(f'PORSCHE PORTAL: {len(photos)} credited photos, {len(generations)} generations, {len(data["films"])} official films, {len(entries)} retained identities')
    from all_brand_portals import build_all
    build_all(write, all_rows)
