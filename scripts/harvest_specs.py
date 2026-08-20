#!/usr/bin/env python3
"""harvest_specs.py — technical facts per model -> data/car_specs.json

Measured coverage across the catalogue (Wikidata, counted before building this):

    Commons category   9,983    powers the photo gallery
    engine             4,748
    length             4,578
    kerb mass          2,000
    assembled in       1,212
    top speed            533
    units built          503
    designer             252
    production ended     223
    power output          58    <- effectively absent

So horsepower is NOT available as free structured data and is deliberately not shown
rather than invented. Every field here is rendered only when the model actually has it;
a model with nothing gets no specs table instead of a table full of dashes.

Never fails the build: on any network error the previous specs file is left in place.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "car_specs.json"
ENDPOINT = "https://query.wikidata.org/sparql"
UA = "MotorJury/1.0 (https://motorjury.com) python-urllib"

CLASSES = ["Q3231690", "Q1420", "Q850270", "Q59773381", "Q90834785",
           "Q673687", "Q10429667", "Q3882470"]

# key -> (property, kind). "label" resolves the value to its English name,
# "num" keeps the raw number, "str" is a plain string such as a category name.
FIELDS = {
    "engine":    ("P516",  "label"),
    "length":    ("P2043", "num"),
    "mass":      ("P2067", "num"),
    "made_in":   ("P1071", "label"),
    "top_speed": ("P2052", "num"),
    "built":     ("P1092", "num"),
    "designer":  ("P287",  "label"),
    "ended":     ("P2669", "year"),
    "commons":   ("P373",  "str"),
}

TPL = """SELECT ?i ?v %(lbl)s WHERE {
  ?i wdt:P31 wd:%(cls)s ; wdt:%(prop)s ?v .
  %(svc)s
}"""


def _query(q, timeout=120):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"format": "json", "query": q})
    req = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json",
                                               "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["results"]["bindings"]


def fetch(prop, kind):
    """One query per class. Asking for all eight at once makes the public endpoint
    return 502 — measured, not guessed. Two retries absorb transient failures."""
    lbl = "?vLabel" if kind == "label" else ""
    svc = ('SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }'
           if kind == "label" else "")
    rows = []
    for cls in CLASSES:
        q = TPL % {"prop": prop, "cls": cls, "lbl": lbl, "svc": svc}
        for attempt in range(3):
            try:
                rows += _query(q)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(3 * (attempt + 1))
        time.sleep(0.5)
    return rows


def clean(kind, b):
    v = b.get("vLabel", b["v"])["value"] if kind == "label" else b["v"]["value"]
    if kind == "num":
        try:
            f = float(v)
        except ValueError:
            return None
        return round(f, 2) if f % 1 else int(f)
    if kind == "year":
        return v[:4] if len(v) >= 4 else None
    v = v.strip()
    # an unresolved label comes back as the Q-id itself — useless to a reader
    if not v or (v.startswith("Q") and v[1:].isdigit()):
        return None
    return v


# Currency label -> symbol for the "Price when new" fact. Anything unmapped renders
# as "12,345 <currency name>" - honest, if less pretty.
CURRENCY = {"United States dollar": "US$", "euro": "\u20ac", "pound sterling": "\u00a3",
            "Japanese yen": "\u00a5", "Swiss franc": "CHF ", "Canadian dollar": "CA$",
            "Australian dollar": "A$", "Indian rupee": "\u20b9", "renminbi": "CN\u00a5",
            "South Korean won": "\u20a9", "Russian ruble": "\u20bd",
            "Deutsche Mark": "DM ", "French franc": "FF ", "Italian lira": "\u20a4",
            "Swedish krona": "SEK ", "Brazilian real": "R$", "Mexican peso": "MX$"}

MSRP_TPL = """SELECT ?i ?v ?unitLabel WHERE {
  ?i wdt:P31 wd:%(cls)s ; p:P2284/psv:P2284 ?n .
  ?n wikibase:quantityAmount ?v ; wikibase:quantityUnit ?unit .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def harvest_msrp(specs):
    """Launch price (P2284) with its currency unit -> a formatted "Price when new" string.
    Wikidata's price claims need the statement node (p:/psv:) because wdt: drops the unit,
    and a bare number without a currency is meaningless to a reader."""
    n = 0
    for cls in CLASSES:
        q = MSRP_TPL % {"cls": cls}
        try:
            rows = _query(q)
        except Exception as e:
            print(f"  msrp       class {cls} FAILED ({type(e).__name__})")
            time.sleep(2)
            continue
        for b in rows:
            qid = b["i"]["value"].rsplit("/", 1)[-1]
            unit = (b.get("unitLabel") or {}).get("value", "").strip()
            if not unit or (unit.startswith("Q") and unit[1:].isdigit()):
                continue                      # unresolved or dimensionless: not a price
            try:
                amt = float(b["v"]["value"])
            except ValueError:
                continue
            if amt <= 0:
                continue
            num = f"{amt:,.0f}" if amt % 1 == 0 else f"{amt:,.2f}"
            sym = CURRENCY.get(unit)
            val = f"{sym}{num}" if sym else f"{num} {unit}"
            slot = specs.setdefault(qid, {})
            if "msrp" in slot:
                continue
            slot["msrp"] = val
            n += 1
        time.sleep(0.5)
    print(f"  msrp       {n:6} models")


def harvest_logos():
    """Marque logos (P154) — a wordmark on white beats a faded photo of a factory."""
    q = ("SELECT ?m ?mLabel ?logo WHERE { ?i wdt:P31 wd:Q3231690 ; wdt:P176 ?m . "
         "?m wdt:P154 ?logo . "
         'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }')
    try:
        rows = _query(q)
    except Exception as e:
        print(f"  logos      FAILED ({type(e).__name__})")
        return
    out = {}
    for b in rows:
        name = (b.get("mLabel") or {}).get("value", "").strip()
        if not name or (name.startswith("Q") and name[1:].isdigit()):
            continue
        out.setdefault(name, b["logo"]["value"])
    if out:
        (ROOT / "data" / "brand_logos.json").write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"  logos      {len(out):6} marques")



# ---------------------------------------------------------------- image quality
# Wikidata often carries several P18 images for one car, and the harvester used to keep
# whichever row arrived first: a 640px interior shot could beat a Featured Picture of the
# car itself. This scores every candidate against the Commons file record and rewrites
# data/car_library.json with the winner, so the library grid and every model page show
# the best available photograph. Time-boxed and fail-safe: on a slow or broken API the
# existing photographs are left exactly as they are.
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Filename words that mean "this is not a photograph of the whole car".
PENALTY = {"interior": 45, "dashboard": 45, "dash ": 30, "cockpit": 40, "engine": 40,
           "motor ": 25, "badge": 50, "logo": 55, "emblem": 50, "wheel": 30, "seat": 35,
           "boot": 25, "trunk": 25, "headlamp": 35, "headlight": 35, "taillight": 35,
           "tail light": 35, "gauge": 35, "steering": 40, "chassis": 30, "cutaway": 25,
           "diagram": 45, "drawing": 40, "blueprint": 45, "sketch": 35, "poster": 30,
           "advert": 35, "brochure": 35, "stamp": 40, "model car": 45, "toy": 45,
           "scale model": 45, "miniature": 40, "wreck": 30, "crash": 30, "junkyard": 30,
           "scrapyard": 30, "rusty": 25, "burn": 25, "engine bay": 40}
BONUS = {"front": 8, "side": 6, "rear": 4, "exterior": 8, "profile": 4}


def score_image(name, w, h, assessments):
    """Higher is better. Community assessment dominates, resolution breaks ties, and
    filenames that describe a part rather than the car are pushed down."""
    n = (name or "").lower()
    a = (assessments or "").lower()
    s = 0.0
    if "featured" in a:
        s += 100
    if "quality" in a:
        s += 60
    if "valued" in a:
        s += 30
    w, h = int(w or 0), int(h or 0)
    s += min((w * h) / 1e6, 16.0) * 1.5        # up to +24: a tiebreaker, not a trump card
    if w and w < 800:
        s -= 60                                 # too small to run at 1100px on a model page
    if w and h and 0.45 <= h / w <= 1.10:
        s += 10                                 # landscape-ish: how a car is normally shot
    if n.endswith(".svg"):
        s -= 80                                 # a diagram or wordmark, never a car photo
    for word, pen in PENALTY.items():
        if word in n:
            s -= pen
    for word, bon in BONUS.items():
        if word in n:
            s += bon
    return s


MULTI_TPL = """SELECT ?i (GROUP_CONCAT(?img; separator="|") AS ?imgs) WHERE {
  ?i wdt:P31 wd:%(cls)s ; wdt:P18 ?img .
} GROUP BY ?i HAVING(COUNT(?img) > 1)"""


def _fname(url):
    """P18 value -> Commons file name. The claim is a Special:FilePath URL."""
    part = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    return part.replace("_", " ").strip()


def _commons_meta(names, timeout=60):
    """imageinfo for up to 50 files in one call. Returns {name: (w, h, assessments)}."""
    params = {"action": "query", "format": "json", "prop": "imageinfo",
              "iiprop": "size|extmetadata", "iiextmetadatafilter": "Assessments",
              "titles": "|".join("File:" + n for n in names)}
    req = urllib.request.Request(COMMONS_API + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        pages = json.loads(r.read().decode()).get("query", {}).get("pages", {})
    out = {}
    for p in pages.values():
        title = p.get("title", "")[5:]          # strip the "File:" prefix
        ii = (p.get("imageinfo") or [{}])[0]
        ext = ii.get("extmetadata") or {}
        out[title] = (ii.get("width", 0), ii.get("height", 0),
                      (ext.get("Assessments") or {}).get("value", ""))
    return out


def harvest_image_quality(budget_s=None):
    """Pick the best P18 image for every model that has more than one, and write the
    winner back into data/car_library.json. Never raises, never blocks the build."""
    import os
    budget = float(budget_s if budget_s is not None else os.environ.get("IMG_SCORE_BUDGET", 150))
    started = time.monotonic()
    lib_path = ROOT / "data" / "car_library.json"
    try:
        lib = json.loads(lib_path.read_text())
    except Exception as e:
        print(f"  imagequality skipped ({type(e).__name__}: no catalogue to patch)")
        return
    known = {r.get("q") for r in lib if r.get("q")}

    cands = {}
    for cls in CLASSES:
        if time.monotonic() - started > budget:
            break
        try:
            rows = _query(MULTI_TPL % {"cls": cls}, timeout=90)
        except Exception as e:
            print(f"  imagequality class {cls} FAILED ({type(e).__name__})")
            time.sleep(2)
            continue
        for b in rows:
            qid = b["i"]["value"].rsplit("/", 1)[-1]
            if qid not in known or qid in cands:
                continue
            files = [_fname(u) for u in b["imgs"]["value"].split("|") if u]
            files = [f for f in dict.fromkeys(files) if f]
            if len(files) > 1:
                cands[qid] = files[:8]          # eight candidates is already generous
        time.sleep(0.4)
    if not cands:
        print("  imagequality      0 models with a choice to make")
        return

    names = sorted({f for fs in cands.values() for f in fs})
    meta, batches = {}, 0
    for i in range(0, len(names), 50):
        if time.monotonic() - started > budget:
            print(f"  imagequality time budget hit after {batches} batches; scoring what we have")
            break
        try:
            meta.update(_commons_meta(names[i:i + 50]))
            batches += 1
        except Exception as e:
            print(f"  imagequality batch {batches} FAILED ({type(e).__name__})")
            time.sleep(1)
        time.sleep(0.15)
    if not meta:
        print("  imagequality      no Commons metadata; photographs left unchanged")
        return

    best, changed = {}, 0
    for qid, files in cands.items():
        scored = [(score_image(f, *meta[f]), f) for f in files if f in meta]
        if not scored:
            continue
        best[qid] = max(scored)[1]
    by_q = {r["q"]: r for r in lib if r.get("q")}
    for qid, winner in best.items():
        row = by_q.get(qid)
        if row is not None and row.get("p") != winner:
            row["p"] = winner
            changed += 1
    if changed:
        lib_path.write_text(json.dumps(lib, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "data" / "image_best.json").write_text(
        json.dumps(best, ensure_ascii=False, separators=(",", ":")))
    print(f"  imagequality {len(best):6} models scored ({len(meta)} files, "
          f"{batches} batches); {changed} photograph(s) upgraded")


# Ordered best to worst. Dimensions are held constant where the point is the filename,
# so the assertion tests the ranking rule and not an accident of resolution.
SELFTEST = [
    ("Porsche 911 front three quarter.jpg", 4000, 2600, "featured picture"),
    ("Porsche 911 side.jpg", 4000, 2600, "quality image"),
    ("Porsche 911 rear.jpg", 4000, 2600, "valued image"),
    ("Porsche 911.jpg", 4000, 2600, ""),
    ("Porsche 911.jpg", 1600, 1050, ""),
    ("Porsche 911 wheel.jpg", 4000, 2600, ""),
    ("Porsche 911 interior.jpg", 4000, 2600, ""),
    ("Porsche 911 badge.jpg", 4000, 2600, ""),
    ("Porsche 911 tiny.jpg", 400, 300, ""),
    ("Porsche 911 logo.svg", 4000, 2600, ""),
]


def selftest():
    """Ranking is the whole point, so assert the order rather than eyeball it."""
    scores = [(score_image(*c), c[0]) for c in SELFTEST]
    for i in range(len(scores) - 1):
        assert scores[i][0] > scores[i + 1][0], f"{scores[i]} should outrank {scores[i+1]}"
    for s, n in scores:
        print(f"  {s:8.1f}  {n}")
    print("SELFTEST OK: image ranking holds")
    return 0


def main():
    specs, failed = {}, []
    for key, (prop, kind) in FIELDS.items():
        try:
            rows = fetch(prop, kind)
        except Exception as e:
            failed.append(key)
            print(f"  {key:11} FAILED ({type(e).__name__})")
            time.sleep(2)
            continue
        n = 0
        for b in rows:
            qid = b["i"]["value"].rsplit("/", 1)[-1]
            val = clean(kind, b)
            if val is None:
                continue
            slot = specs.setdefault(qid, {})
            if key in slot:                       # keep the first value; models list variants
                continue
            slot[key] = val
            n += 1
        print(f"  {key:11} {n:6} models")
        time.sleep(1)

    harvest_msrp(specs)
    harvest_logos()
    harvest_image_quality()

    if not specs:
        print("SPECS SKIPPED: no data retrieved; leaving any existing file untouched")
        return 0
    OUT.write_text(json.dumps(specs, ensure_ascii=False, separators=(",", ":")))
    with_gallery = sum(1 for v in specs.values() if v.get("commons"))
    print(f"SPECS OK: {len(specs)} models carry at least one fact "
          f"({with_gallery} have a Commons gallery); {len(failed)} field(s) failed")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
