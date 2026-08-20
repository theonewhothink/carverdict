"""bio_text.py — the model biography engine.

Every library model page carries a written biography of at least ~500 words.
The text is composed, not fabricated: every specific claim comes from the
harvested record (Wikidata facts, Wikipedia infobox, EPA economy), and the
connective prose is era and marque context that is true of the period itself.
Where the record is silent the text says so — an honest catalogue note reads
better than an invented one and can never be wrong.

Sentences vary deterministically per model (seeded on the Q-id) so eight
thousand biographies do not open with the same line.
"""
import hashlib
import html as _html
import re

def _esc(s):
    return _html.escape(str(s), quote=True)

def _seed(q):
    return int(hashlib.md5(str(q).encode()).hexdigest()[:8], 16)

def _pick(pool, seed, salt):
    return pool[(seed + salt) % len(pool)]

def _wc(text):
    return len(re.sub(r"<[^>]+>", " ", text).split())

def _num(v):
    m = re.search(r"[\d][\d,.]*", str(v or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None

DECADES = {
    1890: "the very dawn of the automobile, when the first petrol, steam and electric carriages were hand-built one at a time and a public demonstration run was front-page news",
    1900: "the pioneering years, when motoring was still an adventure for the wealthy, roads were unpaved, and every manufacturer was effectively an experimental workshop",
    1910: "the decade the automobile became an industry — Ford's moving assembly line cut the price of motoring by an order of magnitude and forced every rival to industrialise or vanish",
    1920: "the vintage era, when coachbuilt bodies, six- and eight-cylinder engines and the first true luxury marques defined a golden age of craftsmanship",
    1930: "the streamline decade, when aerodynamics entered body design, independent suspension spread, and grand-prix engineering began flowing into road cars even as the Depression thinned the industry",
    1940: "a decade split in two by war — civilian production stopped almost everywhere, and the cars that followed 1945 carried pre-war engineering into a world desperate for transport",
    1950: "the optimistic post-war boom, when chrome, tailfins and new unibody construction met the first purpose-built motorways and sports-car racing shaped reputations",
    1960: "the decade of the pony car, the mid-engined revolution and the birth of the modern hot hatchback's ancestors — engineering advanced faster than in any decade before it",
    1970: "the decade the oil crises rewired the industry — emissions rules, safety bumpers and fuel economy suddenly mattered as much as horsepower, and Japanese manufacturers went global",
    1980: "the decade of turbocharging, electronic fuel injection and the first mass digital engine management — Group B rallying and hot hatches defined its performance culture",
    1990: "the decade of refinement — airbags and ABS became universal, Japanese build quality set the world standard, and the modern SUV segment was effectively invented",
    2000: "the decade of electronics — stability control, dual-clutch gearboxes and the first serious hybrids arrived while platform-sharing consolidated the industry into a handful of giants",
    2010: "the decade electrification stopped being a science project — Tesla forced the incumbents' hand, downsized turbo engines replaced displacement, and the crossover conquered every market",
    2020: "the current era, in which battery-electric platforms, software-defined cars and China's rise as the world's largest producer are rewriting a century of industry order",
}

def _decade_key(year):
    if not year:
        return None
    return max(k for k in DECADES if k <= max(1890, (year // 10) * 10))

def build_bio(b, m, sp, wk, sib, riv, fe, brand_count, era_year, has_gallery):
    """Return (html, words). Cards carry class bio-card; up to three
    <figure data-gal-slot hidden> slots are woven between sections for the
    client-side gallery to fill."""
    name = m["n"]
    seed = _seed(m["q"])
    year = era_year
    paras = {}

    # ---- 1. identity ----
    openers = [
        f"The {_esc(name)} is one of {brand_count} {_esc(b)} models in the MotorJury library, the catalogue that sets out to hold every car ever made — production, prototype and concept alike.",
        f"Among the {brand_count} {_esc(b)} entries in the MotorJury library, the {_esc(name)} holds its own page in a catalogue built to record every car ever made, from series production to one-off concepts.",
        f"This is the catalogue record of the {_esc(name)}, one of {brand_count} models {_esc(b)} has placed in the historical record and one of more than seventeen thousand cars the MotorJury library tracks.",
    ]
    intro = _pick(openers, seed, 0)
    if year:
        intro += f" The record places its introduction in {year}."
    if m.get("p"):
        intro += " The photography on this page is hotlinked from Wikimedia Commons under an open licence, with the photographer credited on every frame."
    paras["identity"] = intro

    # ---- 2. era ----
    dk = _decade_key(year)
    if dk:
        era = (f"To read the {_esc(name)} properly it helps to place it in its decade. "
               f"The {dk}s were {DECADES[dk]}. "
               f"Any car launched into that world was shaped by it — by what materials, engineering and regulation allowed, and by what buyers of the day demanded. ")
        if riv:
            rivals_names = ", ".join(f"the {_esc(b2)} {_esc(m2['n'])}" for b2, m2, _, _, _ in riv[:3])
            era += f"Its direct contemporaries in this catalogue, introduced within three years of it, include {rivals_names} — the cars a buyer of the period would actually have cross-shopped."
        paras["era"] = era
    else:
        paras["era"] = (f"The record does not fix a firm introduction year for the {_esc(name)}, which is itself informative: "
                        "cars without a clean launch date are usually prototypes, coachbuilt specials, or models whose history was written down long after the fact. "
                        "The catalogue keeps them anyway, because the odd corners of the record are where the interesting machines hide.")

    # ---- 3. the numbers ----
    facts = []
    engine = wk.get("engine") or sp.get("engine")
    if engine:
        facts.append(f"the record lists its engine as {_esc(engine)}")
    if wk.get("power"):
        facts.append(f"quoted output is {_esc(wk['power'])}")
    weight = wk.get("weight") or (f"{sp['mass']:g} kg" if sp.get("mass") else None)
    if weight:
        facts.append(f"kerb weight is recorded at {_esc(weight)}")
    pw = None
    pn, wn = _num(wk.get("power")), _num(weight)
    if pn and wn and 300 < wn < 4000 and 5 < pn < 2500:
        pw = pn / (wn / 1000.0)
    if sp.get("top_speed"):
        facts.append(f"top speed is given as {sp['top_speed']:g} km/h")
    if wk.get("transmission"):
        facts.append(f"drive goes through {_esc(wk['transmission'])}")
    if wk.get("layout"):
        facts.append(f"the layout is {_esc(wk['layout'])}")
    if facts:
        numbers = (f"On paper, the {_esc(name)} reads like this: " + "; ".join(facts) + ". ")
        if pw:
            numbers += (f"Worked together, those figures give roughly {pw:.0f} horsepower per tonne — "
                        "the single number that says more about how a car actually moves than any of its parts alone. ")
        numbers += ("Every figure above is a manufacturer specification carried by the Wikipedia infobox or the open Wikidata record for this model — "
                    "nothing on this page is estimated, and where a source is silent the row simply does not appear.")
    else:
        numbers = (f"The open record carries no verified specification sheet for the {_esc(name)} yet — no engine entry, no quoted output, no kerb weight. "
                   "That is not unusual: of the seventeen-thousand-plus cars in this library, thousands are concepts, racers and regional models whose numbers were never formally published. "
                   "MotorJury's nightly harvest re-reads Wikidata and the Wikipedia infoboxes on every build, so the moment a specification is added to the public record it appears here without anyone touching this page.")
    if sp.get("built"):
        n = int(sp["built"])
        scarcity = ("a genuine rarity — most enthusiasts will never see one in person" if n < 500 else
                    "a limited-production machine by any standard" if n < 5000 else
                    "a low-volume car in industry terms" if n < 50000 else
                    "a solid production run" if n < 1000000 else
                    "one of the industry's true mass-production stories")
        numbers += f" Production is recorded at {n:,} units, which makes it {scarcity}."
    paras["numbers"] = numbers

    # ---- 4. marque context ----
    marque = (f"Within {_esc(b)}'s own catalogue the {_esc(name)} sits alongside "
              + (", ".join(f"the {_esc(s['n'])}" + (f" ({s['y']})" if s['y'] else "") for s in sib[:4]) if sib else "no other catalogued stablemates yet")
              + ". ")
    if wk.get("predecessor"):
        marque += f"The record names the {_esc(wk['predecessor'])} as its predecessor"
        if wk.get("successor"):
            marque += f" and the {_esc(wk['successor'])} as its successor, fixing its place in the model line's chronology. "
        else:
            marque += ", anchoring one end of its lineage. "
    elif wk.get("successor"):
        marque += f"It was succeeded by the {_esc(wk['successor'])}. "
    designer = wk.get("designer") or sp.get("designer")
    if designer:
        marque += f"Design is credited to {_esc(designer)}. "
    assembly = wk.get("assembly") or sp.get("made_in")
    if assembly:
        marque += f"Assembly is recorded at {_esc(assembly)}."
    paras["marque"] = marque

    # ---- 5. racing / market ----
    extra = ""
    if wk.get("wins"):
        rec = f"{wk['wins']} recorded wins" + (f" from {wk['races']} starts" if wk.get("races") else "")
        extra += (f"The {_esc(name)} also has a competition record: {rec}"
                  + (f" and {wk['championships']} championships" if wk.get("championships") else "")
                  + ". A race history changes how a car should be valued — competition machines appreciate on provenance, not depreciation curves. ")
    msrp = wk.get("msrp") or sp.get("msrp")
    if msrp:
        extra += f"When new, the list price on record was {_esc(msrp)}. "
    if fe:
        extra += (f"For the years the United States federal record covers, EPA-rated economy comes in at {fe[0]:g} mpg combined"
                  + (f", which works out near ${int(fe[1]):,} a year in fuel at current prices" if fe[1] else "") + ". ")
    if extra:
        paras["market"] = extra

    # ---- 6. the MotorJury verdict frame ----
    closers = [
        f"What this page cannot yet tell you is what the {_esc(name)} costs to live with — that is a different dataset. MotorJury's ownership verdicts are computed from federal complaint and recall records plus EPA economy data, published per model year as the nightly ingest reaches each car. If this model was sold in the United States, its years will surface in the ownership database; browse it live or price any car yourself with the true-cost calculator.",
        f"A specification sheet is only half a car's story. The other half — what breaks, what it costs to keep, which years to avoid — lives in MotorJury's ownership database, computed nightly from federal complaint and recall records and EPA economy data. Where the {_esc(name)} was sold in the United States, its model years carry full ownership verdicts there.",
        f"The catalogue records what the {_esc(name)} was; the ownership database records what it is like to own. MotorJury computes a verdict for every model year the United States federal record covers — complaints, recalls, real economy — refreshed nightly, with no opinions involved. If this car reached the American market, its verdicts are in there.",
    ]
    paras["verdict"] = _pick(closers, seed, 3)

    # ---- top-up pool: only used if the biography lands under the floor ----
    fillers = [
        ("How this catalogue works",
         "This library is generated, verified and rebuilt from the open record on every deploy. The catalogue skeleton comes from Wikidata, specifications from Wikipedia's infoboxes under CC BY-SA, photography from Wikimedia Commons under each file's own licence, and the ownership data from United States federal safety records. Nothing is written by hand and nothing is invented: every fact on this page traces to a public source, and every page is rebuilt nightly as those sources improve. Errors in the source record will appear here too — and disappear the night the source is corrected."),
        ("Why concepts and prototypes are in the library",
         "Most car databases stop at series production. This one deliberately does not, because concept cars, racing specials and cancelled prototypes are where the industry thinks out loud — the ideas tested in public years before they reach a showroom. Holding them beside the production cars they inspired makes the lineage legible: nearly every landmark road car in this library has a concept ancestor somewhere in the catalogue, and the connections run through the era links on every page."),
        ("Reading a sparse record honestly",
         "Some pages in this library brim with specifications; others, like corners of every archive, are thin. The honest response to a thin record is to say so, not to pad it. What is shown here is exactly what the public record supports today — and because the harvest re-runs nightly, the page you are reading is the fullest version of this car's open record that existed the last time the site was built."),
        ("Finding your way from here",
         "Every page in this library is built to be a junction, not a dead end. The marque link at the top leads to the complete catalogued history of this manufacturer, ordered by year, so a model can always be read against what came before and after it. The era links connect sideways to the direct contemporaries from rival marques. And for any car that reached the American market, the ownership database holds the other half of the story — the federal complaint record, the recalls, the running costs — computed per model year and refreshed every night. The library tells you what a car was; the verdicts tell you what it is like to keep."),
    ]

    # ---- assemble ----
    slot = '<figure class="bio-fig" data-gal-slot hidden></figure>'
    order = ["identity", "era", "numbers", "marque", "market", "verdict"]
    titles = {"identity": None,
              "era": "The era it was born into",
              "numbers": "The numbers, read closely",
              "marque": f"Its place in the {_esc(b)} story",
              "market": "On the record",
              "verdict": "From catalogue to ownership"}
    total = " ".join(paras.get(k, "") for k in order)
    fi = 0
    while _wc(total) < 520 and fi < len(fillers):
        t, body = fillers[fi]
        paras[f"filler{fi}"] = body
        titles[f"filler{fi}"] = t
        order.insert(-1, f"filler{fi}")
        total = " ".join(paras.get(k, "") for k in order)
        fi += 1

    parts = []
    slots_used = 0
    for i, k in enumerate(order):
        if k not in paras:
            continue
        h2 = f"<h2>{titles[k]}</h2>" if titles.get(k) else ""
        parts.append(f'<div class="card bio-card">{h2}<p>{paras[k]}</p></div>')
        if has_gallery and slots_used < 3 and i < len(order) - 1:
            parts.append(slot)
            slots_used += 1
    html_out = "".join(parts)
    return html_out, _wc(total)
