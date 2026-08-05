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
UA = "CarVerdict/1.0 (https://carsite.adir-073.workers.dev) python-urllib"

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

    if not specs:
        print("SPECS SKIPPED: no data retrieved; leaving any existing file untouched")
        return 0
    OUT.write_text(json.dumps(specs, ensure_ascii=False, separators=(",", ":")))
    with_gallery = sum(1 for v in specs.values() if v.get("commons"))
    print(f"SPECS OK: {len(specs)} models carry at least one fact "
          f"({with_gallery} have a Commons gallery); {len(failed)} field(s) failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
