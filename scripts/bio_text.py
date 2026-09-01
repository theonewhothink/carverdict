"""bio_text.py — the model biography engine.

Every library model page carries a short biography built only from sourced facts.
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


def _clean(v):
    """Reject infobox-template debris before it reaches prose."""
    s = re.sub(r"\s+", " ", str(v or "")).strip()
    fields = r"class|body(?:_style)?|engine|power|layout|transmission|production|assembly|designer|predecessor|successor|wheelbase|length|width|height|weight"
    if not s or re.search(rf"(?:^|\b)(?:{fields})\s*=|unbulleted list|plainlist|\{{\{{|\}}\}}", s, re.I):
        return None
    return s

def build_bio(b, m, sp, wk, sib, riv, fe, brand_count, era_year, has_gallery):
    """Write only what the record carries.

    The previous version padded every biography to ~500 words with era essays, a
    "how to read the record" lecture and a generic closing paragraph, repeated across
    eleven thousand pages. Google AdSense rejected the site for exactly that ("low value
    content"). This version emits a sentence only when a sourced fact stands behind it;
    a model with no facts gets two honest lines, and the page is marked thin so the
    build can keep it out of the index (it still serves readers and navigation).

    Returns (html, word_count, fact_count).
    """
    name, year = m["n"], era_year
    seed = _seed(m["q"])
    engine = _clean(wk.get("engine")) or _clean(sp.get("engine"))
    power = _clean(wk.get("power"))
    body = _clean(wk.get("body"))
    designer = _clean(wk.get("designer")) or _clean(sp.get("designer"))
    assembly = _clean(wk.get("assembly")) or _clean(sp.get("made_in"))
    production = _clean(wk.get("production"))
    weight = _clean(wk.get("weight")) or (f"{sp['mass']:g} kg" if sp.get("mass") else None)
    transmission = _clean(wk.get("transmission"))
    layout = _clean(wk.get("layout"))
    predecessor, successor = _clean(wk.get("predecessor")), _clean(wk.get("successor"))
    msrp = _clean(wk.get("msrp")) or _clean(sp.get("msrp"))

    def full_name(brand, row):
        n = row["n"]
        return n if n.lower().startswith(brand.lower() + " ") else f"{brand} {n}"

    facts = 0
    sections = []

    # --- lead: the identity line, from the catalogue ---
    lead = f"The {_esc(name)} is a {_esc(b)} model"
    if production:
        lead += f" built {_esc(production)}"; facts += 1
    elif year:
        lead += f" introduced in {year}"; facts += 1
    if body:
        lead += f", catalogued as a {_esc(body)}"; facts += 1
    lead += "."
    if designer:
        lead += f" Its design is credited to {_esc(designer)}."; facts += 1
    if assembly:
        lead += f" Assembly is recorded at {_esc(assembly)}."; facts += 1
    sections.append((None, lead))

    # --- engineering: only sourced figures ---
    eng = []
    if engine:
        eng.append(f"engine: {_esc(engine)}")
    if power:
        eng.append(f"power: {_esc(power)}")
    if transmission:
        eng.append(f"transmission: {_esc(transmission)}")
    if layout:
        eng.append(f"layout: {_esc(layout)}")
    if weight:
        eng.append(f"kerb weight: {_esc(weight)}")
    if sp.get("top_speed"):
        eng.append(f"top speed: {sp['top_speed']:g} km/h")
    if eng:
        facts += len(eng)
        text = f"Published specification: {'; '.join(eng)}."
        pn, wn = _num(power), _num(weight)
        if pn and wn and 300 < wn < 4000 and 5 < pn < 2500:
            text += f" That works out to roughly {pn / (wn / 1000):.0f} horsepower per tonne."
        text += " These are manufacturer figures carried by Wikipedia or Wikidata, not road-test measurements."
        sections.append(("Specification", text))

    # --- lineage: only where the record names it ---
    lin = []
    if predecessor:
        lin.append(f"it followed the {_esc(predecessor)}")
    if successor:
        lin.append(f"it was succeeded by the {_esc(successor)}")
    if sp.get("built"):
        lin.append(f"recorded production totals {int(sp['built']):,} cars")
    if lin:
        facts += len(lin)
        text = f"In the {_esc(b)} line-up, {'; '.join(lin)}."
        if sib:
            text += " Related catalogue entries: " + ", ".join(f"the {_esc(s['n'])}" for s in sib[:4]) + "."
        sections.append(("Lineage", text))

    # --- money and racing: only where sourced ---
    market = []
    if msrp:
        market.append(f"the recorded list price when new was {_esc(msrp)}")
    if fe:
        t = f"EPA combined economy is {fe[0]:g} mpg"
        if fe[1]:
            t += f" (about ${int(fe[1]):,} a year in fuel at EPA assumptions)"
        market.append(t)
    if wk.get("wins"):
        t = f"the competition record lists {wk['wins']} wins"
        if wk.get("races"):
            t += f" from {wk['races']} starts"
        market.append(t)
    if market:
        facts += len(market)
        text = "; ".join(market)
        text = text[0].upper() + text[1:] + ". Condition, mileage and specification move any individual car a long way from a headline figure; the ownership section separates purchase price, depreciation, insurance, fuel and repair risk where a United States model-year record exists."
        sections.append(("Price and economy", text))

    if riv and facts >= 2:
        rivals = ", ".join(f"the {_esc(full_name(b2, m2))}" for b2, m2, _, _, _ in riv[:3])
        sections.append(("Contemporaries", f"Catalogue contemporaries introduced within a few years of the {_esc(name)} include {rivals}."))

    if facts < 2:
        sections.append(("Record status",
            f"The open record for the {_esc(name)} carries no verified engine, output, weight or price yet. "
            "MotorJury does not fill gaps with guesses; this entry exists so the model has a place in the catalogue and "
            "grows as sourced specifications and photographs are added. Corrections: corrections@motorjury.com."))

    text_all = " ".join(p for _, p in sections)
    slot = '<figure class="bio-fig" data-gal-slot hidden></figure>'
    parts, slots_used = [], 0
    for i, (title, paragraph) in enumerate(sections):
        heading = f"<h2>{title}</h2>" if title else ""
        parts.append(f'<section class="card bio-card">{heading}<p>{paragraph}</p></section>')
        if has_gallery and slots_used < 6 and i < len(sections) - 1:
            parts.append(slot)
            slots_used += 1
    return "".join(parts), _wc(text_all), facts
