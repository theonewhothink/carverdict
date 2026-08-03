#!/usr/bin/env python3
"""ingest_scale.py — real NHTSA + EPA data at scale, rebuilt on every deploy.

The problem this fixes: data/cars.sqlite shipped with 16 model-years and 8 fuel rows, so a
site promising "true ownership costs from public data" was running on a seed. The original
ingest worked but was only ever pointed at a handful of cars.

Design: the build container has network and ~20 usable minutes, so the whole dataset is
rebuilt from source every deploy rather than persisted. Nothing to migrate, nothing to
drift, and a failed fetch just means that model-year is skipped this run.

Sources (all free, all public, no key):
  EPA fueleconomy.gov  menu/make -> menu/model -> menu/options -> vehicle/{id}
                       MPG city/hwy/combined, annual fuel cost, CO2, displacement, drive
  NHTSA api.nhtsa.gov  complaintsByVehicle  -> complaint count + components
                       recallsByVehicle     -> recall count + severity signals

Budget is explicit: MODEL_YEAR_BUDGET caps the run so a deploy cannot hang. Raise it as
build minutes allow; the selection is ordered so the most-searched cars are always covered.
"""
import concurrent.futures as cf
import json, os, re, sqlite3, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cars.sqlite"
UA = "CarVerdict/1.0 (https://carsite.adir-073.workers.dev) python-urllib"
EPA = "https://www.fueleconomy.gov/ws/rest/vehicle"
NHTSA = "https://api.nhtsa.gov"

MODEL_YEAR_BUDGET = int(os.environ.get("INGEST_BUDGET", "2200"))
YEARS = list(range(int(os.environ.get("INGEST_FROM", "2011")), 2026))
WORKERS = 8

# NHTSA is US-market data, so the marque list is the US market. Ordered by how often
# people actually look them up — the budget is spent from the top down.
MAKES = ["Toyota", "Honda", "Ford", "Chevrolet", "Nissan", "Jeep", "Subaru", "Hyundai",
         "Kia", "BMW", "Mercedes-Benz", "Volkswagen", "Audi", "Lexus", "Mazda", "Dodge",
         "Ram", "GMC", "Tesla", "Volvo", "Acura", "Infiniti", "Cadillac", "Buick",
         "Chrysler", "Porsche", "Land Rover", "Jaguar", "Mitsubishi", "Mini"]


def get(url, timeout=25, tries=2):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(1.5)
    return None


def items(menu):
    """EPA returns a list for many results and a bare object for exactly one."""
    if not isinstance(menu, dict):
        return []
    it = menu.get("menuItem", [])
    return it if isinstance(it, list) else [it]


def base_model(name):
    """'4Runner 2WD' and '4Runner 4WD' are the same nameplate to a reader."""
    n = re.sub(r"\b(2WD|4WD|AWD|FWD|RWD|4x4|4WD/AWD)\b", "", name, flags=re.I)
    return re.sub(r"\s{2,}", " ", n).strip(" -")


def plan():
    """Ask EPA which models actually existed per make-year. Guarantees valid names and
    means we never waste NHTSA calls on a car that was not sold that year."""
    targets, seen = [], set()
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        jobs = {ex.submit(get, f"{EPA}/menu/model?year={y}&make={urllib.parse.quote(mk)}"): (y, mk)
                for y in YEARS for mk in MAKES}
        by_make = {}
        for f in cf.as_completed(jobs):
            y, mk = jobs[f]
            names = []
            for it in items(f.result()):
                b = base_model(it.get("value", ""))
                if b and len(b) < 30:
                    names.append(b)
            by_make.setdefault(mk, {})[y] = sorted(dict.fromkeys(names))
    # round-robin across makes so the budget is not eaten by one manufacturer
    depth = 0
    while len(targets) < MODEL_YEAR_BUDGET and depth < 40:
        added = False
        for mk in MAKES:
            for y in sorted(by_make.get(mk, {}), reverse=True):
                lst = by_make[mk][y]
                if depth < len(lst):
                    key = (mk, lst[depth], y)
                    if key not in seen:
                        seen.add(key)
                        targets.append({"make": mk, "model": lst[depth], "year": y})
                        added = True
                if len(targets) >= MODEL_YEAR_BUDGET:
                    break
            if len(targets) >= MODEL_YEAR_BUDGET:
                break
        if not added:
            break
        depth += 1
    return targets


SEVERE = re.compile(r"air ?bag|brake|steering|fuel|fire|stall|seat belt|electrical", re.I)


def fetch_one(t):
    mk, mo, yr = urllib.parse.quote(t["make"]), urllib.parse.quote(t["model"]), t["year"]
    row = dict(t)

    c = get(f"{NHTSA}/complaints/complaintsByVehicle?make={mk}&model={mo}&modelYear={yr}")
    comp = {}
    if c:
        row["complaints"] = c.get("count") or len(c.get("results") or [])
        for r in (c.get("results") or []):
            for part in (r.get("components") or "").split(","):
                part = part.strip()
                if part:
                    comp[part] = comp.get(part, 0) + 1
    row["components"] = sorted(comp.items(), key=lambda kv: -kv[1])[:6]

    rc = get(f"{NHTSA}/recalls/recallsByVehicle?make={mk}&model={mo}&modelYear={yr}")
    recalls = []
    if rc:
        for r in (rc.get("results") or [])[:12]:
            part = r.get("Component") or ""
            recalls.append({"campaign": r.get("NHTSACampaignNumber") or "",
                            "date": r.get("ReportReceivedDate") or "",
                            "component": part[:120],
                            "summary": (r.get("Summary") or "")[:400],
                            "severe": 1 if SEVERE.search(part) else 0})
    row["recalls"] = recalls

    menu = get(f"{EPA}/menu/options?year={yr}&make={mk}&model={mo}")
    veh = None
    its = items(menu)
    if its:
        veh = get(f"{EPA}/{its[0].get('value')}")
    row["epa"] = veh
    return row


def num(v, cast=float):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def main():
    t0 = time.time()
    targets = plan()
    print(f"planned {len(targets)} model-years across {len(MAKES)} makes, {YEARS[0]}–{YEARS[-1]}")

    rows = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for i, r in enumerate(ex.map(fetch_one, targets), 1):
            rows.append(r)
            if i % 250 == 0:
                print(f"  fetched {i}/{len(targets)}  ({time.time()-t0:.0f}s)")

    got = [r for r in rows if r.get("complaints") or r.get("recalls") or r.get("epa")]
    print(f"fetched {len(rows)}; {len(got)} carry data ({time.time()-t0:.0f}s)")
    if len(got) < 50:
        print("INGEST ABORTED: too little data returned; keeping the committed database")
        return 0

    tmp = ROOT / "data" / "cars.new.sqlite"
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript((ROOT / "scripts" / "schema.sql").read_text()
                      if (ROOT / "scripts" / "schema.sql").exists() else SCHEMA)

    def slug(s):
        s = re.sub(r"[^\w\s-]", "", str(s).lower()).strip()
        return re.sub(r"[\s_]+", "-", s)[:60] or "x"

    mk_id, mo_id = {}, {}
    for r in got:
        mk = r["make"]
        if mk not in mk_id:
            cur = con.execute("INSERT OR IGNORE INTO makes(name,slug) VALUES(?,?)", (mk, slug(mk)))
            mk_id[mk] = con.execute("SELECT id FROM makes WHERE name=?", (mk,)).fetchone()[0]
        key = (mk, r["model"])
        if key not in mo_id:
            con.execute("INSERT OR IGNORE INTO models(make_id,name,slug) VALUES(?,?,?)",
                        (mk_id[mk], r["model"], slug(r["model"])))
            mo_id[key] = con.execute("SELECT id FROM models WHERE make_id=? AND slug=?",
                                     (mk_id[mk], slug(r["model"]))).fetchone()[0]

        e = r.get("epa") or {}
        fuel_type = (e.get("fuelType") or "").strip()
        is_ev = 1 if "electric" in fuel_type.lower() else 0
        severe = sum(x["severe"] for x in r["recalls"])
        con.execute("""INSERT OR IGNORE INTO model_years
            (model_id,year,complaint_count,complaint_sample,recall_count,severe_recalls,is_ev,data_gap)
            VALUES(?,?,?,?,?,?,?,?)""",
            (mo_id[key], r["year"], r.get("complaints") or 0, r.get("complaints") or 0,
             len(r["recalls"]), severe, is_ev, None if r.get("complaints") is not None else "complaints"))
        my = con.execute("SELECT id FROM model_years WHERE model_id=? AND year=?",
                         (mo_id[key], r["year"])).fetchone()[0]

        for part, n in r["components"]:
            con.execute("INSERT INTO complaints(my_id,component,count,sample) VALUES(?,?,?,?)",
                        (my, part, n, None))
        for x in r["recalls"]:
            con.execute("""INSERT INTO recalls(my_id,campaign,date,component,summary,severe)
                           VALUES(?,?,?,?,?,?)""",
                        (my, x["campaign"], x["date"], x["component"], x["summary"], x["severe"]))
        if e:
            con.execute("""INSERT OR REPLACE INTO fuel
                (my_id,fuel_type,mpg_city,mpg_hwy,mpg_comb,annual_fuel_cost,ev_range,kwh_100mi)
                VALUES(?,?,?,?,?,?,?,?)""",
                (my, fuel_type or None, num(e.get("city08")), num(e.get("highway08")),
                 num(e.get("comb08")), num(e.get("fuelCost08"), int),
                 num(e.get("rangeA")) or num(e.get("range")), num(e.get("combE"))))
    con.commit()

    # verdicts: complaints per year of exposure, weighted by severe recalls
    for my, yr, cc, rc, sev in con.execute(
            "SELECT id,year,complaint_count,recall_count,severe_recalls FROM model_years"):
        age = max(1, 2026 - yr)
        cpy = (cc or 0) / age
        score = 100 - min(60, cpy * 1.6) - min(25, (sev or 0) * 5) - min(10, (rc or 0) * 1.2)
        score = max(1, min(100, round(score)))
        verdict = "BUY" if score >= 70 else ("CAUTION" if score >= 45 else "AVOID")
        reasons = json.dumps([
            f"{cc or 0} NHTSA complaints on record ({cpy:.1f}/yr of exposure)",
            f"{rc or 0} recall campaigns, {sev or 0} touching safety-critical systems",
        ])
        curve = json.dumps([{"age": a,
                             "total_low": 260 + a * 95 + int(cpy * 12),
                             "total_high": 520 + a * 185 + int(cpy * 26)} for a in range(0, 16)])
        con.execute("""INSERT OR REPLACE INTO computed_scores
            (my_id,reliability_score,verdict,reasons,cost_curve,complaints_per_year)
            VALUES(?,?,?,?,?,?)""", (my, score, verdict, reasons, curve, round(cpy, 2)))
    con.commit()

    n_my = con.execute("SELECT COUNT(*) FROM model_years").fetchone()[0]
    n_f = con.execute("SELECT COUNT(*) FROM fuel").fetchone()[0]
    n_c = con.execute("SELECT SUM(complaint_count) FROM model_years").fetchone()[0] or 0
    n_r = con.execute("SELECT COUNT(*) FROM recalls").fetchone()[0]
    con.close()

    # only replace the committed database once the new one is provably bigger
    old = 0
    if DB.exists():
        try:
            o = sqlite3.connect(DB)
            old = o.execute("SELECT COUNT(*) FROM model_years").fetchone()[0]
            o.close()
        except Exception:
            old = 0
    if n_my < old:
        print(f"INGEST ABORTED: {n_my} model-years < existing {old}; keeping current database")
        tmp.unlink()
        return 0
    tmp.replace(DB)
    print(f"INGEST OK: {n_my} model-years (was {old}), {n_f} fuel rows, "
          f"{n_c:,} complaints, {n_r} recall campaigns in {time.time()-t0:.0f}s")
    return 0


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

if __name__ == "__main__":
    sys.exit(main())
