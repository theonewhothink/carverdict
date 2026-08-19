#!/usr/bin/env python3
"""ingest_scale.py — real NHTSA + EPA data at scale, rebuilt on every deploy.

The problem this fixes: data/cars.sqlite shipped with 16 model-years and 8 fuel rows, so a
site promising "true ownership costs from public data" was running on a seed. The original
ingest worked but was only ever pointed at a handful of cars.

Design: the dataset ACCUMULATES. Every run opens the existing database, plans only
model-years it does not already hold, and merges what it fetches back in. Coverage
therefore grows run over run instead of resetting to whatever one build window could
fetch. A failed fetch costs that model-year this run and nothing else.

This replaces the original "rebuild everything on every deploy" design, which capped the
site permanently: a Cloudflare build has ~20 usable minutes, ~5 of them affordable for
ingestion, which bought about 200 model-years - and because plan() is deterministic, every
single deploy fetched the SAME 200. Fifteen thousand catalogue pages sat on top of an
ownership dataset that could never exceed two hundred rows. Nothing in the design or the
copy fixed that; only persistence does.

Set INGEST_REFRESH=<n> to spend part of the budget re-checking the n stalest model-years
already held, so complaint and recall counts do not go stale as coverage widens.

Sources (all free, all public, no key):
  EPA fueleconomy.gov  menu/make -> menu/model -> menu/options -> vehicle/{id}
                       MPG city/hwy/combined, annual fuel cost, CO2, displacement, drive
  NHTSA api.nhtsa.gov  complaintsByVehicle  -> complaint count + components
                       recallsByVehicle     -> recall count + severity signals

Budget is explicit: MODEL_YEAR_BUDGET caps the run so a deploy cannot hang. Raise it as
build minutes allow; the selection is ordered so the most-searched cars are always covered.
"""
import concurrent.futures as cf
import json, os, re, shutil, sqlite3, sys, time, urllib.parse, urllib.request
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


# The cars people actually search, per marque. With a small budget the round-robin used to
# pick alphabetically - Toyota became the 4Runner and the Camry vanished. Priority names are
# taken first; anything unlisted follows alphabetically after them.
PRIORITY = {
 "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Tacoma", "Prius", "4Runner", "Sienna"],
 "Honda": ["Civic", "Accord", "CR-V", "Pilot", "Odyssey", "HR-V"],
 "Ford": ["F-150", "F150", "Escape", "Explorer", "Mustang", "Focus", "Fusion", "Edge"],
 "Chevrolet": ["Silverado", "Equinox", "Malibu", "Tahoe", "Traverse", "Cruze", "Bolt EV", "Camaro"],
 "Nissan": ["Altima", "Rogue", "Sentra", "Pathfinder", "Frontier", "Leaf", "Murano"],
 "Jeep": ["Grand Cherokee", "Wrangler", "Cherokee", "Compass", "Gladiator"],
 "Subaru": ["Outback", "Forester", "Crosstrek", "Impreza", "Ascent", "WRX"],
 "Hyundai": ["Elantra", "Tucson", "Santa Fe", "Sonata", "Kona", "Palisade"],
 "Kia": ["Sorento", "Sportage", "Telluride", "Forte", "Soul", "Optima"],
 "BMW": ["3 Series", "330i", "X3", "X5", "5 Series", "530i", "X1"],
 "Mercedes-Benz": ["C-Class", "C300", "GLC", "E-Class", "E350", "GLE"],
 "Volkswagen": ["Jetta", "Tiguan", "Atlas", "Golf", "Passat", "ID.4"],
 "Audi": ["Q5", "A4", "Q7", "A6", "Q3"],
 "Lexus": ["RX", "RX 350", "ES", "ES 350", "NX", "GX"],
 "Mazda": ["CX-5", "Mazda3", "3", "CX-9", "CX-30", "MX-5", "MX-5 Miata"],
 "Dodge": ["Charger", "Challenger", "Durango", "Grand Caravan"],
 "Ram": ["1500", "2500", "ProMaster"],
 "GMC": ["Sierra", "Sierra 1500", "Acadia", "Terrain", "Yukon"],
 "Tesla": ["Model 3", "Model Y", "Model S", "Model X"],
 "Volvo": ["XC90", "XC60", "XC40", "S60"],
 "Acura": ["MDX", "RDX", "TLX", "Integra"],
 "Infiniti": ["Q50", "QX60", "QX80"],
 "Cadillac": ["Escalade", "XT5", "CT5"],
 "Buick": ["Enclave", "Encore", "Envision"],
 "Chrysler": ["Pacifica", "300"],
 "Porsche": ["911", "Cayenne", "Macan", "Taycan", "Boxster"],
 "Land Rover": ["Range Rover", "Range Rover Sport", "Defender", "Discovery"],
 "Jaguar": ["F-Pace", "XE", "F-Type"],
 "Mitsubishi": ["Outlander", "Eclipse Cross", "Mirage"],
 "Mini": ["Cooper", "Countryman"],
}


def rank(mk, names):
    """Priority nameplates first (in listed order), then the rest alphabetically."""
    pri = PRIORITY.get(mk, [])

    def key(n):
        for i, want in enumerate(pri):
            if n.lower() == want.lower() or n.lower().startswith(want.lower()):
                return (0, i, n)
        return (1, 0, n)
    return sorted(dict.fromkeys(names), key=key)


def held():
    """(make, model, year) already carrying data, plus the stalest of them.

    Returned lowercase so a name that comes back from EPA with different capitalisation
    than the one already stored does not read as a new car and get fetched twice.
    """
    if not DB.exists():
        return set(), []
    try:
        con = sqlite3.connect(DB)
        con.row_factory = sqlite3.Row
        cols = {r[1] for r in con.execute("PRAGMA table_info(model_years)")}
        order = "my.ingested_at IS NOT NULL, my.ingested_at" if "ingested_at" in cols else "my.id"
        rows = con.execute(f"""SELECT mk.name make, mo.name model, my.year
                               FROM model_years my
                               JOIN models mo ON mo.id = my.model_id
                               JOIN makes mk ON mk.id = mo.make_id
                               ORDER BY {order}""").fetchall()
        con.close()
    except Exception as e:                                    # noqa: BLE001
        print(f"ingest: could not read existing database ({e}); planning from scratch")
        return set(), []
    have = {(r["make"].lower(), r["model"].lower(), r["year"]) for r in rows}
    stale = [{"make": r["make"], "model": r["model"], "year": r["year"]} for r in rows]
    return have, stale


def plan(have=frozenset(), refresh=()):
    """Ask EPA which models actually existed per make-year. Guarantees valid names and
    means we never waste NHTSA calls on a car that was not sold that year.

    `have` is skipped: the budget buys NEW coverage every run. `refresh` is prepended, so
    a slice of each run re-checks rows already held and keeps their counts current."""
    targets = [dict(t) for t in refresh]
    seen = {(t["make"].lower(), t["model"].lower(), t["year"]) for t in targets}
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
            by_make.setdefault(mk, {})[y] = rank(mk, names)
    # round-robin across makes so the budget is not eaten by one manufacturer
    depth = 0
    while len(targets) < MODEL_YEAR_BUDGET and depth < 40:
        added = False
        for mk in MAKES:
            for y in sorted(by_make.get(mk, {}), reverse=True):
                lst = by_make[mk][y]
                if depth < len(lst):
                    key = (mk.lower(), lst[depth].lower(), y)
                    if key not in seen:
                        seen.add(key)
                        added = True
                        if key not in have:          # already in the database: skip, do not refetch
                            targets.append({"make": mk, "model": lst[depth], "year": y})
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
    """Fetch one model-year. Never raises: a single bad response must not kill the run.

    get() returns None on a timeout or an HTTP error, and NHTSA does time out under load.
    Every read of a response is therefore guarded, and the whole body is wrapped so that
    one unlucky model-year costs one row rather than the entire ingest. Before this guard
    a single None response raised AttributeError inside the thread pool, ex.map re-raised
    it in main(), and build.sh swallowed the traceback as "ingest skipped" - so every
    deploy since silently shipped the committed seed database instead of fresh federal data.
    """
    try:
        return _fetch_one(t)
    except Exception as e:                                    # noqa: BLE001 - deliberate
        r = dict(t)
        r["error"] = f"{type(e).__name__}: {e}"[:200]
        return r


def _fetch_one(t):
    mk, mo, yr = urllib.parse.quote(t["make"]), urllib.parse.quote(t["model"]), t["year"]
    row = dict(t)

    c = get(f"{NHTSA}/complaints/complaintsByVehicle?make={mk}&model={mo}&modelYear={yr}")
    results = (c.get("results") or []) if isinstance(c, dict) else []
    comp = {}
    if isinstance(c, dict):
        row["complaints"] = c.get("count") or len(results)
        for r in results:
            for part in (r.get("components") or "").split(","):
                part = part.strip()
                if part:
                    comp[part] = comp.get(part, 0) + 1
    row["components"] = sorted(comp.items(), key=lambda kv: -kv[1])[:6]
    # The narratives are the product: real owners describing real failures, public record.
    # Keep three substantial ones per model-year for the "what owners say" section.
    quotes = []
    for rr in results:
        tx = (rr.get("summary") or "").strip()
        if 120 <= len(tx) <= 900 and not tx.isupper():
            quotes.append(tx[:420])
        elif 120 <= len(tx) <= 900:
            quotes.append(tx[:420].capitalize())
        if len(quotes) == 3:
            break
    row["quotes"] = quotes

    rc = get(f"{NHTSA}/recalls/recallsByVehicle?make={mk}&model={mo}&modelYear={yr}")
    recalls = []
    if isinstance(rc, dict):
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
    if its and isinstance(its[0], dict) and its[0].get("value"):
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
    have, stale = held()
    n_refresh = int(os.environ.get("INGEST_REFRESH", "0"))
    refresh = stale[:max(0, min(n_refresh, MODEL_YEAR_BUDGET // 2))]
    targets = plan(have, refresh)
    print(f"planned {len(targets)} model-years across {len(MAKES)} makes, {YEARS[0]}–{YEARS[-1]} "
          f"({len(have)} already held, {len(refresh)} of them queued for refresh)")
    if not targets:
        print("INGEST: nothing new to fetch at this budget; database unchanged")
        return 0

    rows = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for i, r in enumerate(ex.map(fetch_one, targets), 1):
            rows.append(r)
            if i % 250 == 0:
                print(f"  fetched {i}/{len(targets)}  ({time.time()-t0:.0f}s)")

    errs = [r for r in rows if r.get("error")]
    if errs:
        # Loud, not silent: build.sh swallows a non-zero exit, so the only way a broken
        # ingest gets noticed is if it says so in the build log in plain words.
        kinds = {}
        for r in errs:
            k = r["error"].split(":")[0]
            kinds[k] = kinds.get(k, 0) + 1
        print(f"INGEST WARNING: {len(errs)}/{len(rows)} model-years failed to fetch "
              f"({', '.join(f'{k} x{v}' for k, v in sorted(kinds.items()))}); "
              f"first: {errs[0].get('make')} {errs[0].get('model')} {errs[0].get('year')} "
              f"-> {errs[0]['error']}")

    got = [r for r in rows if r.get("complaints") or r.get("recalls") or r.get("epa")]
    print(f"fetched {len(rows)}; {len(got)} carry data ({time.time()-t0:.0f}s)")
    floor = 50 if not have else max(5, len(targets) // 20)
    if len(got) < floor:
        print(f"INGEST ABORTED: {len(got)} rows carry data, below the floor of {floor}; "
              "keeping the existing database")
        return 0

    tmp = ROOT / "data" / "cars.new.sqlite"
    if tmp.exists():
        tmp.unlink()
    # Start from what is already held. This one line is the difference between a dataset
    # that grows every night and one that is re-fetched from zero on every deploy.
    if DB.exists():
        shutil.copy2(DB, tmp)
    con = sqlite3.connect(tmp)
    con.executescript((ROOT / "scripts" / "schema.sql").read_text()
                      if (ROOT / "scripts" / "schema.sql").exists() else SCHEMA)
    if "ingested_at" not in {r[1] for r in con.execute("PRAGMA table_info(model_years)")}:
        con.execute("ALTER TABLE model_years ADD COLUMN ingested_at TEXT")
    today = time.strftime("%Y-%m-%d")

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
        vals = (r.get("complaints") or 0, r.get("complaints") or 0, len(r["recalls"]), severe,
                is_ev, None if r.get("complaints") is not None else "complaints", today)
        con.execute("""INSERT OR IGNORE INTO model_years
            (model_id,year,complaint_count,complaint_sample,recall_count,severe_recalls,is_ev,data_gap)
            VALUES(?,?,0,0,0,0,?,NULL)""", (mo_id[key], r["year"], is_ev))
        my = con.execute("SELECT id FROM model_years WHERE model_id=? AND year=?",
                         (mo_id[key], r["year"])).fetchone()[0]
        # A refreshed model-year must overwrite, not stack: without this the row keeps its
        # first-ever counts and its complaint and recall children double on every re-fetch.
        con.execute("""UPDATE model_years SET complaint_count=?, complaint_sample=?,
            recall_count=?, severe_recalls=?, is_ev=?, data_gap=?, ingested_at=?
            WHERE id=?""", vals + (my,))
        con.execute("DELETE FROM complaints WHERE my_id=?", (my,))
        con.execute("DELETE FROM recalls WHERE my_id=?", (my,))

        for part, n in r["components"]:
            con.execute("INSERT INTO complaints(my_id,component,count,sample) VALUES(?,?,?,?)",
                        (my, part, n, None))
        for q in r.get("quotes", []):
            con.execute("INSERT INTO complaints(my_id,component,count,sample) VALUES(?,?,?,?)",
                        (my, "__quote__", 0, q))
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
    print(f"INGEST OK: {n_my} model-years (+{n_my - old} this run), {n_f} fuel rows, "
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
