"""Original, explicitly scoped reading journeys; no copied encyclopedia prose."""
import html,json,hashlib
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DATA=json.loads((ROOT/'data/collection_profiles.json').read_text())
PROFILES={p['name']:p for p in DATA['profiles']}
esc=html.escape

@lru_cache(maxsize=1)
def catalogue_revision():
    inputs=('car_library.json','photo_additions.json','photo_delivery.json','photo_credits.json','collection_profiles.json')
    return hashlib.sha256(b''.join((ROOT/'data'/name).read_bytes() for name in inputs)).hexdigest()[:10]

def story(name):
    p=PROFILES.get(name)
    if not p:return ''
    sections=''.join(f'<section><h2>{esc(h)}</h2><p>{esc(t)}</p></section>' for h,t in p['sections'])
    sources=''.join(f'<li><a href="{esc(url,quote=True)}" rel="noopener">{esc(title)}</a><p class="note">{esc(scope)}</p></li>' for title,url,scope in p['sources'])
    return f'<article class="collection-story" data-reviewed-profile><p class="eyebrow">The design story · {esc(p["scope"])}</p><h2>{esc(p["title"])}</h2><p class="lede">{esc(p["intro"])}</p>{sections}<aside class="callout"><b>A question worth keeping</b><p>{esc(p["question"])}</p></aside><h2>Check the source, then the version</h2><ul>{sources}</ul><p class="note">Research checked {DATA["reviewed_at"]}. {esc(DATA["method"])} Manufacturer accounts are primary records of their projects, not independent evidence of ownership quality. This profile does not establish an individual car’s condition or value.</p></article>'

def main(write,all_rows,card):
    picks={r['n']:r for r in all_rows if r['n'] in PROFILES}
    public=[dict(p,url=picks[p['name']]['u']) for p in DATA['profiles']]
    (ROOT/'site/assets/collection-profiles.json').write_text(json.dumps(public,ensure_ascii=False,separators=(',',':')))
    groups=[('The engine changes the shape','Follow three ways to package a dramatic sports car.',['Lamborghini Miura','Ferrari F40','Honda NSX']),('The brief changes the car','A compact open roadster and a road car with a racing brief.',['Mazda MX-5','BMW M3']),('A detail with a reason','Start with the doors. End with the frame underneath them.',['Mercedes-Benz 300 SL'])]
    body='<section class="collection-hero compact"><p class="eyebrow">Follow your curiosity</p><h1>There is a reason it looks like that.</h1><p class="lede">Six cars. Six design decisions. Choose a question, find the story, then keep the cars you want to explore.</p></section><section class="card"><h2>What draws you to a car?</h2><form data-discovery-question><label for="discovery-question">Tell us what you want to explore</label><div class="collection-search-line"><input id="discovery-question" name="q" maxlength="200" placeholder="Lightweight roadsters, racing history, unusual doors…"><button>Find my starting point →</button></div></form><p class="note">Guided discovery uses this small reviewed collection. It runs in your browser; it does not send your question to an AI service.</p><p role="status" data-discovery-status></p><div class="collection-chips"><button type="button" data-discovery-prompt="roadster">Open-top simplicity</button><button type="button" data-discovery-prompt="engine">Supercar engineering</button><button type="button" data-discovery-prompt="racing">Racing roots</button><button type="button" data-discovery-prompt="doors">Design with a reason</button></div></section>'
    for title,description,names in groups:
        if len(names)==1:
            body+=f'<section class="collection-feature"><div><p class="eyebrow">Design with a reason</p><h2>{title}</h2><p>{description}</p><a class="button" href="{picks[names[0]]["u"]}">Read the design story →</a></div>'+card(picks[names[0]])+'</section>'
        else:
            body+=f'<section><h2>{title}</h2><p>{description}</p><div class="collection-grid journey-{len(names)}">'+''.join(card(picks[n]) for n in names)+'</div></section>'
    body+='<section class="card"><h2>Keep exploring</h2><p>Save cars to your shortlist and compare the researched design briefs. The full collection also includes entries whose history is still being checked.</p><a class="button" href="/shortlist/">Open my shortlist →</a> <a href="/library/">Search every catalogue entry</a></section>'
    write('/discover/','Car design stories — follow your curiosity',body)
    body='<section class="collection-hero compact"><p class="eyebrow">Your own collection</p><h1>The cars that stayed with you.</h1><p class="lede">Save a car anywhere in the collection. Choose up to three to compare their design briefs.</p><p class="note">Saved in this browser only. No account required. Clearing browser data removes the list. Your question and saved cars are not sent to an AI service.</p></section><section data-shortlist><p role="status" data-shortlist-status>Loading your saved cars…</p><div class="collection-grid" data-shortlist-grid></div><div class="actions"><button type="button" data-shortlist-export>Download my list</button><button type="button" class="secondary" data-shortlist-clear>Clear my list</button></div><section data-shortlist-comparison hidden><h2>Different briefs. Different compromises.</h2><p class="note">Facts below apply to the stated historical version. Catalogue photographs can show later cars. These are design comparisons, not buying verdicts.</p><div class="comparison-grid" data-comparison-grid></div></section><noscript><p>Saving and comparing needs JavaScript. <a href="/discover/">Read the design stories</a> or <a href="/all-cars/">browse the complete directory</a>.</p></noscript></section><section class="card"><h2>Start with a car you cannot ignore.</h2><a href="/discover/">Explore the six design stories →</a> · <a href="/library/">Search the full photo collection →</a></section>'
    write('/shortlist/','Your saved cars and design comparisons',body)
    for path in ('/shortlist/',):
        f=ROOT/'site'/path.strip('/')/'index.html';f.write_text(f.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))

@lru_cache(maxsize=1)
def asset_script():
    assets=ROOT/'site/assets';assets.mkdir(parents=True,exist_ok=True)
    def emit(name,text):
        hashed=name.replace('.mjs','.'+hashlib.sha256(text.encode()).hexdigest()[:10]+'.mjs')
        (assets/hashed).write_text(text);return hashed
    catalogue=emit('catalogue-core.mjs',(ROOT/'assets/catalogue-core.mjs').read_text())
    core=emit('collection-core.mjs',(ROOT/'assets/collection-core.mjs').read_text().replace('./catalogue-core.mjs','./'+catalogue))
    app=emit('collection.mjs',(ROOT/'assets/collection.mjs').read_text().replace('./collection-core.mjs','./'+core).replace('./catalogue-core.mjs','./'+catalogue).replace('__CATALOGUE_VERSION__',catalogue_revision()))
    return '<script type="module" src="/assets/'+app+'"></script>'
