#!/usr/bin/env python3
"""build_models.py — one page per car model: /library/{brand}/{model}/
Every photograph on the site links HERE (never to an image file, never off-site).
The model page carries: big photo, brand, first year, sibling models, a link to the
ownership-cost data when we have it, and JSON-LD.

File-count discipline: Cloudflare Workers static assets cap is 20,000 files. We generate
model pages for photographed models first (most valuable), then unphotographed ones,
stopping at MAX_MODEL_PAGES. Anything beyond that still appears on its brand page.
"""
import json, re, sys, html
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import LANGS, RTL, t
from build_library import slug, norm_brand, BRAND_ALIAS, commons_thumb

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = "https://carverdict.example"
BRAND = "CarVerdict"
MAX_MODEL_PAGES = 3400          # keeps total site files under the 20k asset cap


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
<a class="logo" href="/">Car<em>Verdict</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="Search any car ever made…" autocomplete="off" aria-label="search" data-none="No matches"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/cars/">Browse</a><a href="/library/">Library</a><a href="/play/">Play</a><a href="/calculators/">Calculators</a></nav>
</div></header>
{body}
<footer><div class="wrap"><p>Catalogue: <a href="https://www.wikidata.org" rel="noopener">Wikidata</a> (CC0) ·
Photography: <a href="https://commons.wikimedia.org" rel="noopener">Wikimedia Commons</a> ·
<a href="/methodology/">Methodology</a></p></div></footer>
<script src="/assets/site.js" defer></script>
<script src="/assets/lightbox.js" defer></script></body></html>"""


def main():
    data = json.load(open(ROOT / "data" / "car_library.json"))
    known = {}
    for x in data:
        m = (x.get("m") or "").strip()
        if m:
            k = BRAND_ALIAS.get(m, m)
            known[k.lower()] = k

    brands = defaultdict(list)
    for x in data:
        name = x["n"].strip()
        if name.startswith("Q") and name[1:].isdigit():
            continue
        b = norm_brand(x["m"])
        if b == "Independent & coachbuilders":
            low = name.lower()
            for n_words in (3, 2, 1):
                if " ".join(low.split()[:n_words]) in known:
                    b = known[" ".join(low.split()[:n_words])]
                    break
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

    (ROOT / "data" / "model_index.json").write_text(
        json.dumps(index, separators=(",", ":"), ensure_ascii=False))
    if "--plan" in sys.argv:
        print(f"PLAN OK: {len(selected)} model pages planned across {len(index)} brands")
        return

    # ---- pass 2: render ----
    for b, m, bs, ms in selected:
        url = f"/library/{bs}/{ms}/"
        sib = [s for s in brands[b]
               if s["n"] != m["n"] and s["n"] in index.get(bs, {})][:8]
        sib_html = "".join(
            f'<a href="/library/{bs}/{index[bs][s["n"]]}/">{esc(s["n"])}'
            + (f'<small>{s["y"]}</small>' if s["y"] else "<small>&nbsp;</small>") + "</a>"
            for s in sib) or '<p class="muted">No other catalogued models yet.</p>'
        made += 1

        if m["p"]:
            fn = m["p"].replace(" ", "_")
            shot = (f'<figure class="model-shot"><a href="#" data-lb data-credit="Photo: Wikimedia Commons &middot; CC">'
                    f'<img src="{commons_thumb(m["p"], 1100)}" alt="{esc(m["n"])}" fetchpriority="high"></a>'
                    f'<figcaption>Photo: Wikimedia Commons &middot; click to enlarge</figcaption></figure>')
        else:
            shot = ('<figure class="model-shot noimg"><div class="ph noimg">'
                    '<svg viewBox="0 0 64 28"><path d="M6 22c2-6 8-9 14-9h20c6 0 12 3 14 9" fill="none" '
                    'stroke="currentColor" stroke-width="2"/><circle cx="18" cy="22" r="4" fill="currentColor"/>'
                    '<circle cx="46" cy="22" r="4" fill="currentColor"/></svg></div>'
                    '<figcaption>No free photograph catalogued yet</figcaption></figure>')

        facts = f'<div class="fact"><span>Marque</span><b><a href="/library/{bs}/">{esc(b)}</a></b></div>'
        if m["y"]:
            facts += f'<div class="fact"><span>Introduced</span><b>{esc(m["y"])}</b></div>'
        facts += ('<div class="fact"><span>Catalogue ID</span><b>'
                  f'{esc(m["q"])}</b></div>')

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
<div class="card"><h2>What we can tell you about running one</h2>
<p>CarVerdict computes ownership verdicts from NHTSA complaint and recall records plus EPA economy
data, re-priced for your country. Model-year verdicts are published as the data is ingested —
<a href="/cars/">browse the verdicts live today</a>, or open the
<a href="/calculators/">true-cost calculator</a> to price any year yourself.</p></div>
<div class="card"><h2>More from {esc(b)}</h2><div class="rel-grid">{sib_html}</div></div>
</div>"""

        jsonld = json.dumps({"@context": "https://schema.org", "@type": "Vehicle", "name": m["n"],
                             "brand": {"@type": "Brand", "name": b},
                             "url": ORIGIN + url}, separators=(",", ":"))
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
