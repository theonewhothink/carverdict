#!/usr/bin/env python3
"""harvest_wikidata.py — refresh data/car_library.json from Wikidata.

Why this exists: the original harvest only asked for three classes (car model, car,
concept car). Wikidata files most flagship nameplates under OTHER classes, so the
catalogue was silently missing them:

    Porsche Cayenne, Porsche Boxster  -> Q59773381  automobile model series
    Porsche 917, Porsche 962          -> Q90834785  racing automobile model

Those classes are queried here. Merge is by Q-id, additive: a record already in the
committed catalogue is never dropped, only enriched with a photograph if it lacked one.

Network failures never fail the build — the committed catalogue is the floor, this is
the delta on top. Run with --from-file <json> to merge a pre-fetched harvest instead.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "data" / "car_library.json"
ENDPOINT = "https://query.wikidata.org/sparql"
UA = "CarVerdict/1.0 (https://carsite.adir-073.workers.dev) python-urllib"

# Classes that hold real road/racing cars. Deliberately excludes bus model (Q23039057),
# truck model (Q21546143), locomotive class (Q19832486), motorcycle model (Q23866334)
# and combat vehicle model (Q100710213) — an earlier harvest polluted the catalogue with
# locomotives and lifeboats, so class selection stays a strict allow-list.
CLASSES = {
    "Q3231690":  "car model",
    "Q1420":     "car",
    "Q850270":   "concept car",
    "Q59773381": "automobile model series",
    "Q90834785": "racing automobile model",
    "Q673687":   "racing automobile",
    "Q10429667": "sports car",
    "Q3882470":  "one-off vehicle",
}

QUERY = """SELECT ?i ?iLabel ?mLabel ?inc ?img WHERE {
  ?i wdt:P31 wd:%s .
  OPTIONAL { ?i wdt:P176 ?m }
  OPTIONAL { ?i wdt:P571 ?inc }
  OPTIONAL { ?i wdt:P18 ?img }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def fetch(cls, timeout=90):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"format": "json", "query": QUERY % cls})
    req = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json",
                                               "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["results"]["bindings"]


def to_record(b):
    qid = b["i"]["value"].rsplit("/", 1)[-1]
    name = (b.get("iLabel") or {}).get("value", "").strip()
    # an unlabelled item comes back as its own Q-id; that is not a car name
    if not name or (name.startswith("Q") and name[1:].isdigit()):
        return None
    img = (b.get("img") or {}).get("value", "")
    photo = ""
    if img:
        photo = urllib.parse.unquote(img.rsplit("/", 1)[-1]).replace("_", " ")
    inc = (b.get("inc") or {}).get("value", "")
    # the label service echoes the Q-id when the manufacturer item has no English label;
    # storing that would render "Mini - Q796364" on the site, so drop it and let the
    # build infer the marque from the model name instead
    mk = (b.get("mLabel") or {}).get("value", "").strip()
    if mk.startswith("Q") and mk[1:].isdigit():
        mk = ""
    return {"q": qid, "n": name, "m": mk,
            "p": photo, "y": inc[:4] if inc else ""}


def merge(existing, incoming):
    by_q = {x["q"]: x for x in existing}
    added = enriched = 0
    for r in incoming:
        cur = by_q.get(r["q"])
        if cur is None:
            by_q[r["q"]] = r
            added += 1
        elif not cur.get("p") and r.get("p"):
            cur["p"] = r["p"]
            enriched += 1
        elif not cur.get("y") and r.get("y"):
            cur["y"] = r["y"]
    out = sorted(by_q.values(), key=lambda x: ((x.get("m") or "zzz"), x["n"]))
    return out, added, enriched


def main():
    existing = json.loads(LIB.read_text())
    before = len(existing)

    if "--from-file" in sys.argv:
        src = Path(sys.argv[sys.argv.index("--from-file") + 1])
        incoming = json.loads(src.read_text())
        incoming = [{k: r.get(k, "") for k in ("q", "n", "m", "p", "y")} for r in incoming]
    else:
        incoming, failures = [], []
        for cls, label in CLASSES.items():
            try:
                rows = fetch(cls)
                got = [r for r in (to_record(b) for b in rows) if r]
                incoming += got
                print(f"  {label:26} {len(got):6} records")
            except Exception as e:                      # network, timeout, rate limit
                failures.append(label)
                print(f"  {label:26} FAILED ({type(e).__name__}) - keeping committed data")
            time.sleep(1)                               # be a good Wikidata citizen
        if failures and not incoming:
            print(f"HARVEST SKIPPED: every query failed; catalogue unchanged at {before}")
            return 0

    merged, added, enriched = merge(existing, incoming)
    if len(merged) < before:                            # never shrink the catalogue
        print(f"HARVEST ABORTED: merge would drop records ({before} -> {len(merged)})")
        return 0
    LIB.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")))
    photos = sum(1 for x in merged if x.get("p"))
    print(f"HARVEST OK: {before} -> {len(merged)} models "
          f"(+{added} new, {enriched} gained a photo, {photos} with photography)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
