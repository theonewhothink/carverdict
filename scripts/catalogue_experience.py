"""Photo-led discovery of every distinct stored entry; no claim of global completeness."""
import html,json,hashlib,re,shutil,math
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote
import build_library as lib
ROOT=Path(__file__).resolve().parent.parent
SITE=ROOT/'site'
esc=html.escape
FEATURED=['Ferrari F40','Lamborghini Miura','BMW M3','Mazda MX-5','Honda NSX','Mercedes-Benz 300 SL','Ford Mustang','Volkswagen Golf','Toyota RAV4','Citroën DS','Alpine A110','Lancia Stratos','Jaguar E-Type','Porsche 356','Aston Martin DB5','Audi Quattro']

@lru_cache(maxsize=1)
def photo_credits():
    path=ROOT/'data/photo_credits.json'
    return json.loads(path.read_text()) if path.exists() else {}

def rows():
    lib.load_model_index();brands=lib.build_dataset();out=[]
    credits=photo_credits()
    for brand,models in brands.items():
        bs=lib.slug(brand)
        for m in models:
            ms=lib.slug(m['n']);has=m['n'] in lib.MODEL_INDEX.get(bs,{})
            out.append(dict(n=m['n'],b=brand,p=m['p'],y=m['y'],q=m['q'],u=f'/library/{bs}/{ms}/' if has else f'/library/{bs}/#m-{ms}',t=credits.get(m['p'],{}).get('thumb','')))
    return sorted(out,key=lambda r:r['n'].casefold()),brands

def image(filename,name,lazy=True):
    if not filename:return '<span class="collection-photo photo-missing">Photo not yet catalogued</span>'
    credits=photo_credits()
    src=credits.get(filename,{}).get('thumb') or lib.commons_thumb(filename,640)
    return f'<span class="collection-photo"><img src="{esc(src,quote=True)}" alt="{esc(name)} · catalogue photograph" width="640" height="400" decoding="async" {"loading=lazy" if lazy else "fetchpriority=high"} referrerpolicy="no-referrer"></span>'

def card(r,lazy=True):
    credit='<a class="collection-credit" href="'+esc(lib.commons_page(r['p']),quote=True)+'" rel="noopener">Photo &amp; attribution ↗</a>' if r['p'] else '<span class="collection-credit">Photo not yet catalogued</span>'
    save=f'<button type="button" class="save-car" data-save-car="{esc(r["u"],quote=True)}" data-car-name="{esc(r["n"],quote=True)}" aria-pressed="false">Save car +</button>'
    return f'<article class="collection-card"><a href="{esc(r["u"],quote=True)}">{image(r["p"],r["n"],lazy)}<div class="collection-card-body"><span class="collection-brand">{esc(r["b"])}</span><h3>{esc(r["n"])}</h3></div></a>{credit}{save}</article>'

def roster_row(r):
    photo=('<a class="roster-credit" href="'+esc(lib.commons_page(r['p']),quote=True)+'">View photograph &amp; attribution ↗</a>') if r['p'] else ''
    status='Photo reference' if r['p'] else 'Photo not yet catalogued'
    return f'<li id="m-{lib.slug(r["n"])}"><a href="{esc(r["u"],quote=True)}"><b>{esc(r["n"])}</b><span>{status}</span></a>{photo}</li>'


def selected(all_rows):
    picks=[next((r for r in all_rows if r['n']==name and r['p']),None) for name in FEATURED]
    return [r for r in picks if r]

@lru_cache(maxsize=1)
def photo_candidates():
    result={}
    for row in lib.DATA:
        if row['p']:
            key=re.sub(r'[^a-z0-9]','',row['n'].lower())
            result.setdefault(key,[]).append(row)
    return result


def record_photo(make,model,year=None):
    key=re.sub(r'[^a-z0-9]','',(make+' '+model).lower())
    if key=='toyotarav4':
        filename='2019 Toyota RAV4 LE 2.5L front 4.14.19.jpg';name='2019 Toyota RAV4 LE'
        return f'<figure class="record-photo">{image(filename,name)}<figcaption>{name}, shown as a nameplate illustration; your year and trim may differ. Photo: <a href="{lib.commons_page(filename)}">Kevauto</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. Displayed in a cropped frame.</figcaption></figure>'
    candidates=photo_candidates().get(key,[])
    for x in candidates:
        filename=x['p'];dates=[int(y) for y in re.findall(r'(?:19|20)\d{2}',filename)]
        if re.search(r'prototype|spy|camoufla|render|concept',filename,re.I) or (year and dates and min(dates)>int(year)+1):continue
        return f'<figure class="record-photo">{image(filename,x["n"])}<figcaption>Catalogue illustration of {esc(x["n"])}; exact generation, year and trim are not verified. <a href="{esc(lib.commons_page(filename),quote=True)}">Photo, author and licence</a>.</figcaption></figure>'
    return ''

def main(write):
    all_rows,brands=rows();featured=selected(all_rows);n=len(all_rows);photos=sum(bool(r['p']) for r in all_rows)
    (SITE/'assets/catalogue-data.json').write_text(json.dumps(all_rows,separators=(',',':'),ensure_ascii=False))
    for name in ['catalogue.css','catalogue-core.mjs','catalogue.mjs']:
        shutil.copy2(ROOT/'assets'/name,SITE/'assets'/name)
    core=(ROOT/'assets/catalogue-core.mjs').read_text();core_name='catalogue-core.'+hashlib.sha256(core.encode()).hexdigest()[:10]+'.mjs';(SITE/'assets'/core_name).write_text(core)
    app=(ROOT/'assets/catalogue.mjs').read_text().replace('./catalogue-core.mjs','./'+core_name);app_name='catalogue.'+hashlib.sha256(app.encode()).hexdigest()[:10]+'.mjs';(SITE/'assets'/app_name).write_text(app)
    script=f'<script type="module" src="/assets/{app_name}"></script>'
    search='<form class="collection-search" data-collection-entry role="search"><label for="car-search">Find a car or marque</label><div><input id="car-search" name="q" type="search" placeholder="Try Ferrari, 911 or Toyota RAV4" autocomplete="off"><button>Find cars <span aria-hidden="true">→</span></button></div></form>'
    stats=f'<p class="collection-stats"><b>{n:,}</b> catalogue entries <span>·</span> <b>{len(brands):,}</b> marques <span>·</span> <b>{photos:,}</b> photo references</p>'
    header=f'<section class="collection-hero"><p class="eyebrow">For the cars you love. And the one you might buy.</p><h1>A whole world of cars.</h1><p class="lede">Classics, icons and everyday cars. Find yours.</p>{search}{stats}</section>'
    gallery='<div class="collection-grid">'+''.join(card(r,lazy=i>0) for i,r in enumerate(featured[:12]))+'</div>'
    home=header+'<nav class="collection-chips" aria-label="Explore by interest"><a href="/discover/">Six design stories →</a><a href="/shortlist/">My saved cars →</a><a href="/buying-brief/">Prepare for a viewing →</a></nav>'+'<section aria-label="Explore the collection">'+gallery+'<div class="collection-bottom"><a class="button" href="/library/">Explore the photo collection →</a><a href="/all-cars/">Complete A–Z directory</a></div></section><section class="collection-feature"><div><p class="eyebrow">Considering a used RAV4?</p><h2>Take better questions to the viewing.</h2><p>A source-backed 2019–2020 US RAV4 brief, a private checklist and a budget using your numbers.</p><a class="button" href="/buying-brief/">Prepare my buying brief →</a></div>'+record_photo('Toyota','RAV4')+'</section><p class="note">This is the complete current MotorJury catalogue, not a verified list of every car ever made. Reference photos may show another generation or trim. <a href="/catalogue-notes/">Coverage and photo credits</a>.</p>'
    write('/','Explore the world of cars',home,script)
    options=''.join(f'<option>{esc(b)}</option>' for b in sorted(brands))
    filters=f'<details class="collection-filters"><summary>Filter by marque, decade or photos</summary><div class="grid"><label>Marque<select name="brand"><option value="">All marques</option>{options}</select></label><label>Recorded decade<select name="era"><option value="">All decades, including unknown</option>'+''.join(f'<option value="{y}">{y}s</option>' for y in range(1880,2030,10))+'</select></label><label>Sort<select name="sort"><option value="featured">Photos first</option><option value="name">Name A–Z</option><option value="oldest">Oldest recorded year</option></select></label><label class="check"><input type="checkbox" name="photos">Only entries with photo references</label></div><button class="secondary" type="button" data-catalogue-reset>Reset filters</button></details>'
    quick=''.join(f'<a href="/library/{lib.slug(b)}/" data-marque="{esc(b)}">{esc(b)}</a>' for b in ['Porsche','Ferrari','BMW','Toyota','Ford','Mercedes-Benz'])
    body=f'<section class="collection-hero compact"><p class="eyebrow">The MotorJury collection</p><h1>Find your car.</h1>{stats}</section><section data-catalogue><form data-catalogue-form><label for="collection-query">Search all catalogue entries</label><div class="collection-search-line"><input name="q" id="collection-query" type="search" autocomplete="off" placeholder="A marque, model or a car you remember"><button>Search</button></div>{filters}</form><nav class="collection-chips" aria-label="Quick marque filters">{quick}</nav><div class="collection-result-head"><p role="status" data-catalogue-status>Explore a few favourites, or search the entire collection.</p><a href="/all-cars/">Every entry, A–Z →</a></div><div class="collection-grid" data-catalogue-grid>{"".join(card(r,lazy=i>0) for i,r in enumerate(featured))}</div><button class="secondary collection-more" type="button" data-catalogue-more>Show more cars</button><noscript><p>Search needs JavaScript. The <a href="/all-cars/">complete paginated A–Z list</a> and every marque below work without it.</p></noscript></section><details class="card"><summary>Browse all {len(brands):,} marques</summary><div class="marque-directory">'+''.join(f'<a href="/library/{lib.slug(b)}/">{esc(b)} <span>{len(brands[b])}</span></a>' for b in sorted(brands))+'</div></details><p class="note">Every distinct stored entry is searchable, including cars without a photograph or recorded year. Missing dates are excluded only when you choose a decade. <a href="/catalogue-notes/">Coverage and image credits</a>.</p>'
    write('/library/','Search the complete MotorJury car collection',body,script)
    # Modern marque pages retain every roster row, while loading photos in useful batches.
    for brand,models in brands.items():
        entries=sorted([r for r in all_rows if r['b']==brand],key=lambda r:(not bool(r['p']),r['n']))
        roster=''.join(roster_row(r) for r in entries)
        form=f'<form data-catalogue-form><label for="collection-query">Search the collection</label><div class="collection-search-line"><input name="q" id="collection-query" type="search" placeholder="Find a model"><button>Search</button></div>{filters}</form>'
        body=f'<section class="collection-hero compact"><p class="eyebrow"><a href="/library/">The car collection</a> / {esc(brand)}</p><h1>{esc(brand)}</h1><p>{len(entries):,} catalogue entries · {sum(bool(r["p"]) for r in entries):,} photo references</p></section><section data-catalogue data-catalogue-brand="{esc(brand)}">{form}<p role="status" data-catalogue-status>Showing {min(24,len(entries))} entries. Browse more photographs or open the complete roster below.</p><div class="collection-grid" data-catalogue-grid>{"".join(card(r,lazy=i>0) for i,r in enumerate(entries[:24]))}</div><button class="secondary collection-more" type="button" data-catalogue-more {"hidden" if len(entries)<=24 else ""}>Show more cars</button></section><details class="card"><summary>Complete {esc(brand)} roster · {len(entries):,} entries</summary><ul class="car-directory">{roster}</ul></details><p class="note">Reference photographs may show another generation or trim. Catalogue identities are not reviewed buying advice. <a href="/catalogue-notes/">Coverage and photo credits</a>.</p>'
        write('/library/'+lib.slug(brand)+'/',brand+' car collection',body,script)
        # Retain the prior library hold until collection evidence and image permissions are reviewed.
        f=SITE/'library'/lib.slug(brand)/'index.html';f.write_text(f.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))
    # Every entry has a crawlable, usable HTML directory row; no JavaScript or photo is required.
    size=120;total=math.ceil(n/size)
    for page in range(1,total+1):
        path='/all-cars/' if page==1 else f'/all-cars/page/{page}/'
        subset=all_rows[(page-1)*size:page*size]
        links=''.join(f'<li><a href="{esc(r["u"],quote=True)}"><b>{esc(r["n"])}</b><span>{esc(r["b"])}</span></a></li>' for r in subset)
        prev=('/all-cars/' if page==2 else f'/all-cars/page/{page-1}/')
        nav=(f'<a class="button secondary" href="{prev}">← Previous</a>' if page>1 else '')+f'<span>Page {page} of {total}</span>'+(f'<a class="button secondary" href="/all-cars/page/{page+1}/">Next →</a>' if page<total else '')
        body=f'<section class="collection-hero compact"><p class="eyebrow">Every entry in the current catalogue</p><h1>Cars, A–Z.</h1><p>{n:,} distinct entries · {esc(subset[0]["n"])} to {esc(subset[-1]["n"])}</p><a href="/library/">Search or browse with photos →</a></section><nav class="directory-pages" aria-label="Directory pages">{nav}</nav><ol class="car-directory" start="{(page-1)*size+1}">{links}</ol><nav class="directory-pages" aria-label="More directory pages">{nav}</nav><p class="note">The full current catalogue, including missing photos and dates. Global historical completeness is not established. <a href="/catalogue-notes/">Read the coverage notes</a>.</p>'
        write(path,'Car directory — page '+str(page),body)
        if page>1:
            f=SITE/path.strip('/')/'index.html';f.write_text(f.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))
    credits=photo_credits()
    credit_list=''.join(f'<li><a href="{esc(lib.commons_page(name),quote=True)}">{esc(name)}</a> — {esc(c["author"])} · <a href="{esc(c["licence_url"],quote=True)}">{esc(c["licence"])}</a>. Displayed in cropped frames.</li>' for name,c in credits.items())
    write('/catalogue-notes/','Catalogue coverage and photography',f'<section class="collection-hero compact"><h1>A collection with room to grow.</h1></section><article class="card"><p>MotorJury preserves {len(lib.DATA):,} raw catalogue rows. Duplicate paths are merged into {n:,} distinct entries across {len(brands):,} marques. The directory includes entries without photos or reliable dates. These are catalogue identities, not independently reviewed ownership advice.</p><p>We aim to document automotive history broadly. We cannot establish that this snapshot contains every car ever made, every local badge, prototype or racing variant. Catalogue identities originated in Wikidata; buying advice uses separately linked primary evidence. Wikipedia prose is not reproduced.</p><p>Existing photo references remain accessible through the collection and marque pages. Each photograph links to its Commons file page with its author, licence and original image. Featured-image metadata below was checked on 6 October 2026. The rest of the inherited photo permissions still require review; a hotlink does not remove attribution obligations.</p><h2>Featured photographs</h2><ul>{credit_list}</ul><a href="/all-cars/">Browse every current entry</a></article>')
    (SITE/'assets/catalogue-coverage.json').write_text(json.dumps({'raw_rows':len(lib.DATA),'distinct_entries':n,'marques':len(brands),'photo_references':photos,'directory_pages':total,'directory_page_size':size}))
    from collection_stories import main as build_stories
    build_stories(write,all_rows,card)
    print(f'COLLECTION: all {n} distinct entries searchable and in {total} HTML directory pages; {photos} photo references preserved')
