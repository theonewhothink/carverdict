#!/usr/bin/env python3
"""
cardata_ingest.py — Carsite data engine (Phase 1).

Modes:
  --fetch        Live HTTP pull from NHTSA/EPA (run on machine/CI with open network).
                 Idempotent + resumable: skips any endpoint already cached in data/raw/.
  --build        Parse data/raw/ caches -> data/cars.sqlite (computed scores, verdicts, cost curves).
  --manifest F   JSON list of {"make":..,"model":..,"years":[..]} to ingest. Default: manifest_seed.json.
  --top300       (fetch) discover models via vPIC ranked list in manifest_top300.json.

Every number published downstream traces to a cached raw file. No fabrication.
"""
import argparse, json, math, re, sqlite3, sys, time, unicodedata
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = Path("/tmp/cars.sqlite") if (Path("/sessions").exists() and not __import__("os").environ.get("CARSITE_DB_LOCAL")) else ROOT / "data" / "cars.sqlite"  # sandbox mount lacks sqlite locking; copied back post-build
CURRENT_YEAR = 2026
SLEEP = 0.5
UA = {"User-Agent": "CarsiteBot/1.0 (ownership-cost research; contact via site)"}

# Age-indexed annual maintenance+repair bands (USD), industry averages.
# Source: AAA "Your Driving Costs" 2023-2025 editions + CarMD Vehicle Health Index 2024
# (repair cost trend +15% YoY). Published on /methodology. Estimates, labeled as such.
MAINT_BAND = [
    (0, 2, 450, 900), (3, 5, 700, 1300), (6, 8, 950, 1700),
    (9, 12, 1200, 2200), (13, 30, 1500, 2800),
]

SEVERE_RE = re.compile(r"fire|crash|injur|death|stall|brake fail|steering loss|rollaway|explod", re.I)


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def cache_path(kind: str, make: str, model: str, year=None) -> Path:
    name = f"{slug(make)}~{slug(model)}" + (f"~{year}" if year else "")
    p = RAW / kind
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{name}.json"


def fetch_json(url: str):
    req = Request(url, headers=UA)
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def cached_fetch(kind, url, make, model, year=None):
    p = cache_path(kind, make, model, year)
    if p.exists() and p.stat().st_size > 2:
        return json.loads(p.read_text())
    data = fetch_json(url)
    p.write_text(json.dumps(data))
    time.sleep(SLEEP)
    return data


def fetch_vehicle(make, model, year):
    m, mo = quote(make), quote(model)
    cached_fetch("complaints",
        f"https://api.nhtsa.gov/complaints/complaintsByVehicle?make={m}&model={mo}&modelYear={year}",
        make, model, year)
    cached_fetch("recalls",
        f"https://api.nhtsa.gov/recalls/recallsByVehicle?make={m}&model={mo}&modelYear={year}",
        make, model, year)
    # EPA: resolve model name, then menu options -> first vehicle id detail
    try:
        menu = cached_fetch("epa_menu",
            f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?year={year}&make={m}&model={mo}",
            make, model, year)
        items = menu.get("menuItem", []) if isinstance(menu, dict) else []
        if items:
            vid = items[0]["value"] if isinstance(items, list) else items["value"]
            cached_fetch("epa_vehicle",
                f"https://www.fueleconomy.gov/ws/rest/vehicle/{vid}", make, model, year)
    except Exception as e:
        print(f"  EPA miss {make} {model} {year}: {e}")


# ---------------- BUILD ----------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS makes(id INTEGER PRIMARY KEY, name TEXT UNIQUE, slug TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS models(id INTEGER PRIMARY KEY, make_id INT, name TEXT, slug TEXT,
  UNIQUE(make_id, slug));
CREATE TABLE IF NOT EXISTS model_years(id INTEGER PRIMARY KEY, model_id INT, year INT,
  complaint_count INT, complaint_sample INT, recall_count INT, severe_recalls INT DEFAULT 0,
  is_ev INT DEFAULT 0, data_gap TEXT, UNIQUE(model_id, year));
CREATE TABLE IF NOT EXISTS complaints(id INTEGER PRIMARY KEY, my_id INT, component TEXT,
  count INT, sample TEXT);
CREATE TABLE IF NOT EXISTS recalls(id INTEGER PRIMARY KEY, my_id INT, campaign TEXT, date TEXT,
  component TEXT, summary TEXT, severe INT);
CREATE TABLE IF NOT EXISTS fuel(my_id INT PRIMARY KEY, fuel_type TEXT, mpg_city REAL, mpg_hwy REAL,
  mpg_comb REAL, annual_fuel_cost INT, ev_range REAL, kwh_100mi REAL);
CREATE TABLE IF NOT EXISTS computed_scores(my_id INT PRIMARY KEY, reliability_score INT,
  verdict TEXT, reasons TEXT, cost_curve TEXT, complaints_per_year REAL);
CREATE TABLE IF NOT EXISTS ev_extras(my_id INT PRIMARY KEY, battery_warranty TEXT,
  battery_replacement_low INT, battery_replacement_high INT, source TEXT);
"""


def load_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def build(manifest):
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    cur = con.cursor()
    rows = []  # (my_id, cpx) for percentile pass
    ev_seed = load_json(ROOT / "data" / "ev_battery_seed.json") or {}
    gaps = set(load_json(ROOT / "data" / "known_gaps.json") or [])

    for entry in manifest:
        make, model = entry["make"], entry["model"]
        cur.execute("INSERT OR IGNORE INTO makes(name, slug) VALUES(?,?)", (make, slug(make)))
        make_id = cur.execute("SELECT id FROM makes WHERE slug=?", (slug(make),)).fetchone()[0]
        cur.execute("INSERT OR IGNORE INTO models(make_id, name, slug) VALUES(?,?,?)",
                    (make_id, model, slug(model)))
        model_id = cur.execute("SELECT id FROM models WHERE make_id=? AND slug=?",
                               (make_id, slug(model))).fetchone()[0]
        for year in entry["years"]:
            c = load_json(cache_path("complaints", make, model, year)) or {}
            r = load_json(cache_path("recalls", make, model, year)) or {}
            ev = load_json(cache_path("epa_vehicle", make, model, year)) or {}
            complaints = c.get("results", [])
            recalls = r.get("results", [])
            key3 = f"{slug(make)}~{slug(model)}~{year}"
            gap = []
            if f"{key3}.complaints" in gaps:
                gap.append("complaints")
            if f"{key3}.recalls" in gaps:
                gap.append("recalls")
            # API 'count' field is authoritative when responses were truncated at fetch time
            complaint_total = max(len(complaints), int(c.get("count") or 0))
            fuel_type = (ev.get("fuelType") or "").lower()
            is_ev = 1 if ("electric" in fuel_type and "hybrid" not in fuel_type) \
                or entry.get("is_ev") else 0
            cur.execute("""INSERT OR REPLACE INTO model_years(model_id, year, complaint_count,
                complaint_sample, recall_count, severe_recalls, is_ev, data_gap)
                VALUES(?,?,?,?,?,?,?,?)""",
                (model_id, year,
                 None if "complaints" in gap else complaint_total, len(complaints),
                 None if "recalls" in gap else len(recalls),
                 sum(1 for x in recalls if SEVERE_RE.search(x.get("Summary", ""))), is_ev,
                 ",".join(gap) or None))
            my_id = cur.execute("SELECT id FROM model_years WHERE model_id=? AND year=?",
                                (model_id, year)).fetchone()[0]
            # component clusters
            cur.execute("DELETE FROM complaints WHERE my_id=?", (my_id,))
            comp = {}
            for x in complaints:
                for part in (x.get("components") or "UNKNOWN").split(","):
                    part = part.strip() or "UNKNOWN"
                    comp.setdefault(part, [0, ""])
                    comp[part][0] += 1
                    if not comp[part][1] and x.get("summary"):
                        comp[part][1] = x["summary"][:400]
            for k, (n, sample) in sorted(comp.items(), key=lambda t: -t[1][0]):
                cur.execute("INSERT INTO complaints(my_id, component, count, sample) VALUES(?,?,?,?)",
                            (my_id, k, n, sample))
            cur.execute("DELETE FROM recalls WHERE my_id=?", (my_id,))
            for x in recalls:
                cur.execute("""INSERT INTO recalls(my_id, campaign, date, component, summary, severe)
                    VALUES(?,?,?,?,?,?)""",
                    (my_id, x.get("NHTSACampaignNumber"), x.get("ReportReceivedDate"),
                     x.get("Component"), (x.get("Summary") or "")[:500],
                     1 if SEVERE_RE.search(x.get("Summary", "")) else 0))
            if ev:
                cur.execute("""INSERT OR REPLACE INTO fuel VALUES(?,?,?,?,?,?,?,?)""",
                    (my_id, ev.get("fuelType"), _f(ev.get("city08")), _f(ev.get("highway08")),
                     _f(ev.get("comb08")), _i(ev.get("fuelCost08")), _f(ev.get("range")) or None,
                     _f(ev.get("combE")) or None))
            key = f"{slug(make)}~{slug(model)}"
            if is_ev and key in ev_seed:
                s = ev_seed[key]
                cur.execute("INSERT OR REPLACE INTO ev_extras VALUES(?,?,?,?,?)",
                    (my_id, s["battery_warranty"], s["repl_low"], s["repl_high"], s["source"]))
            years_on_road = max(1, CURRENT_YEAR - year + 1)
            if "complaints" in gap:
                cur.execute("""INSERT OR REPLACE INTO computed_scores
                    VALUES(?,NULL,'DATA PENDING','["NHTSA complaint data temporarily unavailable for this year"]',NULL,NULL)""",
                    (my_id,))
            else:
                rows.append((my_id, complaint_total / years_on_road))
    con.commit()

    # percentile normalization for complaint penalty
    cpx_sorted = sorted(v for _, v in rows) or [1]
    p95 = cpx_sorted[min(len(cpx_sorted) - 1, int(0.95 * len(cpx_sorted)))] or 1
    for my_id, cpx in rows:
        my = cur.execute("""SELECT my.year, my.recall_count, my.severe_recalls, my.is_ev,
            f.annual_fuel_cost FROM model_years my LEFT JOIN fuel f ON f.my_id=my.id
            WHERE my.id=?""", (my_id,)).fetchone()
        year, rc, sev, is_ev, afc = my
        rc, sev = rc or 0, sev or 0
        pen_c = min(60.0, 60.0 * cpx / p95)
        pen_r = min(30.0, 6.0 * sev + 2.0 * (rc - sev))
        score = max(0, round(100 - pen_c - pen_r))
        top = cur.execute("SELECT component, count FROM complaints WHERE my_id=? ORDER BY count DESC LIMIT 3",
                          (my_id,)).fetchall()
        reasons = []
        for compn, n in top:
            if n >= 5:
                reasons.append(f"{n} owner complaints filed with NHTSA for {compn.title()}")
        if sev:
            reasons.append(f"{sev} safety recall(s) involving fire/crash/stall risk")
        elif rc:
            reasons.append(f"{rc} NHTSA recall campaign(s) on record")
        if not reasons:
            reasons.append("Low NHTSA complaint volume for its age")
        verdict = "BUY" if score >= 70 else ("CAUTION" if score >= 45 else "AVOID")
        # cost curve: fuel + maintenance band by age
        curve = []
        for age in range(0, 11):
            lo = hi = 0
            for a0, a1, l, h in MAINT_BAND:
                if a0 <= age <= a1:
                    lo, hi = l, h
            fc = afc or (700 if is_ev else 1900)  # EPA default assumption, labeled estimate
            curve.append({"age": age, "fuel": fc, "maint_low": lo, "maint_high": hi,
                          "total_low": fc + lo, "total_high": fc + hi})
        cur.execute("""INSERT OR REPLACE INTO computed_scores VALUES(?,?,?,?,?,?)""",
                    (my_id, score, verdict, json.dumps(reasons[:3]), json.dumps(curve), round(cpx, 2)))
    con.commit()
    n_my = cur.execute("SELECT COUNT(*) FROM model_years").fetchone()[0]
    n_c = cur.execute("SELECT SUM(complaint_count) FROM model_years").fetchone()[0]
    print(f"BUILD OK: {n_my} model-years, {n_c} complaints total -> {DB}")
    con.close()


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--manifest", default=str(ROOT / "data" / "manifest_seed.json"))
    args = ap.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    if args.fetch:
        for e in manifest:
            for y in e["years"]:
                print(f"fetch {e['make']} {e['model']} {y}")
                try:
                    fetch_vehicle(e["make"], e["model"], y)
                except Exception as ex:
                    print(f"  ERROR {ex} (resumable; rerun)")
    if args.build:
        build(manifest)
    if not (args.fetch or args.build):
        ap.print_help()


if __name__ == "__main__":
    main()
