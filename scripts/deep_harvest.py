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


# ---------------------------------------------------------------------------
# Sweep 2: the WHOLE subclass tree. The manufacturer sweep above only reaches makers the
# allow-list already knows. This sweep asks the question the catalogue's promise implies:
# every item whose class descends from "automobile model" or "motor car" — whatever the
# class is called, whoever made it, concept cars and one-offs included. Class membership
# in the tree is the keep-signal, so the GOOD name-filter is not needed here; BAD still
# strips items whose other classes reveal junk (military trucks, video games, teams).
TREE_ROOTS = ("Q3231690", "Q1420", "Q850270")   # automobile model / motor car / concept car
TREE_BUDGET = int(os.environ.get("TREE_BUDGET", "1500"))


def tree_classes():
    cls = set()
    for root in TREE_ROOTS:
        try:
            rows = _sparql("SELECT DISTINCT ?c WHERE { ?c wdt:P279* wd:%s }" % root, timeout=180)
            for b in rows:
                cls.add(b["c"]["value"].rsplit("/", 1)[-1])
        except Exception as e:
            print(f"  tree: class scan {root} failed ({e}); continuing")
        time.sleep(1)
    return sorted(cls)


TREE_SWEEP = """SELECT ?i ?iLabel ?mLabel ?inc ?img WHERE {
  VALUES ?cls { %s }
  ?i wdt:P31 ?cls .
  OPTIONAL { ?i wdt:P176 ?m }
  OPTIONAL { ?i wdt:P571 ?inc }
  OPTIONAL { ?i wdt:P18 ?img }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def tree_sweep(deadline):
    classes = tree_classes()
    print(f"  tree: {len(classes)} car classes in the subclass tree")
    keep = {}
    CHUNK = 25
    for i in range(0, len(classes), CHUNK):
        if time.time() > deadline:
            print(f"  tree: budget reached after {i}/{len(classes)} classes; keeping what was swept")
            break
        vals = " ".join(f"wd:{q}" for q in classes[i:i + CHUNK])
        try:
            rows = _sparql(TREE_SWEEP % vals, timeout=150)
        except Exception as e:
            print(f"  tree: chunk {i // CHUNK} failed ({e}); continuing")
            time.sleep(2)
            continue
        for b in rows:
            rec = hw.to_record(b)
            if not rec:
                continue
            if BAD.search(rec["n"]):
                continue
            cur = keep.setdefault(rec["q"], rec)
            if rec.get("p") and not cur.get("p"):
                cur["p"] = rec["p"]
            if rec.get("m") and not cur.get("m"):
                cur["m"] = rec["m"]
        time.sleep(0.4)
    print(f"  tree: swept {len(keep)} items across the class tree")
    return list(keep.values())


# ---------------------------------------------------------------------------
# Sweep 3: NHTSA vPIC — the catalogue of every make and model ever registered for the US
# road, which is where the cars that exist OUTSIDE Wikipedia live: kit-car builders,
# three-car EV startups, coachbuilders nobody wrote an article about. Names only, no
# photos — the honest shape of that data. Trim spam is collapsed before merging and a
# per-make cap keeps a junk-heavy make from flooding its brand page.
VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles"
VPIC_BUDGET = int(os.environ.get("VPIC_BUDGET", "2400"))
VPIC_TRIM = re.compile(r"\b(2|4)WD\b|\bAWD\b|\bFWD\b|\bRWD\b|\b4X[24]\b|"
                       r"\bL{1,2}T\b$|\bC[RE]W\b|\bCAB\b|\bS{1,2}R?T?\b$", re.I)


def _vpic(path):
    req = urllib.request.Request(f"{VPIC}/{path}?format=json", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()).get("Results", [])


def vpic_sweep(existing, deadline):
    try:
        makes = _vpic("GetMakesForVehicleType/car")
    except Exception as e:
        print(f"  vpic: make list failed ({e}); skipping")
        return []
    print(f"  vpic: {len(makes)} passenger-car makes registered with the US regulator")
    have = {(str(x.get("m", "")).lower(), x["n"].lower()) for x in existing}
    have_names = {x["n"].lower() for x in existing}
    out, made = [], 0
    for mk in makes:
        if time.time() > deadline:
            print(f"  vpic: budget reached after {made}/{len(makes)} makes; keeping what was fetched")
            break
        made += 1
        mid, mname = mk.get("MakeId"), str(mk.get("MakeName", "")).strip().title()
        if not mid or not mname:
            continue
        try:
            models = _vpic(f"GetModelsForMakeId/{mid}")
        except Exception:
            time.sleep(1)
            continue
        seen_local = set()
        added_for_make = 0
        for row in models:
            n = str(row.get("Model_Name", "")).strip()
            if not n or len(n) > 60 or VPIC_TRIM.search(n):
                continue
            n = re.sub(r"\s+", " ", n).title()
            key = n.lower()
            if key in seen_local:
                continue
            seen_local.add(key)
            if (mname.lower(), key) in have or f"{mname.lower()} {key}" in have_names or key in have_names:
                continue
            if added_for_make >= 400:
                print(f"  vpic: {mname} capped at 400 models (had more)")
                break
            added_for_make += 1
            out.append({"q": f"vpic{mid}-{re.sub(r'[^a-z0-9]+', '-', key)[:40]}",
                        "n": n, "m": mname, "p": "", "y": ""})
        time.sleep(0.25)
    print(f"  vpic: {len(out)} models not in the catalogue from any other source")
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

        # sweep 2: everything in the automobile subclass tree, whoever made it
        tree_found = tree_sweep(time.time() + TREE_BUDGET)
        merged, a2, e2 = hw.merge(merged, tree_found)
        print(f"  tree: +{a2} new, {e2} enriched")

        # sweep 3: the US registration catalogue — the cars outside Wikipedia
        vpic_found = vpic_sweep(merged, time.time() + VPIC_BUDGET)
        merged, a3, _ = hw.merge(merged, vpic_found)
        print(f"  vpic: +{a3} new")
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
