"""bio_text.py — the model biography engine: a magazine-style article from the record.

Everything specific in the article is sourced: the Wikipedia article summary (CC BY-SA,
attributed), the infobox specification, Wikidata facts, the EPA record and MotorJury's own
ownership data. The connective prose interprets those facts — what a mid-engined layout
means on the road, what 300 horsepower per tonne feels like, why a coachbuilt one-off has
no price — and never invents a figure. Where the record is thin the article is short and
says so; the build keeps such pages out of the search index.

Photographs and Commons videos are woven into the article by gallery.js, which fills every
<figure data-gal-slot> in document order, so the media sit beside the paragraph they
illustrate rather than in a bin at the bottom. Phrasing varies deterministically per model
(seeded on the Wikidata id), so eight thousand articles do not open with the same line.
"""
import hashlib
import html as _html
import json
import re
from pathlib import Path

# Ad units. In-article native units read as part of the article and pay far better than
# a banner. The slot id is created in AdSense (Ads -> By ad unit -> In-article) and kept
# in data/ads.json; until it exists, Auto Ads (loaded in every page head) place units and
# the anchor div below tells the placer where an in-article unit is welcome.
AD_CLIENT = "ca-pub-6675837012921030"
try:
    _ADS = json.load(open(Path(__file__).resolve().parent.parent / "data" / "ads.json"))
except Exception:
    _ADS = {}
AD_SLOT_IN_ARTICLE = str(_ADS.get("in_article_slot") or "")


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
    s = s.replace("&ndash;", "–").replace("&mdash;", "—").replace("&amp;", "&")
    fields = (r"class|body(?:_style)?|engine|power|layout|transmission|production|assembly|designer|"
              r"predecessor|successor|wheelbase|length|width|height|weight|sp|related|platform|aka")
    if not s or "=" in s or re.search(rf"(?:^|\b)(?:{fields})\s*=|unbulleted list|plainlist|\{{\{{|\}}\}}|\[\[", s, re.I):
        return None
    if len(s) > 220:
        s = s[:217].rsplit(" ", 1)[0] + "…"
    return s


def _first(v):
    """'4.0L H6 (GT9) / 3.6L H6 (GT9-CS)' -> '4.0L H6'; 'Stradale: 190 hp / Group 4: 280 hp'
    -> '190 hp'; 'Germany: / Zuffenhausen (Porsche)' -> 'Zuffenhausen' — the headline value."""
    if not v:
        return None
    parts = [x.strip() for x in re.split(r"\s+/\s+|\s*;\s*|\s*\|\s*", v) if x.strip()]
    head = ""
    for x in parts:
        x = re.sub(r"^[A-Za-z][\w .-]{0,24}:\s*", "", x)     # drop a short "Label:" prefix
        x = re.sub(r"\s*\([^)]*\)\s*$", "", x).strip(" ,:")
        if x:
            head = x
            break
    return head or v


def _layout_words(layout):
    l = (layout or "").lower()
    if "mr" in l or "mid-engine" in l or "rear mid" in l:
        return "the engine sits behind the driver and ahead of the rear axle, which puts the mass in the middle of the car and is why mid-engined cars change direction the way they do"
    if "rr" in l or "rear-engine" in l:
        return "the engine hangs behind the rear axle, a layout that gives ferocious traction out of a corner and a reputation to match on the way in"
    if "awd" in l or "4wd" in l or "four-wheel" in l or "all-wheel" in l or "quattro" in l:
        return "drive goes to all four wheels, which is what lets the power be used on a wet road"
    if "ff" in l or "front-wheel" in l:
        return "the engine drives the front wheels, the packaging choice that gives a small car a big cabin"
    if "fr" in l or "front-engine, rear" in l or "rear-wheel" in l:
        return "a front engine drives the rear wheels, the classic proportion — long bonnet, cabin set back — that most people picture when they picture a sports saloon or a grand tourer"
    return None


def _years_of(production, year):
    m = re.findall(r"(?:18|19|20)\d\d", str(production or ""))
    if m:
        if len(m) >= 2 and m[0] != m[-1]:
            return int(m[0]), int(m[-1])
        return int(m[0]), None
    if year:
        return int(year), None
    return None, None


def _decade_note(start):
    """One clause of context that is true of the period."""
    if not start:
        return ""
    d = (start // 10) * 10
    return {
        1890: "when the motor car was still a public experiment",
        1900: "when a car was a rich man's adventure and every maker was a workshop",
        1910: "as the assembly line was turning motoring into an industry",
        1920: "the vintage years, when coachbuilders still shaped most of what was sold",
        1930: "when streamlining and independent suspension were arriving together",
        1940: "in a decade split by war, when civilian production stopped and restarted",
        1950: "at the height of the post-war boom",
        1960: "in the decade that gave the world the pony car and the mid-engined supercar",
        1970: "as the oil crises and the first emissions rules rewired the industry",
        1980: "in the age of turbocharging and the first electronic engine management",
        1990: "when airbags, anti-lock brakes and Japanese build quality became the world standard",
        2000: "in the decade of stability control, dual-clutch gearboxes and the first serious hybrids",
        2010: "as electrification stopped being an experiment and the crossover took every market",
        2020: "in the decade the industry is turning electric",
    }.get(d, "")


def _p(text):
    return f"<p>{text}</p>"


def build_bio(b, m, sp, wk, sib, riv, fe, brand_count, era_year, has_gallery, own=None):
    """Returns (html, word_count, fact_count).

    own: optional ownership summary from build_models.ownership_summary (price, running,
    insurance) so the article can close on what the car costs to own today.
    """
    name = m["n"]
    seed = _seed(m["q"])
    engine = _clean(wk.get("engine")) or _clean(sp.get("engine"))
    power = _clean(wk.get("power"))
    body = _clean(wk.get("body"))
    designer = _clean(wk.get("designer")) or _clean(sp.get("designer"))
    assembly = _clean(wk.get("assembly")) or _clean(sp.get("made_in"))
    if assembly and ("/" in assembly or ";" in assembly):
        assembly = _first(assembly)
    if assembly:
        assembly = re.sub(r"^([A-Z][\w .-]{1,30}):\s*(.+)$", r"\2, \1", assembly)   # "Italy: Turin" -> "Turin, Italy"
    production = _clean(wk.get("production"))
    weight = _clean(wk.get("weight")) or (f"{sp['mass']:g} kg" if sp.get("mass") else None)
    weight = _first(weight) if weight else None
    transmission = _clean(wk.get("transmission"))
    layout = _clean(wk.get("layout"))
    wheelbase = _clean(wk.get("wheelbase"))
    predecessor, successor = _clean(wk.get("predecessor")), _clean(wk.get("successor"))
    msrp = _clean(wk.get("msrp")) or _clean(sp.get("msrp"))
    built = int(sp["built"]) if sp.get("built") else None
    about = (wk.get("about") or "").strip()
    wp = wk.get("wp") or name
    start, end = _years_of(production, era_year)
    dn = _decade_note(start)

    def full_name(brand, row):
        n = row["n"]
        return n if n.lower().startswith(brand.lower() + " ") else f"{brand} {n}"

    facts = sum(1 for x in (engine, power, body, designer, assembly, production or start, weight,
                            transmission, layout, wheelbase, predecessor, successor, msrp, built) if x)
    if about:
        facts += 2

    sections = []   # (title, html)

    # ---------------------------------------------------------------- 1. the lede ----
    e_head, p_head = _first(engine), _first(power)
    when = f"in {start}" if start else ""
    span = (f"from {start} to {end}" if start and end else (f"from {start}" if start else ""))
    built_phrase = ("built " + span) if span else (("introduced " + when) if when else "")
    lw = _layout_words(layout)
    lede_pool = []
    if e_head and p_head:
        lede_pool += [
            f"Strip the {_esc(name)} back to its specification sheet and the character is already there: {_esc(e_head)}, {_esc(p_head)}. {_esc(b)} {built_phrase or 'built it in small numbers'}{', ' + dn if dn else ''}.",
            f"Every car is an argument about what matters, and the {_esc(name)} makes its case with {_esc(e_head)} and {_esc(p_head)}. {_esc(b)} {built_phrase or 'put it on sale and let the numbers do the talking'}{' — ' + dn if dn else ''}.",
            f"The {_esc(name)} is the {_esc(b)} that answered a simple question — how much car can this badge carry? — with {_esc(p_head)} from {_esc(e_head)}. It was {built_phrase or 'built in small numbers'}{', ' + dn if dn else ''}.",
            f"Numbers first, because with the {_esc(name)} they are the story: {_esc(e_head)}, {_esc(p_head)}. {_esc(b)} {built_phrase or 'built it'}{', ' + dn if dn else ''}.",
        ]
    elif e_head or body:
        lede_pool += [
            f"The {_esc(name)} is a {_esc(body) if body else 'car'} from {_esc(b)}{', ' + built_phrase if built_phrase else ''}{', ' + dn if dn else ''}{'. Under the bonnet: ' + _esc(e_head) if e_head else ''}.",
            f"{_esc(b)} does not build many cars like the {_esc(name)}{': a ' + _esc(body) if body else ''}{' with ' + _esc(e_head) if e_head else ''}, {built_phrase or 'made in small numbers'}{' ' + dn if dn else ''}.",
            f"Start with what the {_esc(name)} is: a {_esc(body) if body else 'car'}{' with ' + _esc(e_head) if e_head else ''}, {built_phrase or 'from ' + _esc(b)}{', ' + dn if dn else ''}. What it meant takes a little longer.",
        ]
    else:
        lede_pool += [
            f"The {_esc(name)} is one of the {_esc(b)} entries the open record knows by name{' and by date — ' + when if when else ''}, and by little else. That is not nothing: a name in the catalogue is where a car's story starts to be recoverable.",
            f"Some cars leave a paper trail; the {_esc(name)} left a name{', a year — ' + str(start) + ' — ' if start else ' '}and a place in {_esc(b)}'s list. What follows is what can be said with a source behind it.",
        ]
    lede = _pick(lede_pool, seed, 0)
    if designer:
        lede += " " + _pick([
            f"The shape is credited to {_esc(designer)}.",
            f"{_esc(designer)} drew it.",
            f"Its designer of record is {_esc(designer)}.",
        ], seed, 1)
    if built:
        lede += " " + _pick([
            f"Production ran to {built:,} cars.",
            f"{built:,} were built.",
            f"The total made was {built:,}.",
        ], seed, 2)
    sections.append((None, _p(lede)))

    # ------------------------------------------------------- 2. the story (Wikipedia) ----
    if about:
        paras = [x.strip() for x in re.split(r"\n{2,}", about) if x.strip()]
        if len(paras) == 1 and len(paras[0]) > 520:
            sents = re.split(r"(?<=[.!?])\s+", paras[0])
            mid = max(1, len(sents) // 2)
            paras = [" ".join(sents[:mid]), " ".join(sents[mid:])]
        paras = paras[:4]
        wp_url = "https://en.wikipedia.org/wiki/" + wp.replace(" ", "_")
        story_parts = [_p(_esc(x)) for x in paras]
        # a photograph between story paragraphs, so the pictures sit in the narrative
        story = ('<figure class="bio-fig" data-gal-slot hidden></figure>'.join(story_parts)
                 if has_gallery and len(story_parts) > 1 else "".join(story_parts))
        sections.append((_pick(["The story", "How it came about", "Where it came from", "The background"], seed, 3), story))

    # ---------------------------------------------------------- 3. under the skin ----
    eng_bits = []
    if engine:
        eng_bits.append(_pick([f"The engine is {_esc(e_head)}", f"Power comes from {_esc(e_head)}",
                               f"Under the skin sits {_esc(e_head)}"], seed, 4))
    if power:
        eng_bits.append(_pick([f"it is rated at {_esc(p_head)}", f"the output is {_esc(p_head)}",
                               f"{_esc(p_head)} is the published figure"], seed, 5))
    if engine and " / " in engine and e_head != engine:
        eng_bits.append("other versions carried different engines, listed in the specification table below")
    pn, wn = _num(power), _num(weight)
    ratio = None
    if pn and wn and 300 < wn < 4000 and 5 < pn < 2500:
        ratio = pn / (wn / 1000)
    if eng_bits:
        text = "; ".join(eng_bits) + "."
        if weight:
            text += " " + _pick([
                f"It weighs {_esc(weight)}.",
                f"Kerb weight is {_esc(weight)}.",
                f"On the scales it comes to {_esc(weight)}.",
            ], seed, 6)
        if ratio:
            if ratio >= 400:
                feel = "hypercar territory, where the limiting factor is the tyre, not the engine"
            elif ratio >= 250:
                feel = "genuine supercar pace"
            elif ratio >= 150:
                feel = "quick by any era's standard, the kind of figure a hot hatch or a sports saloon posts"
            elif ratio >= 90:
                feel = "brisk everyday performance"
            elif ratio >= 50:
                feel = "unhurried — enough for the job, not for the bragging"
            else:
                feel = "leisurely, which for a car of its age and purpose is the point"
            text += " " + _pick([
                f"That is roughly {ratio:.0f} horsepower per tonne: {feel}.",
                f"Work it out per tonne and you get about {ratio:.0f} horsepower — {feel}.",
                f"Power-to-weight lands near {ratio:.0f} horsepower per tonne, which is {feel}.",
            ], seed, 7)
        if transmission:
            text += " " + _pick([
                f"The gearbox is a {_esc(transmission)}.",
                f"Drive goes through a {_esc(transmission)}.",
                f"It shifts through a {_esc(transmission)}.",
            ], seed, 8)
        if lw:
            text += f" The layout matters: {lw}."
        if wheelbase:
            text += f" The wheelbase is {_esc(wheelbase)}."
        text += " These are manufacturer figures carried by Wikipedia and Wikidata, not road-test measurements."
        sections.append((_pick(["Under the skin", "The engineering", "What is underneath", "The hardware"], seed, 9), _p(text)))
    elif body or layout:
        text = f"The record carries the shape — a {_esc(body)}" if body else "The record carries the layout"
        if lw:
            text += f" — and the layout: {lw}"
        text += ". The engine, output and weight have not yet reached the open record, and MotorJury does not guess at them."
        sections.append(("Under the skin", _p(text)))

    # ----------------------------------------------------------- 4. where it sits ----
    lin = []
    if predecessor:
        lin.append(_pick([f"it replaced the {_esc(predecessor)}", f"it took over from the {_esc(predecessor)}",
                          f"the {_esc(predecessor)} came before it"], seed, 10))
    if successor:
        lin.append(_pick([f"the {_esc(successor)} followed it", f"it handed the line to the {_esc(successor)}",
                          f"its successor was the {_esc(successor)}"], seed, 11))
    if assembly:
        lin.append(_pick([f"assembly was at {_esc(assembly)}", f"it was built at {_esc(assembly)}",
                          f"the factory was {_esc(assembly)}"], seed, 12))
    place = ""
    if lin:
        place = _pick([
            f"In the {_esc(b)} line-up the {_esc(name)} has a clear place: ",
            f"Its family tree is legible: ",
            f"Where it sits in {_esc(b)}'s history is not in doubt: ",
        ], seed, 13) + "; ".join(lin) + "."
    if riv:
        rivals = ", ".join(f"the {_esc(full_name(b2, m2))}" for b2, m2, _, _, _ in riv[:3])
        place += " " + _pick([
            f"On a showroom list of its day it stood against {rivals}.",
            f"The cars a buyer would have weighed it against include {rivals}.",
            f"Its contemporaries in the catalogue — {rivals} — show what else the money bought that year.",
        ], seed, 14)
    if sib and len(sib) >= 2:
        place += " " + _pick([
            f"Nearby in the {_esc(b)} catalogue sit the {_esc(sib[0]['n'])} and the {_esc(sib[1]['n'])}.",
            f"Its {_esc(b)} stablemates include the {_esc(sib[0]['n'])} and the {_esc(sib[1]['n'])}.",
        ], seed, 15)
    if place.strip():
        sections.append((_pick(["Where it sits", "Its place in the line", "Family and rivals", "In context"], seed, 16), _p(place.strip())))

    # ---------------------------------------------------------- 5. owning one today ----
    own_text = ""
    if own and own.get("price"):
        p0, p1 = own["price"]
        own_text = _pick([
            f"On the used market today a {_esc(name)} typically changes hands for ${p0:,}–${p1:,}",
            f"Buying one now means ${p0:,}–${p1:,} for a typical example",
            f"The money question first: ${p0:,}–${p1:,} is the typical asking range today",
        ], seed, 17)
        if own.get("running"):
            r0, r1 = own["running"]
            own_text += f", and running it — fuel and maintenance at its age — costs about ${r0:,}–${r1:,} a year"
        own_text += ". "
        if own.get("insurance"):
            i0, i1 = own["insurance"]
            own_text += f"Insurance sits around ${i0:,}–${i1:,} a year. "
        own_text += (f'The figures are class-level estimates from the federal record, with the formula on the '
                     f'<a href="/methodology/#prices">methodology page</a>; the model-year pages carry '
                     f'complaints, recalls and repair costs year by year.')
    elif msrp or fe:
        bits = []
        if msrp:
            bits.append(f"the list price when new was {_esc(msrp)}")
        if fe:
            t = f"EPA combined economy is {fe[0]:g} mpg"
            if fe[1]:
                t += f", about ${int(fe[1]):,} a year in fuel at the EPA's assumptions"
            bits.append(t)
        joined = "; ".join(bits)
        own_text = joined[0].upper() + joined[1:] + ". Condition, mileage and specification move any single car a long way from a headline figure."
    elif start and start < 1990:
        own_text = _pick([
            f"There is no federal ownership record for the {_esc(name)} — it predates the complaint database or was never sold in the United States — so MotorJury publishes no running-cost figure for it. For a car of this age the price is set by the collector market and the condition of the individual example, not by a formula.",
            f"MotorJury scores cars on the United States complaint and recall record, and the {_esc(name)} has none: too old, too rare, or never sold there. Its value today is a collector's question, decided by provenance and condition rather than by a class average.",
        ], seed, 18)
    if own_text:
        sections.append((_pick(["Owning one today", "What it costs now", "The money"], seed, 19), _p(own_text)))

    # ------------------------------------------------------------ thin record note ----
    if facts < 2:
        sections.append(("The record", _p(
            f"The open record for the {_esc(name)} carries no verified engine, output, weight or price yet. "
            "MotorJury does not fill gaps with guesses; this entry gives the model a home in the catalogue and "
            "grows as sourced specifications and photographs arrive. Corrections: corrections@motorjury.com.")))

    # ---------------------------------------------------------------- assemble ----
    slot = '<figure class="bio-fig" data-gal-slot hidden></figure>'
    if AD_SLOT_IN_ARTICLE:
        ad = (f'<ins class="adsbygoogle bio-ad" style="display:block;text-align:center" data-ad-layout="in-article" '
              f'data-ad-format="fluid" data-ad-client="{AD_CLIENT}" data-ad-slot="{AD_SLOT_IN_ARTICLE}"></ins>'
              '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>')
    else:
        ad = '<div class="bio-ad" data-ad-anchor aria-hidden="true"></div>'
    parts, slots_used, text_all = [], 0, []
    for i, (title, html_) in enumerate(sections):
        heading = f"<h2>{title}</h2>" if title else ""
        parts.append(f'<section class="card bio-card">{heading}{html_}</section>')
        text_all.append(html_)
        if has_gallery and slots_used < 6 and i < len(sections) - 1:
            parts.append(slot)
            slots_used += 1
        if i == 0 or (i == 2 and len(sections) > 4):
            parts.append(ad)
    return "".join(parts), _wc(" ".join(text_all)), facts
