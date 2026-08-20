#!/usr/bin/env python3
"""deep_harvest.py — the wide net over Wikidata, run nightly where time is cheap.

The build-time harvest asks for a fixed allow-list of vehicle classes, which is fast
but misses any car filed under an odd class. This pass turns the question around:
it collects every manufacturer the catalogue already knows, then pulls EVERYTHING
those manufacturers ever made (P176), whatever class it was filed under, and keeps
the records whose class reads like a car. A Chery filed as "electric car", a
Mercedes filed only as "limousine", a JAC filed under a class nobody thought to
allow-list — all of it lands.

Results are merged into data/car_library.json AND embedded into data/cars.sqlite
(table site_kv, key car_library_json) so the nightly release carries the fat
catalogue to every deploy — build.sh extracts it via extract_library.py.

Never raises out of main(): the nightly ingest must publish even on a Wikidata
outage.
"""
import json, os, re, sqlite3, time, urllib.parse, urllib.request
from pathlib import Path

import harvest_wikidata as hw

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "data" / "car_library.json"
DB = ROOT / "data" / "cars.sqlite"
ENDPOINT = "https://query.wikidata.org/sparql"
UA = hw.UA
BUDGET = int(os.environ.get("DEEP_BUDGET", "1800"))

# A record survives the sweep only if at least one of its classes reads like a car
# and none reads like the junk P176 also covers (engines, gearboxes, army trucks,
# the manufacturer's racing TEAM, video games about the marque...).
GOOD = re.compile(r"car|automobile|vehicle model|roadster|coup|sedan|saloon|hatchback|"
                  r"estate|convertible|cabriolet|limousine|pickup|sport utility|suv|"
                  r"minivan|van model|grand tourer|supercar|hypercar|prototype", re.I)
BAD = re.compile(r"engine|gearbox|transmission|combat|tank|military|armoured|armored|"
                 r"truck|lorry|bus\b|coach\b|motorcycle|moped|scooter|bicycle|"
                 r"locomotive|tram|boat|ship|vessel|aircraft|aeroplane|helicopter|"
                 r"tractor|forklift|excavator|business|enterprise|company|team|"
                 r"organization|human|award|video game|film|song|album|book|"
                 r"racing series|championship|firearm", re.I)


def _sparql(query, timeout=120):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"format": "json", "query": query})
    req = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json",
                                               "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["results"]["bindings"]


def manufacturers():
    """Every distinct manufacturer QID behind the classes the base harvest covers."""
    qids = set()
    for cls in hw.CLASSES:
        try:
            rows = _sparql("SELECT DISTINCT ?m WHERE { ?i wdt:P31 wd:%s . ?i wdt:P176 ?m }" % cls)
            for b in rows:
                qids.add(b["m"]["value"].rsplit("/", 1)[-1])
        except Exception as e:
            print(f"  deep: manufacturer scan {cls} failed ({e}); continuing")
        time.sleep(0.5)
    return sorted(qids)


SWEEP = """SELECT ?i ?iLabel ?mLabel ?inc ?img ?clsLabel WHERE {
  VALUES ?m { %s }
  ?i wdt:P176 ?m .
  ?i wdt:P31 ?cls .
  OPTIONAL { ?i wdt:P571 ?inc }
  OPTIONAL { ?i wdt:P18 ?img }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def sweep(qids, deadline):
    keep, seen_cls = {}, {}
    CHUNK = 40
    for i in range(0, len(qids), CHUNK):
        if time.time() > deadline:
            print(f"  deep: budget reached after {i}/{len(qids)} manufacturers; keeping what was swept")
            break
        vals = " ".join(f"wd:{q}" for q in qids[i:i + CHUNK])
        try:
            rows = _sparql(SWEEP % vals)
        except Exception as e:
            print(f"  deep: chunk {i // CHUNK} failed ({e}); continuing")
            time.sleep(2)
            continue
        for b in rows:
            rec = hw.to_record(b)
            if not rec:
                continue
            cls = (b.get("clsLabel") or {}).get("value", "")
            q = rec["q"]
            entry = keep.setdefault(q, rec)
            cl = seen_cls.setdefault(q, [])
            cl.append(cls)
            if rec.get("p") and not entry.get("p"):
                entry["p"] = rec["p"]
        time.sleep(0.5)
    out = []
    for q, rec in keep.items():
        classes = " | ".join(seen_cls.get(q, []))
        if BAD.search(classes):
            continue
        if not GOOD.search(classes):
            continue
        out.append(rec)
    return out


def embed(records_json):
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS site_kv (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("INSERT OR REPLACE INTO site_kv (k, v) VALUES ('car_library_json', ?)",
                (records_json,))
    con.commit()
    con.close()


def main():
    deadline = time.time() + BUDGET
    try:
        existing = json.loads(LIB.read_text()) if LIB.exists() else []
        qids = manufacturers()
        print(f"  deep: sweeping {len(qids)} manufacturers (budget {BUDGET}s)")
        found = sweep(qids, deadline)
        print(f"  deep: sweep kept {len(found)} car records after class filtering")
        merged, added, enriched = hw.merge(existing, found)
        payload = json.dumps(merged, separators=(",", ":"), ensure_ascii=False)
        LIB.write_text(payload)
        embed(payload)
        print(f"DEEP HARVEST OK: {len(existing)} -> {len(merged)} models "
              f"(+{added} new, {enriched} enriched); catalogue embedded in the dataset")
    except Exception as e:
        print(f"WARNING: deep harvest skipped ({e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
