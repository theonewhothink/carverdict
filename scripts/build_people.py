#!/usr/bin/env python3
"""build_people.py — "The Legends": the people who made the car what it is.

Curated, not scraped. Wikidata lists 82,887 engineers and 19,444 designers; a machine
ranking of those produces noise. This list is chosen by significance, then each entry is
resolved against Wikidata for the photograph and dates, and against Wikipedia for the
biography paragraph (CC BY-SA — credited and linked on every page, as the licence requires).

Network failures degrade gracefully: a person who cannot be resolved is skipped, and if the
whole harvest fails the section is simply not built rather than the build breaking.
"""
import html, json, re, sys, time, unicodedata, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
CACHE = ROOT / "data" / "people.json"
import os
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")
BRAND = "MotorJury"
UA = "MotorJury/1.0 (https://motorjury.com) python-urllib"

# ---------------------------------------------------------------- the list
GROUPS = [
    ("The founders", "The people who turned an experiment into an industry.", [
        "Karl Benz", "Bertha Benz", "Gottlieb Daimler", "Henry Ford", "Ransom E. Olds",
        "André Citroën", "Louis Renault", "Ettore Bugatti", "Enzo Ferrari",
        "Ferruccio Lamborghini", "Ferdinand Porsche", "Giovanni Agnelli", "Walter Chrysler",
        "William C. Durant", "Kiichiro Toyoda", "Soichiro Honda", "Chung Ju-yung",
        "Armand Peugeot", "Vincenzo Lancia", "Herbert Austin",
    ]),
    ("The engineers", "The ones who solved the problem nobody else could.", [
        "Rudolf Diesel", "Nikolaus Otto", "Alec Issigonis", "Colin Chapman", "Gordon Murray",
        "Zora Arkus-Duntov", "Dante Giacosa", "Hans Mezger", "Keith Duckworth",
        "Mauro Forghieri", "Ferdinand Piëch", "Adrian Newey", "Ross Brawn", "John Cooper",
        "Harry Miller", "Alex Moulton", "Felix Wankel", "Charles Kettering",
    ]),
    ("The designers", "Shape is the first argument a car makes.", [
        "Giorgetto Giugiaro", "Marcello Gandini", "Battista Farina", "Nuccio Bertone",
        "Harley Earl", "Bill Mitchell", "Sergio Pininfarina", "Walter de Silva",
        "Ian Callum", "Peter Schreyer", "Franco Scaglione", "Bruno Sacco",
        "Flaminio Bertoni", "Patrick le Quément", "Chris Bangle",
    ]),
    ("The drivers", "Champions, and the ones who changed how the job is done.", [
        "Juan Manuel Fangio", "Ayrton Senna", "Michael Schumacher", "Lewis Hamilton",
        "Jim Clark", "Niki Lauda", "Alain Prost", "Jackie Stewart", "Stirling Moss",
        "Alberto Ascari", "Jack Brabham", "Graham Hill", "Gilles Villeneuve",
        "Nelson Piquet", "Emerson Fittipaldi", "Nigel Mansell", "Mika Häkkinen",
        "Sebastian Vettel", "Fernando Alonso", "Max Verstappen", "Sébastien Loeb",
        "Colin McRae", "Walter Röhrl", "Michèle Mouton", "Tom Kristensen", "Jacky Ickx",
        "Carroll Shelby", "Ken Miles", "Denise McCluggage",
    ]),
    ("The industrialists", "Capital, scale and the decisions behind them.", [
        "Alfred P. Sloan", "Lee Iacocca", "Eiji Toyoda", "Sergio Marchionne",
        "Carlos Ghosn", "Elon Musk", "Wang Chuanfu", "Mary Barra", "Robert Bosch",
        "Mate Rimac", "JB Straubel", "Bernie Ecclestone", "Frank Williams", "Ron Dennis",
        "Jean Todt", "Roger Penske",
    ]),
]

WD_API = "https://www.wikidata.org/w/api.php"
WP_SUM = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def esc(s):
    return html.escape(str(s), quote=True)


def slug(s):
    # fold accents first: "Ferdinand Piëch" -> ferdinand-piech. A URL containing raw
    # non-ASCII survives locally but invites percent-encoding mismatches on a CDN.
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:60] or "x"


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def resolve(name):
    """Wikipedia first: its summary endpoint gives title, extract, thumbnail and the
    Wikidata id in one request, and its title matching is far better than a raw search."""
    try:
        j = _get(WP_SUM + urllib.parse.quote(name.replace(" ", "_")))
    except Exception:
        return None
    if j.get("type", "").endswith("not_found"):
        return None
    extract = (j.get("extract") or "").strip()
    if not extract:
        return None
    return {
        "name": j.get("title") or name,
        "desc": (j.get("description") or "").strip(),
        "extract": extract,
        "img": ((j.get("thumbnail") or {}).get("source") or "").replace("/thumb/", "/thumb/"),
        "img_big": ((j.get("originalimage") or {}).get("source") or ""),
        "wp": ((j.get("content_urls") or {}).get("desktop") or {}).get("page", ""),
        "qid": ((j.get("wikibase_item")) or ""),
    }


def dates(qid):
    if not qid:
        return ""
    try:
        j = _get(f"{WD_API}?action=wbgetentities&format=json&props=claims&ids={qid}")
        c = j["entities"][qid].get("claims", {})
    except Exception:
        return ""

    def yr(p):
        try:
            return c[p][0]["mainsnak"]["datavalue"]["value"]["time"][1:5]
        except Exception:
            return ""
    b, d = yr("P569"), yr("P570")
    if b and d:
        return f"{b}–{d}"
    if b:
        return f"b. {b}"
    return ""


def card(p, group):
    img = p.get("img") or p.get("img_big")
    media = (f'<span class="pp-ph"><img loading="lazy" src="{esc(img)}" alt="{esc(p["name"])}"></span>'
             if img else '<span class="pp-ph pp-noimg"></span>')
    meta = " · ".join(x for x in (p.get("years"), p.get("desc")) if x)
    return (f'<a class="pp-card" href="/legends/{slug(p["name"])}/">{media}'
            f'<b>{esc(p["name"])}</b><small>{esc(meta[:70])}</small></a>')


def person_page(p, group, shell):
    years = f' · {p["years"]}' if p.get("years") else ""
    img = p.get("img_big") or p.get("img")
    shot = (f'<figure class="model-shot"><img src="{esc(img)}" alt="{esc(p["name"])}"></figure>'
            if img else "")
    body = f"""<div class="model-hero"><div class="wrap">
<nav class="crumbs"><a href="/legends/">The Legends</a> › {esc(p["name"])}</nav>
<div class="model-grid">
{shot}
<div class="model-side">
<h1>{esc(p["name"])}</h1>
<p class="sub">{esc(p.get("desc") or group)}{esc(years)}</p>
<div class="hh-cta"><a class="btn" href="/library/">Browse the cars</a>
<a class="btn ghost" href="/legends/">All legends</a></div>
</div></div></div></div>
<div class="wrap" style="display:grid;gap:22px;padding:26px 0">
<div class="card"><h2>Who they were</h2><p>{esc(p["extract"])}</p>
<p class="lib-note">Biography from <a href="{esc(p.get("wp") or "https://en.wikipedia.org")}"
rel="noopener">Wikipedia</a>, used under CC BY-SA. Photograph via Wikimedia Commons.</p></div>
<div class="card"><h2>Keep going</h2><div class="rel-grid">
<a href="/legends/">The Legends<small>every name in this collection</small></a>
<a href="/library/">The Car Library<small>every model ever catalogued</small></a>
<a href="/superlatives/">The extremes<small>fastest · rarest · most expensive</small></a>
</div></div></div>"""
    return shell(f"{p['name']} — {group} | {BRAND}",
                 (p.get("desc") or group) + f". {p['extract'][:130]}",
                 f"{ORIGIN}/legends/{slug(p['name'])}/", body)


def main():
    # --harvest-only runs before gen_site.py (which wipes site/) purely to fill the cache,
    # so the home page knows whether /legends/ will exist. The page-writing pass runs after.
    harvest_only = "--harvest-only" in sys.argv
    if not harvest_only:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from build_models import shell        # reuse the model-page chrome

    people, seen = [], set()
    if "--from-cache" in sys.argv and CACHE.exists():
        people = json.loads(CACHE.read_text())
    else:
        for group, blurb, names in GROUPS:
            for n in names:
                p = resolve(n)
                time.sleep(0.15)
                if not p or p["name"] in seen:
                    continue
                seen.add(p["name"])
                p["years"] = dates(p.get("qid"))
                p["group"] = group
                people.append(p)
        # a bad network run must not wipe a good roster
        if len(people) < 20 and CACHE.exists():
            cached = json.loads(CACHE.read_text())
            if len(cached) > len(people):
                print(f"PEOPLE: only {len(people)} resolved, keeping cached {len(cached)}")
                people = cached
    if not people:
        print("PEOPLE SKIPPED: nothing resolved; section not built")
        return 0

    CACHE.write_text(json.dumps(people, ensure_ascii=False, separators=(",", ":")))
    if harvest_only:
        print(f"LEGENDS CACHED: {len(people)} people (pages written after gen_site)")
        return 0

    # per-person pages
    for p in people:
        out = SITE / "legends" / slug(p["name"]) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(person_page(p, p["group"], shell))

    # index
    blocks = ""
    for group, blurb, _ in GROUPS:
        rows = [p for p in people if p["group"] == group]
        if not rows:
            continue
        blocks += (f'<h2 class="sec">{esc(group)}</h2><p class="muted" style="margin:-6px 0 14px">'
                   f'{esc(blurb)}</p><div class="pp-grid">'
                   + "".join(card(p, group) for p in rows) + "</div>")
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>The Legends</h1><p class="sub">The {len(people)} people who built, drew, drove and financed
the car — founders, engineers, designers, champions and industrialists.</p></div></div>
<div class="wrap">{blocks}
<p class="lib-note">Biographies from Wikipedia (CC BY-SA), photographs via Wikimedia Commons.
Each name links to the full article.</p></div>"""
    (SITE / "legends").mkdir(parents=True, exist_ok=True)
    (SITE / "legends" / "index.html").write_text(
        shell(f"The Legends — The Greatest People in Motoring | {BRAND}",
              "Founders, engineers, designers, racing drivers and industrialists who made the "
              "motor car what it is.", f"{ORIGIN}/legends/", body))

    # a compact feed the home page renders from
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "legends.json").write_text(json.dumps(
        [{"n": p["name"], "s": slug(p["name"]), "i": p.get("img") or "", "d": p.get("desc", ""),
          "y": p.get("years", ""), "g": p["group"]} for p in people],
        ensure_ascii=False, separators=(",", ":")))
    print(f"LEGENDS OK: {len(people)} people across {len(GROUPS)} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
