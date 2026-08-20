#!/usr/bin/env python3
"""build_models.py — one page per car model: /library/{brand}/{model}/
Every photograph on the site links HERE (never to an image file, never off-site).
The model page carries: big photo, brand, first year, sibling models, a link to the
ownership-cost data when we have it, and JSON-LD.

File-count discipline: Cloudflare Workers static assets cap is 20,000 files. We generate
model pages for photographed models first (most valuable), then unphotographed ones,
stopping at MAX_MODEL_PAGES. Anything beyond that still appears on its brand page.
"""
import json, os, re, sys, html
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import LANGS, RTL, t
from build_library import (slug, norm_brand, BRAND_ALIAS, commons_thumb,
                           is_qid, resolve_qid_brands, brand_of, real_engine)

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")
BRAND = "MotorJury"
MAX_MODEL_PAGES = 3400          # keeps total site files under the 20k asset cap


def _load_specs():
    """Per-model technical facts from harvest_specs.py. Optional: if the harvest has not
    run, pages render exactly as before instead of failing."""
    p = ROOT / "data" / "car_specs.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


SPECS = _load_specs()
FLAT = {}


def _load_wiki():
    """Wikipedia infobox specifications — engine, power, production, weight, transmission."""
    p = ROOT / "data" / "wiki_specs.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


WIKI = _load_wiki()


def _load_people():
    """Legends roster, so a designer's name can link to their page instead of sitting dead."""
    p = ROOT / "data" / "people.json"
    try:
        rows = json.loads(p.read_text()) if p.exists() else []
    except Exception:
        return {}
    import unicodedata as _u

    def sl(s):
        s = _u.normalize("NFKD", str(s))
        s = "".join(c for c in s if not _u.combining(c))
        s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
        return re.sub(r"[\s_]+", "-", s)[:60] or "x"

    return {r["name"].lower(): "/legends/" + sl(r["name"]) + "/" for r in rows}


PEOPLE = _load_people()


def _load_fuel():
    """EPA fuel economy per (make, model) from the ownership database, so library pages
    can answer 'what does it drink?' where the data exists."""
    import sqlite3
    db = ROOT / "data" / "cars.sqlite"
    out = {}
    if not db.exists():
        return out
    try:
        con = sqlite3.connect(db)
        for mk, mo, comb, cost in con.execute(
            """SELECT mk.name, mo.name, MAX(f.mpg_comb), MAX(f.annual_fuel_cost)
               FROM fuel f JOIN model_years my ON my.id=f.my_id
               JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
               GROUP BY mk.name, mo.name"""):
            if comb:
                out[(mk.lower(), mo.lower())] = (comb, cost)
        con.close()
    except Exception:
        pass
    return out


FUEL = _load_fuel()


def _length(v):
    """Render Wikidata P2043 with the unit it was actually recorded in.

    `wdt:P2043` returns a bare number: the unit lives on the statement node and is
    dropped, so every model page printed "4805 m" for a 4,805 mm Camry - a Camry
    the length of fifty buses. Car items record length in millimetres, centimetres
    or metres, and for a road vehicle the three ranges cannot overlap (a 12 m bus
    is 1,200 cm is 12,000 mm), so the magnitude identifies the unit unambiguously.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    if f >= 1000:                      # millimetres
        return f"{f:,.0f} mm"
    if f >= 100:                       # centimetres
        return f"{f:,.0f} cm"
    return f"{f:g} m"                  # metres


def _msrp_num(v):
    """'US$139,900' / '£113,000 (2021)' -> a USD-ish number for the depreciation model,
    or None when the currency is not dollars (an honest model beats a wrong conversion)."""
    m = re.search(r"(?:US)?\$\s?([\d,]{4,})", v or "")
    return int(m.group(1).replace(",", "")) if m else None


def _load_wiki():
    """Wikipedia infobox specifications — engine, power, production, weight, transmission.
    Richer than Wikidata's structured claims, which is why it takes precedence below."""
    p = ROOT / "data" / "wiki_specs.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


WIKI = _load_wiki()


def esc(s):
    return html.escape(str(s), quote=True)


def shell(title, desc, canon, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#FFFFFF"><title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<link rel="stylesheet" href="/assets/site.css"></head><body>
<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="/">Motor<em>Jury</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="Search any car ever made…" autocomplete="off" aria-label="search" data-none="No matches"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/cars/">Browse</a><a href="/library/">Library</a><a href="/events/">Events</a><a href="/play/">Play</a><a href="/calculators/">Calculators</a></nav>
</div></header>
{body}
<footer><div class="wrap"><p>Catalogue: <a href="https://www.wikidata.org" rel="noopener">Wikidata</a> (CC0) ·
Photography: <a href="https://commons.wikimedia.org" rel="noopener">Wikimedia Commons</a> ·
<a href="/methodology/">Methodology</a></p></div></footer>
<script src="/assets/site.js" defer></script>
<script src="/assets/lightbox.js" defer></script>
<script src="/assets/gallery.js" defer></script>
<script src="/assets/rate.js" defer></script></body></html>"""


def main():
    data = json.load(open(ROOT / "data" / "car_library.json"))
    known = {}
    for x in data:
        m = (x.get("m") or "").strip()
        if m and not is_qid(m):
            k = BRAND_ALIAS.get(m, m)
            known[k.lower()] = k

    resolve_qid_brands(data, known)
    brands = defaultdict(list)
    for x in data:
        name = x["n"].strip()
        if name.startswith("Q") and name[1:].isdigit():
            continue
        b = brand_of(name, x["m"], known)
        brands[b].append({"n": name, "p": x["p"], "y": x["y"], "q": x["q"]})

    # de-duplicate model slugs inside a brand
    made, index = 0, {}
    ordered = []
    for b, models in brands.items():
        for m in models:
            ordered.append((b, m))
    # Allocation for the single-upload deploy budget: mainstream marques complete first
    # (these are what visitors click), then everything else by catalogue size, catch-all last.
    # The FULL 15k-model build is produced when MAX_MODEL_PAGES is raised in CI.
    PRIORITY = ["Toyota", "Ford", "Volkswagen", "BMW", "Mercedes-Benz", "Honda", "Nissan",
                "Mazda", "Audi AG", "Audi", "Hyundai", "Kia", "Chevrolet", "GM (General Motors)",
                "Subaru", "Mitsubishi Motors", "Volvo Cars", "Volvo", "Porsche", "Ferrari",
                "Lamborghini", "Jaguar Cars", "Land Rover", "Tesla, Inc.", "Tesla", "Peugeot",
                "Renault", "Citroën", "Fiat", "Alfa Romeo", "SEAT", "Škoda Auto", "Opel",
                "Suzuki", "Lexus", "Jeep", "Dodge", "Chrysler", "Cadillac", "Buick", "GMC",
                "Mini", "Bentley Motors", "Rolls-Royce Motor Cars", "Aston Martin", "Maserati",
                "Bugatti", "Lotus Cars", "Genesis Motor", "BYD Auto", "Great Wall Motors",
                "Chery", "Geely", "SAIC Motor", "Dacia", "Lancia", "Saab", "Daihatsu", "Isuzu",
                "Infiniti", "Acura", "Lincoln Motor Company", "Rover Company", "Datsun"]
    # nameplates a visitor is most likely to click — always guaranteed a page
    FEATURED = {n.lower() for n in [
        "Ford Mustang","Ford F-Series","Ford Fiesta","Ford Focus","Ford Escort","Ford Ranger",
        "Ford Model T","Ford Explorer","Ford Bronco","Ford GT","Ford Transit",
        "Toyota Corolla","Toyota Camry","Toyota RAV4","Toyota Hilux","Toyota Prius","Toyota Supra",
        "Toyota Land Cruiser","Toyota Yaris","Toyota Tacoma","Toyota 4Runner","Toyota MR2",
        "Volkswagen Golf","Volkswagen Beetle","Volkswagen Passat","Volkswagen Polo","Volkswagen Transporter",
        "Volkswagen Tiguan","Volkswagen Scirocco","Volkswagen Type 2",
        "BMW 3 Series","BMW 5 Series","BMW 7 Series","BMW X5","BMW M3","BMW i3","BMW Z3",
        "Mercedes-Benz S-Class","Mercedes-Benz E-Class","Mercedes-Benz C-Class","Mercedes-Benz G-Class",
        "Mercedes-Benz SL","Mercedes-Benz 300 SL",
        "Honda Civic","Honda Accord","Honda CR-V","Honda NSX","Honda Jazz","Honda Fit","Honda S2000",
        "Nissan Skyline","Nissan GT-R","Nissan Leaf","Nissan Micra","Nissan Qashqai","Nissan 370Z",
        "Nissan Patrol","Nissan Silvia","Nissan Z",
        "Mazda MX-5","Mazda RX-7","Mazda RX-8","Mazda3","Mazda6","Mazda CX-5",
        "Porsche 911","Porsche 356","Porsche Cayenne","Porsche Boxster","Porsche 944","Porsche Taycan",
        "Ferrari 250 GTO","Ferrari F40","Ferrari Testarossa","Ferrari LaFerrari","Ferrari 488",
        "Lamborghini Countach","Lamborghini Miura","Lamborghini Aventador","Lamborghini Huracán",
        "Tesla Model S","Tesla Model 3","Tesla Model X","Tesla Model Y","Tesla Roadster","Tesla Cybertruck",
        "Jeep Wrangler","Jeep Cherokee","Jeep Grand Cherokee","Jeep Willys MB",
        "Chevrolet Corvette","Chevrolet Camaro","Chevrolet Impala","Chevrolet Silverado","Chevrolet Bel Air",
        "Chevrolet Suburban","Chevrolet Bolt","Chevrolet Malibu",
        "Audi Quattro","Audi A4","Audi A6","Audi TT","Audi R8","Audi Q7",
        "Mini","Mini Cooper","Range Rover","Land Rover Defender","Land Rover Discovery",
        "Jaguar E-Type","Jaguar XJ","Jaguar F-Type",
        "Subaru Impreza","Subaru Legacy","Subaru Outback","Subaru Forester","Subaru BRZ",
        "Volvo 240","Volvo XC90","Volvo P1800","Volvo 850",
        "Fiat 500","Fiat Panda","Fiat Uno","Fiat Punto",
        "Peugeot 205","Peugeot 206","Peugeot 208","Peugeot 504",
        "Renault Clio","Renault 5","Renault Twingo","Renault Espace",
        "Citroën 2CV","Citroën DS","Citroën C3",
        "Alfa Romeo Giulia","Alfa Romeo Spider","Alfa Romeo 156",
        "Hyundai i30","Hyundai Tucson","Hyundai Santa Fe","Hyundai Pony",
        "Kia Sportage","Kia Ceed","Kia Sorento","Kia EV6",
        "Dodge Charger","Dodge Challenger","Dodge Viper","Dodge Ram",
        "Lancia Delta","Lancia Stratos","Bugatti Veyron","Bugatti Chiron","Bugatti Type 57",
        "Aston Martin DB5","Aston Martin Vantage","Bentley Continental GT",
        "Lotus Esprit","Lotus Elise","Maserati Quattroporte","Lexus LS","Lexus IS","Lexus LFA",
        "Mitsubishi Lancer","Mitsubishi Pajero","Suzuki Jimny","Suzuki Swift",
        "Škoda Octavia","Škoda Fabia","SEAT Ibiza","SEAT León","Opel Astra","Opel Corsa",
        "Saab 900","Saab 9-3","Datsun 240Z","Acura NSX","Infiniti Q50","Cadillac Escalade",
        "Cadillac Eldorado","Buick Riviera","Lincoln Continental","Chrysler 300","Pontiac Firebird",
        "Pontiac GTO","Plymouth Barracuda","AMC Gremlin","DeLorean DMC-12","Hummer H1"]}
    prio = {b: i for i, b in enumerate(PRIORITY)}
    size = {b: len(v) for b, v in brands.items()}
    GENERIC = "Independent & coachbuilders"
    def rank(b):
        if b in prio:
            return (0, prio[b], b)
        return (2 if b == GENERIC else 1, -size[b], b)
    # Inside a marque, prefer the canonical nameplates: photographed, then shortest name
    # ("Ford Mustang" before "Ford Mustang SSP Highway Patrol"), then alphabetical.
    ordered.sort(key=lambda r: (0 if r[1]["n"].lower() in FEATURED else 1,
                                rank(r[0]), 0 if r[1]["p"] else 1, len(r[1]["n"]), r[1]["n"]))
    # spread the deploy budget: at most PER_BRAND pages per marque so every famous name is
    # covered (brand pages still list 100% of models either way)
    PER_BRAND = 95
    seen_count = defaultdict(int)
    first_wave, later = [], []
    for item in ordered:
        b = item[0]
        if seen_count[b] < PER_BRAND:
            seen_count[b] += 1
            first_wave.append(item)
        else:
            later.append(item)
    ordered = first_wave + later

    # ---- pass 1: choose exactly which models get a page (so every link we emit resolves) ----
    used, selected = defaultdict(set), []
    for b, m in ordered:
        if len(selected) >= MAX_MODEL_PAGES:
            break
        bs, ms = slug(b), slug(m["n"])
        if ms in used[bs]:
            continue
        used[bs].add(ms)
        selected.append((b, m, bs, ms))
        index.setdefault(bs, {})[m["n"]] = ms

    # name -> model-page URL, so predecessor/successor/designer can be real links
    global FLAT
    FLAT = {name: f"/library/{bs}/{ms}/" for bs, d in index.items() for name, ms in d.items()}

    (ROOT / "data" / "model_index.json").write_text(
        json.dumps(index, separators=(",", ":"), ensure_ascii=False))
    if "--plan" in sys.argv:
        print(f"PLAN OK: {len(selected)} model pages planned across {len(index)} brands")
        return

    # ---- sideways mesh: cross-brand rivals of the same era ----
    # A model page used to link only up (its brand) and down (its siblings). The mesh
    # adds sideways links: contemporaries from other marques, introduced within three
    # years. Famous nameplates and photographed cars rank first; a CRC tiebreaker
    # spreads the picks so the same six cars do not appear on every page; at most two
    # per rival marque. Candidates come from the selected set, so every link resolves.
    import zlib

    def _era_year(m2):
        """Introduction year for the era mesh: catalogue year first, then the harvested
        Wikipedia production span, then Wikidata facts — whichever exists."""
        ym = re.search(r"(18|19|20)\d\d", str(m2["y"] or ""))
        if not ym:
            wk2 = WIKI.get(m2["q"]) or {}
            sp2 = SPECS.get(m2["q"]) or {}
            ym = re.search(r"(18|19|20)\d\d",
                           str(wk2.get("production") or sp2.get("started") or ""))
        return int(ym.group(0)) if ym else None

    year_buckets = defaultdict(list)
    for b2, m2, bs2, ms2 in selected:
        y2 = _era_year(m2)
        if y2:
            year_buckets[y2].append((b2, m2, bs2, ms2, y2))

    def rivals_of(b, m, ms):
        y0 = _era_year(m)
        if not y0:
            return []
        cand = []
        for y in range(y0 - 3, y0 + 4):
            for b2, m2, bs2, ms2, y2 in year_buckets.get(y, ()):
                if b2 == b:
                    continue
                cand.append((0 if m2["n"].lower() in FEATURED else 1,
                             0 if m2["p"] else 1, abs(y2 - y0),
                             zlib.crc32(f"{ms}:{bs2}/{ms2}".encode()) & 0xffff,
                             b2, m2, bs2, ms2, y2))
        cand.sort(key=lambda c: c[:4])
        out, per = [], defaultdict(int)
        for c in cand:
            b2 = c[4]
            if per[b2] >= 2:
                continue
            per[b2] += 1
            out.append(c[4:])
            if len(out) == 6:
                break
        return out

    # ---- pass 2: render ----
    for b, m, bs, ms in selected:
        url = f"/library/{bs}/{ms}/"
        sib = [s for s in brands[b]
               if s["n"] != m["n"] and s["n"] in index.get(bs, {})][:8]
        sib_html = "".join(
            f'<a href="/library/{bs}/{index[bs][s["n"]]}/">{esc(s["n"])}'
            + (f'<small>{s["y"]}</small>' if s["y"] else "<small>&nbsp;</small>") + "</a>"
            for s in sib) or '<p class="muted">No other catalogued models yet.</p>'
        riv = rivals_of(b, m, ms)
        rivals_card = ""
        if riv:
            rivals_html = "".join(
                f'<a href="/library/{bs2}/{ms2}/">{esc(m2["n"])}'
                f'<small>{esc(b2)}{f" · {y2}" if y2 else ""}</small></a>'
                for b2, m2, bs2, ms2, y2 in riv)
            rivals_card = ('<div class="card"><h2>Rivals of its era</h2>'
                           f'<div class="rel-grid">{rivals_html}</div>'
                           '<p class="lib-note">Contemporaries from other marques, '
                           'introduced within three years of this car.</p></div>')
        made += 1

        if m["p"]:
            fn = m["p"].replace(" ", "_")
            # No per-image credit line: it repeated on every photo and said nothing useful.
            # Attribution (photographer + licence) is rendered once, per image, in the
            # credits block under the gallery — which is what the CC licences actually ask for.
            shot = (f'<figure class="model-shot"><a href="#" data-lb data-credit="Wikimedia Commons &middot; CC">'
                    f'<img src="{commons_thumb(m["p"], 1100)}" alt="{esc(m["n"])}" fetchpriority="high"></a></figure>')
        else:
            shot = ('<figure class="model-shot noimg"><div class="ph noimg">'
                    '<svg viewBox="0 0 64 28"><path d="M6 22c2-6 8-9 14-9h20c6 0 12 3 14 9" fill="none" '
                    'stroke="currentColor" stroke-width="2"/><circle cx="18" cy="22" r="4" fill="currentColor"/>'
                    '<circle cx="46" cy="22" r="4" fill="currentColor"/></svg></div>'
                    '<figcaption>No free photograph catalogued yet</figcaption></figure>')

        sp = SPECS.get(m["q"], {})
        wk = WIKI.get(m["q"], {})

        def linked(val):
            """Link a referenced car or person when we actually have a page for it."""
            if not val:
                return val
            u = FLAT.get(val) or PEOPLE.get(val.lower())
            if not u:
                base = re.sub(r"\s*\([^)]*\)$", "", val).strip()
                u = FLAT.get(base) or PEOPLE.get(base.lower())
            return f'<a href="{u}">{esc(val)}</a>' if u else esc(val)
        wk = WIKI.get(m["q"], {})

        # Headline facts sit beside the photo; the full spec table goes below. Rows appear
        # only when the model actually has that fact — no table of dashes.
        facts = f'<div class="fact"><span>Marque</span><b><a href="/library/{bs}/">{esc(b)}</a></b></div>'
        years = wk.get("production") or ""
        if not years:
            years = m["y"] or ""
            if years and sp.get("ended"):
                years = f'{years} – {sp["ended"]}'
        if years:
            facts += f'<div class="fact"><span>Production</span><b>{esc(years)}</b></div>'
        # the number a petrolhead looks for first
        if wk.get("power"):
            facts += f'<div class="fact"><span>Power</span><b>{esc(wk["power"])}</b></div>'
        engine = real_engine(wk.get("engine")) or real_engine(sp.get("engine"))
        if engine:
            facts += f'<div class="fact"><span>Engine</span><b>{esc(engine)}</b></div>'
        if sp.get("built"):
            facts += f'<div class="fact"><span>Units built</span><b>{int(sp["built"]):,}</b></div>'
        # what it cost new, and what age has done to that number since
        # Infobox price first (richer, often carries the year); Wikidata P2284 fills the gaps.
        msrp = wk.get("msrp") or sp.get("msrp")
        if msrp:
            facts += f'<div class="fact"><span>Price when new</span><b>{esc(msrp)}</b></div>'
            usd = _msrp_num(msrp)
            yr = re.search(r"(19|20)\d\d", str(wk.get("production") or m["y"] or ""))
            # A depreciation curve is honest for a Camry and a lie for a collector car.
            # Skip anything older than 15 years or with a race record - those appreciate,
            # and a wrong number is worse than no number.
            if usd and yr and not wk.get("wins"):
                age = max(0, 2026 - int(yr.group(0)))
                if age <= 15:
                    mid = usd * max(0.12, 0.85 ** age)
                    lo, hi = int(mid * 0.8), int(mid * 1.25)
                    facts += (f'<div class="fact"><span>Estimated value today</span>'
                              f'<b>${lo:,}–${hi:,}<small class="est"> depreciation model, not a quote</small></b></div>')
        fe = FUEL.get((b.lower(), m["n"].lower().replace(b.lower(), "").strip()))
        if not fe:
            for (fmk, fmo), v in FUEL.items():
                if fmk in b.lower() and fmo in m["n"].lower():
                    fe = v
                    break
        if fe:
            facts += (f'<div class="fact"><span>Fuel economy (EPA)</span>'
                      f'<b>{fe[0]:g} mpg combined{f" · ${int(fe[1]):,}/yr fuel" if fe[1] else ""}</b></div>')
        if wk.get("wins"):
            rec = wk["wins"] + (f' wins from {wk["races"]} races' if wk.get("races") else " race wins")
            if wk.get("championships"):
                rec += f' · {wk["championships"]} championships'
            facts += f'<div class="fact"><span>Race record</span><b>{esc(rec)}</b></div>'

        spec_rows = []
        if wk.get("transmission"):
            spec_rows.append(("Transmission", wk["transmission"]))
        if wk.get("layout"):
            spec_rows.append(("Layout", wk["layout"]))
        if wk.get("body"):
            spec_rows.append(("Body style", wk["body"]))
        weight = wk.get("weight") or (f'{sp["mass"]:g} kg' if sp.get("mass") else None)
        if weight:
            spec_rows.append(("Kerb weight", weight))
        if sp.get("top_speed"):
            spec_rows.append(("Top speed", f'{sp["top_speed"]:g} km/h'))
        if wk.get("wheelbase"):
            spec_rows.append(("Wheelbase", wk["wheelbase"]))
        length = _length(sp.get("length"))
        if length:
            spec_rows.append(("Length", length))
        assembly = wk.get("assembly") or sp.get("made_in")
        if assembly:
            spec_rows.append(("Assembly", assembly))
        spec_html = "".join(f'<div class="fact"><span>{esc(k)}</span><b>{esc(v)}</b></div>'
                            for k, v in spec_rows)
        # A predecessor, successor or designer names a real thing. If we hold a page for it,
        # it should be a link — a dead-end string here is a wasted journey.
        def linked(val):
            u = FLAT.get(val) or PEOPLE.get((val or "").lower())
            return f'<a href="{u}">{esc(val)}</a>' if u else esc(val)

        for label, val in (("Designer", wk.get("designer") or sp.get("designer")),
                           ("Predecessor", wk.get("predecessor")),
                           ("Successor", wk.get("successor"))):
            if val:
                spec_html += f'<div class="fact"><span>{label}</span><b>{linked(val)}</b></div>'
        # The catalogue id is provenance, not a specification. On a model with no harvested
        # facts it would be the Specifications card's only row - a card that tells the reader
        # nothing and costs a scroll. Show it beside real facts, and drop the card otherwise.
        if spec_html:
            spec_html += f'<div class="fact"><span>Catalogue ID</span><b>{esc(m["q"])}</b></div>'
        src = ('the Wikipedia infobox for this model (CC BY-SA) and the open Wikidata record'
               if wk else 'the open Wikidata record for this model')
        spec_note = (f'<p class="lib-note">Specifications come from {src}, and are shown only where '
                     'a source actually carries them — nothing here is estimated. Figures are '
                     'manufacturer specifications, not measured results.</p>')
        specs_card = (f'<div class="card"><h2>Specifications</h2>'
                      f'<div class="facts spec-table">{spec_html}</div>{spec_note}</div>') if spec_html else ""

        about_card = ""
        if wk.get("about"):
            paras = [p.strip() for p in re.split(r"\n{2,}", wk["about"]) if p.strip()]
            if len(paras) == 1 and len(paras[0]) > 480:
                sents = re.split(r"(?<=\.)\s+", paras[0])
                mid = len(sents) // 2
                paras = [" ".join(sents[:mid]), " ".join(sents[mid:])]
            prose = "".join(f"<p>{esc(p)}</p>" for p in paras[:4])
            wp = wk.get("wp") or m["n"]
            wp_url = "https://en.wikipedia.org/wiki/" + wp.replace(" ", "_")
            about_card = (f'<div class="card about-card"><h2>About the {esc(m["n"])}</h2>{prose}'
                          f'<p class="lib-note">From the Wikipedia article '
                          f'<a href="{esc(wp_url)}" rel="noopener">{esc(wp)}</a>, CC BY-SA.</p></div>')

        rate_card = (f'<div class="card rate-card" data-rate="{esc(m["q"])}" '
                     f'data-rate-name="{esc(m["n"])}"><h2>Rate your love</h2>'
                     f'<div class="stars" data-stars role="radiogroup" aria-label="Rate this car"></div>'
                     f'<p class="lib-note" data-rate-note>Tap a star. Ratings are kept on your device '
                     f'and feed the most-loved list.</p></div>')

        gallery_card = ""
        if sp.get("commons"):
            gallery_card = (f'<div class="card gallery-card" data-commons-cat="{esc(sp["commons"])}">'
                            f'<h2>Photo gallery</h2>'
                            f'<div class="gal-grid" data-gal></div>'
                            f'<p class="lib-note" data-gal-credits></p></div>')

        body = f"""<div class="model-hero"><div class="wrap">
<nav class="crumbs"><a href="/library/">Library</a> › <a href="/library/{bs}/">{esc(b)}</a> › {esc(m["n"])}</nav>
<div class="model-grid">
{shot}
<div class="model-side">
<h1>{esc(m["n"])}</h1>
<p class="sub">{esc(b)}{f' · introduced {esc(m["y"])}' if m["y"] else ''}</p>
<div class="facts">{facts}</div>
<div class="hh-cta"><a class="btn" href="/cars/">Ownership-cost data</a>
<a class="btn ghost" href="/library/{bs}/">All {esc(b)} models</a></div>
</div></div></div></div>
<div class="wrap" style="display:grid;gap:22px;padding:26px 0">
{about_card}
{specs_card}
{rate_card}
{gallery_card}
<div class="card"><h2>What it costs to run</h2>
<p>Ownership verdicts are computed from NHTSA complaint and recall records plus EPA economy data,
re-priced for your country. Verdicts are published per model year as the data is ingested —
<a href="/cars/">browse them live</a>, or open the
<a href="/calculators/">true-cost calculator</a> to price any year yourself.</p></div>
<div class="card"><h2>More from {esc(b)}</h2><div class="rel-grid">{sib_html}</div></div>
{rivals_card}
</div>"""

        # Vehicle plus the breadcrumb trail the page already shows visually. Google renders the
        # BreadcrumbList as the result's path line instead of a bare URL, so every library model
        # page earns "Library > Brand > Model" in the SERP. A top-level array is valid JSON-LD.
        jsonld = json.dumps([
            {"@context": "https://schema.org", "@type": "Vehicle", "name": m["n"],
             "brand": {"@type": "Brand", "name": b},
             "url": ORIGIN + url},
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Library",
                 "item": ORIGIN + "/library/"},
                {"@type": "ListItem", "position": 2, "name": b,
                 "item": f"{ORIGIN}/library/{bs}/"},
                {"@type": "ListItem", "position": 3, "name": m["n"],
                 "item": ORIGIN + url}]},
        ], separators=(",", ":"))
        page = shell(f"{m['n']} — {b} | {BRAND}",
                     f"{m['n']} by {b}: photograph, catalogue facts and ownership-cost context.",
                     ORIGIN + url, body).replace("</head>",
                     f'<script type="application/ld+json">{jsonld}</script></head>')
        out = SITE / url.lstrip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page)

    (SITE / "assets" / "model-index.json").write_text(
        json.dumps(index, separators=(",", ":"), ensure_ascii=False))
    print(f"MODELS OK: {made} model pages, index covers {len(index)} brands")


if __name__ == "__main__":
    main()
