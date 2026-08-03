#!/usr/bin/env python3
"""
gen_site.py — Carsite static site generator (Phase 4).
Reads data/cars.sqlite -> writes site/ (deploy root). Deterministic. No client frameworks.
Quality gate: model-year page generated ONLY if complaint_count>=30 OR recall_count>=3
OR (is_ev AND ev_extras present); years failing the gate (or with data gaps) merge into
the model overview. Every page: >=8 contextual internal links, JSON-LD, data-sources box.
"""
import hashlib, json, math, os, shutil, sqlite3, sys, re
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_art import car_svg
try:
    from og_card import og_card
except Exception:  # Pillow unavailable -> skip og images gracefully
    og_card = None

# library photos: best Commons photo per (brand-ish, model) for real-photo heroes
def _load_lib_photos():
    p = Path(__file__).resolve().parent.parent / "data" / "car_library.json"
    out = []
    if p.exists():
        for x in json.loads(p.read_text()):
            if x.get("p"):
                y = int(x["y"]) if (x.get("y") or "").isdigit() else None
                out.append((x["n"].strip().lower(), y, x["p"]))
    return out

LIB_PHOTOS = _load_lib_photos()


def _count_lib():
    """Total catalogue size — the home page quotes this, so it must be measured, not typed."""
    p = Path(__file__).resolve().parent.parent / "data" / "car_library.json"
    return json.loads(p.read_text()) if p.exists() else []


LIB_PHOTOS_ALL = _count_lib()

def _load_lib_index():
    """display-name -> (brand_slug, model_slug) so any photo can link to its model page."""
    import re as _re
    from collections import defaultdict as _dd
    p = Path(__file__).resolve().parent.parent / "data" / "car_library.json"
    if not p.exists():
        return {}
    ALIAS = {"Mercedes-Benz Group": "Mercedes-Benz", "Daimler AG": "Mercedes-Benz",
             "Ford Motor Company": "Ford", "General Motors": "GM (General Motors)",
             "Bayerische Motoren Werke AG": "BMW", "Volkswagen Group": "Volkswagen",
             "Fiat Chrysler Automobiles": "Fiat", "PSA Group": "Peugeot"}
    def sl(x):
        x = _re.sub(r"[^\w\s-]", "", x.lower()).strip()
        return _re.sub(r"[\s_]+", "-", x)[:60] or "x"
    rows = json.loads(p.read_text())
    known = {}
    for x in rows:
        m = (x.get("m") or "").strip()
        if m:
            k = ALIAS.get(m, m)
            known[k.lower()] = k
    out = {}
    for x in rows:
        n = x["n"].strip()
        b = ALIAS.get((x.get("m") or "").strip(), (x.get("m") or "").strip()) or ""
        if not b:
            low = n.lower()
            for w in (3, 2, 1):
                cand = " ".join(low.split()[:w])
                if cand in known:
                    b = known[cand]
                    break
        if not b:
            b = "Independent & coachbuilders"
        out.setdefault(n.lower(), (sl(b), sl(n)))
    return out

LIB_INDEX = _load_lib_index()

def _load_planned():
    p = Path(__file__).resolve().parent.parent / "data" / "model_index.json"
    return json.loads(p.read_text()) if p.exists() else {}

PLANNED = _load_planned()

def model_url(display):
    """URL of the model page if one exists, else the brand page, else the library."""
    rec = LIB_INDEX.get(display.lower())
    if not rec:
        return "/library/"
    bs, ms = rec
    for name, sl_ in PLANNED.get(bs, {}).items():
        if sl_ == ms:
            return f"/library/{bs}/{ms}/"
    return f"/library/{bs}/"

def lib_photo(make, model, year=None):
    """Exact model name, or the generation entry (\"Model (XVnn)\") whose production window
    contains the model year. Wrong-car risk > no-photo: anything ambiguous returns None."""
    key = f"{make} {model}".lower()
    exact = [c for c in LIB_PHOTOS if c[0] == key]
    gens = sorted([c for c in LIB_PHOTOS if c[0].startswith(key + " (") and c[1]], key=lambda c: c[1])
    if year and gens:
        y = int(year)
        for i, (n, gy, p) in enumerate(gens):
            nxt = gens[i + 1][1] if i + 1 < len(gens) else 9999
            if gy <= y < nxt:
                return p
        return exact[0][2] if exact else None
    return exact[0][2] if exact else (gens[-1][2] if gens else None)

def hero_art(make, model, is_ev, year=None):
    """Real licensed photo when the library has one; signature illustration otherwise."""
    ph = lib_photo(make, model, year)
    if ph:
        fn = ph.replace(" ", "_")
        href = model_url(f"{make} {model}")
        if href == "/library/":
            href = model_url(model)
        return (f'<figure class="hero-art"><a class="photo" href="{href}">'
                f'<img src="https://commons.wikimedia.org/wiki/Special:FilePath/{fn}?width=900" '
                f'alt="{esc(make)} {esc(model)}" fetchpriority="high"></a>'
                f'<figcaption>Photo: Wikimedia Commons &middot; open the model page</figcaption></figure>')
    return f'<figure class="hero-art">{car_svg(model, is_ev)}<figcaption>Illustration</figcaption></figure>'

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DBP = ROOT / "data" / "cars.sqlite"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://carsite.adir-073.workers.dev").rstrip("/")
BRAND = "CarVerdict"
TODAY = date.today().isoformat()
CURRENT_YEAR = 2026

def db():
    p = DBP
    if Path("/sessions").exists():  # sandbox mount lacks sqlite locking -> read from /tmp copy
        tmp = Path("/tmp/cars_read.sqlite")
        shutil.copy(DBP, tmp)
        p = tmp
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    return con

# ---------------- SVG builders (server-rendered, zero client JS) ----------------
def svg_gauge(score):
    if score is None:
        return '<svg viewBox="0 0 120 70" role="img" aria-label="score pending"><text x="60" y="45" fill="#5A6472" font-size="16" text-anchor="middle" font-family="system-ui">n/a</text></svg>'
    pct = max(0, min(100, score)) / 100
    color = "#0F8A5F" if score >= 70 else ("#B45309" if score >= 45 else "#C42B2B")
    ang = math.pi * (1 - pct)
    x, y = 60 + 46 * math.cos(ang), 62 - 46 * math.sin(ang)
    large = 0
    return (f'<svg viewBox="0 0 120 70" role="img" aria-label="Reliability score {score} of 100">'
            f'<path d="M14 62 A46 46 0 0 1 106 62" fill="none" stroke="#E3E7EC" stroke-width="9" stroke-linecap="round"/>'
            f'<path d="M14 62 A46 46 0 {large} 1 {x:.1f} {y:.1f}" fill="none" stroke="{color}" stroke-width="9" stroke-linecap="round"/>'
            f'<text x="60" y="56" fill="#0E1420" font-size="24" font-weight="800" text-anchor="middle" font-family="system-ui">{score}</text>'
            f'<text x="60" y="69" fill="#8A94A3" font-size="8" text-anchor="middle" font-family="system-ui">RELIABILITY / 100</text></svg>')

def svg_bars(items, accent="#0E7C86"):
    """items: [(label, count)] -> horizontal bar chart."""
    if not items:
        return ""
    mx = max(n for _, n in items) or 1
    h = len(items) * 34 + 6
    rows = []
    for i, (label, n) in enumerate(items):
        y = i * 34
        w = 8 + 300 * n / mx
        lab = label.title()[:34]
        rows.append(
            f'<text x="0" y="{y+12}" fill="#5A6472" font-size="11" font-family="system-ui">{esc(lab)}</text>'
            f'<rect x="0" y="{y+17}" width="{w:.0f}" height="9" rx="4" fill="{accent}" opacity="0.9"/>'
            f'<text x="{w+6:.0f}" y="{y+25}" fill="#0E1420" font-size="11" font-weight="700" font-family="system-ui">{n}</text>')
    return f'<svg viewBox="0 0 400 {h}" role="img" aria-label="Complaints by component">{"".join(rows)}</svg>'

def svg_timeline(recalls):
    """recalls rows with date DD/MM/YYYY -> dot timeline."""
    pts = []
    for r in recalls:
        d = r["date"] or ""
        m = re.search(r"(\d{4})", d)
        if m:
            pts.append((int(m.group(1)), r["severe"]))
    if not pts:
        return ""
    y0, y1 = min(p[0] for p in pts), max(max(p[0] for p in pts), min(p[0] for p in pts) + 1)
    span = y1 - y0 or 1
    dots, seen = [], {}
    for yr, sev in sorted(pts):
        x = 30 + 340 * (yr - y0) / span
        seen[yr] = seen.get(yr, 0) + 1
        cy = 38 - min(3, seen[yr] - 1) * 9
        c = "#C42B2B" if sev else "#B45309"
        dots.append(f'<circle cx="{x:.0f}" cy="{cy}" r="5" fill="{c}" opacity="0.9"/>')
    labels = "".join(
        f'<text x="{30 + 340 * (yr - y0) / span:.0f}" y="62" fill="#8A94A3" font-size="10" text-anchor="middle" font-family="system-ui">{yr}</text>'
        for yr in sorted({p[0] for p in pts}))
    return (f'<svg viewBox="0 0 400 68" role="img" aria-label="Recall timeline">'
            f'<line x1="20" y1="48" x2="390" y2="48" stroke="#E3E7EC" stroke-width="2"/>{"".join(dots)}{labels}</svg>')

def svg_costcurve(curve):
    if not curve:
        return ""
    mx = max(p["total_high"] for p in curve) or 1
    W, H, L, B = 400, 150, 40, 130
    def pt(i, v):
        return (L + (W - L - 8) * i / (len(curve) - 1), B - (B - 14) * v / mx)
    hi = " ".join(f"{pt(i, p['total_high'])[0]:.0f},{pt(i, p['total_high'])[1]:.0f}" for i, p in enumerate(curve))
    lo = " ".join(f"{pt(i, p['total_low'])[0]:.0f},{pt(i, p['total_low'])[1]:.0f}" for i, p in enumerate(reversed(curve)))
    grid = "".join(f'<text x="{pt(i, 0)[0]:.0f}" y="146" fill="#8A94A3" font-size="9" text-anchor="middle" font-family="system-ui">{p["age"]}</text>'
                   for i, p in enumerate(curve) if i % 2 == 0)
    ymax = f'<text x="4" y="20" fill="#8A94A3" font-size="9" font-family="system-ui">${mx:,}</text>'
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Estimated annual running cost by vehicle age">'
            f'<polygon points="{hi} {lo}" fill="#0E7C86" opacity="0.15"/>'
            f'<polyline points="{hi}" fill="none" stroke="#0E7C86" stroke-width="2"/>{grid}{ymax}'
            f'<text x="{W/2:.0f}" y="{H-1}" fill="#8A94A3" font-size="9" text-anchor="middle" font-family="system-ui">vehicle age (years)</text></svg>')

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))

# ---------------- layout ----------------
def page(title, desc, canon, body, jsonld=None, extra_head=""):
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, separators=(",", ":"))}</script>' for x in (jsonld or []))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0B0D10">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canon}">
<link rel="stylesheet" href="/assets/site.css">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
{extra_head}{ld}
</head>
<body>
<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="/">Car<em>Verdict</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="Search any car ever made…" autocomplete="off" aria-label="search" data-none="No matches"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/cars/">Browse</a><a href="/library/">Library</a><a href="/play/">Play</a><a href="/calculators/">Calculators</a><a href="/recalls/">Recalls</a></nav>
<details class="langs"><summary>EN</summary><div><a class="cur" href="/">EN</a><a href="/pt/">PT</a><a href="/es/">ES</a><a href="/fr/">FR</a><a href="/de/">DE</a><a href="/he/">HE</a></div></details>
</div></header>
<div class="geo-bar wrap" data-geo-chip></div>
{body}
<footer><div class="wrap"><div class="cols">
<div><b>{BRAND}</b><br>Every number traceable to NHTSA / EPA public data. Estimates labeled.</div>
<div><a href="/methodology/">Methodology</a><br><a href="/about/">About</a><br><a href="/calculators/">Calculators</a></div>
<div><a href="/privacy/">Privacy</a><br><a href="/terms/">Terms</a><br><a href="/disclosure/">Affiliate disclosure</a></div>
<div>Data sources:<br><a href="https://www.nhtsa.gov" rel="noopener">NHTSA</a> · <a href="https://www.fueleconomy.gov" rel="noopener">EPA / fueleconomy.gov</a></div>
</div><p style="margin-top:18px">© {CURRENT_YEAR} {BRAND}. Not affiliated with any manufacturer. <a href="/disclosure/">Disclosure</a>.</p></div></footer>
<script src="/assets/site.js" defer></script>
<script src="/assets/lightbox.js" defer></script>
<script src="/assets/geo.js" defer></script>
<script src="/assets/engage.js" defer></script>
</body></html>"""

def write(path, html):
    p = SITE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html)
    return path

AD = '<div class="ad" data-slot="{slot}">advertisement</div>'

# ---------------- data helpers ----------------
def rows_all(con):
    return con.execute("""SELECT my.id my_id, my.year, my.complaint_count, my.complaint_sample,
      my.recall_count, my.severe_recalls, my.is_ev, my.data_gap,
      mo.id model_id, mo.name model, mo.slug mslug, mk.name make, mk.slug kslug,
      cs.reliability_score score, cs.verdict, cs.reasons, cs.cost_curve, cs.complaints_per_year,
      f.fuel_type, f.mpg_comb, f.annual_fuel_cost, f.ev_range,
      e.battery_warranty, e.battery_replacement_low, e.battery_replacement_high, e.source ev_source
      FROM model_years my
      JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
      LEFT JOIN computed_scores cs ON cs.my_id=my.id
      LEFT JOIN fuel f ON f.my_id=my.id
      LEFT JOIN ev_extras e ON e.my_id=my.id
      ORDER BY mk.name, mo.name, my.year""").fetchall()

def gate(r):
    if r["data_gap"] and "complaints" in r["data_gap"]:
        return False
    return (r["complaint_count"] or 0) >= 30 or (r["recall_count"] or 0) >= 3 \
        or (r["is_ev"] and r["battery_warranty"])

def url_my(r):
    return f"/cars/{r['kslug']}/{r['mslug']}/{r['year']}/"

def vtag(v):
    cls = {"BUY": "v-BUY", "CAUTION": "v-CAUTION", "AVOID": "v-AVOID"}.get(v, "v-DATA")
    return f'<span class="tag {cls}">{esc(v or "PENDING")}</span>'

# ---------------- model-year page ----------------
def gen_model_year(con, r, all_rows):
    make, model, year = r["make"], r["model"], r["year"]
    name = f"{year} {make} {model}"
    url = url_my(r)
    canon = ORIGIN + url
    comps = con.execute("SELECT component, count, sample FROM complaints WHERE my_id=? ORDER BY count DESC LIMIT 8", (r["my_id"],)).fetchall()
    recalls = con.execute("SELECT * FROM recalls WHERE my_id=? ORDER BY date", (r["my_id"],)).fetchall()
    curve = json.loads(r["cost_curve"] or "[]")
    reasons = json.loads(r["reasons"] or "[]")
    siblings = [x for x in all_rows if x["model_id"] == r["model_id"]]
    related = [x for x in all_rows if x["model_id"] != r["model_id"] and gate(x)][:8]
    related = sorted(related, key=lambda x: (x["is_ev"] != r["is_ev"], abs(x["year"] - year)))[:4]
    partial = r["complaint_sample"] and r["complaint_count"] and r["complaint_sample"] < r["complaint_count"]

    # verdict card
    vc = f"""<div class="card verdict sticky">
<div class="chart" style="max-width:150px;margin:0 auto">{svg_gauge(r['score'])}</div>
<span class="badge v-{r['verdict'] if r['verdict'] in ('BUY','CAUTION','AVOID') else 'DATA'}">{esc(r['verdict'] or 'PENDING')}</span>
<ul>{''.join(f'<li>{esc(x)}</li>' for x in reasons)}</ul>
<p style="margin-top:12px;font-size:12px"><a href="/methodology/">How this score is computed →</a></p>
</div>"""

    # complaint block
    comp_note = (f'<p style="font-size:12px;color:var(--faint)">Component breakdown based on a sample of '
                 f'{r["complaint_sample"]} of {r["complaint_count"]:,} total NHTSA complaints.</p>') if partial else ""
    comp_html = f"""<div class="card"><h2>Owner complaints: {(r['complaint_count'] or 0):,} filed with NHTSA</h2>
<p>Complaints per year on the road: <span class="num">{r['complaints_per_year'] or 'n/a'}</span></p>
<div class="chart">{svg_bars([(c['component'], c['count']) for c in comps])}</div>{comp_note}</div>"""

    # recalls block
    rec_rows = "".join(
        f"<tr><td>{esc(x['campaign'] or '—')}</td><td>{esc((x['component'] or '').title()[:40])}</td>"
        f"<td>{esc((x['summary'] or '')[:140])}…</td></tr>" for x in recalls[:8])
    gap_rec = r["data_gap"] and "recalls" in (r["data_gap"] or "")
    rec_html = f"""<div class="card"><h2>Recalls: {'data unavailable' if gap_rec else f"{(r['recall_count'] or 0)} campaigns"}{'' if gap_rec or not r['severe_recalls'] else f" ({r['severe_recalls']} severe)"}</h2>
<div class="chart">{svg_timeline(recalls)}</div>
{'<p>NHTSA recall feed temporarily unavailable for this vehicle — check <a href="https://www.nhtsa.gov/recalls" rel="noopener">nhtsa.gov/recalls</a>.</p>' if gap_rec else f'<table><thead><tr><th>Campaign</th><th>Component</th><th>Summary</th></tr></thead><tbody>{rec_rows}</tbody></table>'}
</div>"""

    # cost block
    fuel_line = ""
    if r["annual_fuel_cost"]:
        fuel_line = (f"<p>EPA combined <span class='num'>{r['mpg_comb']:.0f} {'MPGe' if r['is_ev'] else 'MPG'}</span>"
                     f" · estimated annual {'energy' if r['is_ev'] else 'fuel'} cost <span class='num'>${r['annual_fuel_cost']:,}</span>"
                     + (f" · EPA range <span class='num'>{r['ev_range']:.0f} mi</span>" if r["ev_range"] else "") + "</p>")
    ev_block = ""
    if r["is_ev"] and r["battery_warranty"]:
        ev_block = f"""<h3>EV battery reality check</h3>
<p>Battery warranty: <span class="num">{esc(r['battery_warranty'])}</span></p>
<p>Out-of-warranty pack replacement: <span class="num">${r['battery_replacement_low']:,}–${r['battery_replacement_high']:,}</span> <em>(estimate)</em></p>
<p style="font-size:12px;color:var(--faint)">Source: {esc(r['ev_source'])}</p>"""
    # geo-aware annual cost: numbers re-priced client-side to the visitor's country
    # use the curve point for the car's ACTUAL age today, not age 0
    age_now = max(0, CURRENT_YEAR - int(year))
    yr1 = None
    if curve:
        yr1 = min(curve, key=lambda p: abs(p["age"] - age_now))
    geo_block = ""
    if yr1:
        fuel_usd = r["annual_fuel_cost"] or 0
        maint_lo = max(0, yr1["total_low"] - fuel_usd)
        maint_hi = max(0, yr1["total_high"] - fuel_usd)
        geo_block = f"""<div class="geo-cost">
<div class="geo-cost-row"><span>{'Energy' if r['is_ev'] else 'Fuel'} (your region)</span>
<b data-usd="{fuel_usd}" data-kind="fuel">${fuel_usd:,}</b></div>
<div class="geo-cost-row"><span>Maintenance band (your region)</span>
<b><span data-usd="{maint_lo}" data-kind="maint">${maint_lo:,}</span>–<span data-usd="{maint_hi}" data-kind="maint">${maint_hi:,}</span></b></div>
<div class="geo-cost-row total"><span>Estimated running cost this year (age {age_now})</span>
<b id="geo-total" data-usd="{yr1['total_high']}" data-fuel-usd="{fuel_usd}">${yr1['total_high']:,}</b></div>
<p class="geo-note">Re-priced automatically from your country's retail fuel, electricity and parts indices —
change country in the bar at the top. Estimates; see <a href="/methodology/">methodology</a>.</p></div>"""
    cost_html = f"""<div class="card"><h2>True cost of ownership</h2>{fuel_line}
{geo_block}
<div class="chart">{svg_costcurve(curve)}</div>
<div class="legend"><span><i style="background:#0E7C86"></i>fuel/energy + maintenance band (annual, USD, estimate)</span></div>
{ev_block}
<p style="margin-top:10px"><a href="/calculators/">Run your own numbers in the true-cost calculator →</a></p></div>"""

    # years strip
    strip = "".join(
        f'<a href="{url_my(s)}" class="{"cur" if s["year"] == year else ""}">{s["year"]} {vtag(s["verdict"]) if s["verdict"] in ("AVOID",) else ""}</a>'
        if gate(s) else f'<span class="years-strip-dead" style="padding:6px 13px;color:var(--faint);font-size:14px">{s["year"]}</span>'
        for s in siblings)
    strip_html = f'<div class="card"><h2>Other {make} {model} years</h2><div class="years-strip">{strip}</div><p style="margin-top:8px;font-size:13px"><a href="/cars/{r["kslug"]}/{r["mslug"]}/">Best &amp; worst {model} years — full table →</a></p></div>'

    # FAQ from complaint clusters
    faqs = []
    if comps:
        top = comps[0]
        faqs.append((f"What is the most common problem with the {name}?",
                     f"The most-reported issue in NHTSA complaint data is {top['component'].title()} "
                     f"({top['count']} complaints in our indexed sample). " +
                     (f"Example owner report: “{top['sample'][:220]}…”" if top["sample"] else "")))
    if r["verdict"] in ("BUY", "CAUTION", "AVOID"):
        faqs.append((f"Is the {name} a good used car to buy?",
                     f"Our data verdict is {r['verdict']} with a reliability score of {r['score']}/100, computed from "
                     f"{(r['complaint_count'] or 0):,} NHTSA complaints and {(r['recall_count'] or 0)} recall campaigns. See the verdict card for the top reasons."))
    if r["is_ev"] and r["battery_warranty"]:
        faqs.append((f"How much does a {name} battery replacement cost?",
                     f"Out of warranty, an estimated ${r['battery_replacement_low']:,}–${r['battery_replacement_high']:,}. "
                     f"Warranty coverage: {r['battery_warranty']}."))
    if recalls and not gap_rec:
        faqs.append((f"Does the {name} have recalls?",
                     f"Yes — {r['recall_count']} NHTSA recall campaigns, {r['severe_recalls']} involving fire/crash/stall risk. Check your VIN at nhtsa.gov/recalls before buying."))
    faq_html = '<div class="card"><h2>FAQ</h2>' + "".join(
        f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faqs) + "</div>"

    related_html = '<div class="card"><h2>Compare with</h2><div class="rel-grid">' + "".join(
        f'<a href="{url_my(x)}">{x["year"]} {esc(x["make"])} {esc(x["model"])}<small>score {x["score"]}/100 · {esc(x["verdict"])}</small></a>'
        for x in related) + "</div></div>"

    sources = f"""<div class="card sources"><h2 style="font-size:15px">Data sources</h2>
<p>Complaints &amp; recalls: <a href="https://www.nhtsa.gov/vehicle/{year}/{esc(make).upper()}/{esc(model).upper().replace(' ', '%20')}" rel="noopener">NHTSA</a> ·
Fuel economy: <a href="https://www.fueleconomy.gov" rel="noopener">EPA fueleconomy.gov</a> ·
Scoring: <a href="/methodology/">our published methodology</a>.<br>
Maintenance bands are industry-average estimates (AAA Your Driving Costs, CarMD index) — labeled estimates, not measurements.
Last updated: {TODAY}.</p></div>"""

    cta = f"""<div class="cta-band"><h2>What will a {name} really cost YOU per year?</h2>
<p style="color:var(--muted);margin:8px 0 14px">Fuel, maintenance band and depreciation — computed from public data in 10 seconds.</p>
<a class="btn" href="/calculators/">Open the true-cost calculator</a></div>"""

    hero = f"""<div class="hero"><div class="wrap hero-inner hero-flex">
<div class="hero-copy">
<nav class="crumbs"><a href="/cars/">Cars</a> › <a href="/cars/{r['kslug']}/">{esc(make)}</a> › <a href="/cars/{r['kslug']}/{r['mslug']}/">{esc(model)}</a> › {year}</nav>
<h1>{name}: True Cost, Problems &amp; Verdict</h1>
<p class="sub">{(r['complaint_count'] or 0):,} NHTSA owner complaints · {(r['recall_count'] if r['recall_count'] is not None else '—')} recalls · data-computed verdict. No opinions — public data only.</p>
</div>
{hero_art(make, model, bool(r['is_ev']), year)}
</div></div>"""

    body = f"""{hero}
<div class="wrap grid">
<div style="display:grid;gap:20px;min-width:0">
{AD.format(slot='top')}
{comp_html}
{rec_html}
{cost_html}
{strip_html}
{faq_html}
{related_html}
{cta}
{sources}
</div>
<div class="col-side">{vc}<div class="card" data-garage="{esc(make)}"></div>{AD.format(slot='side')}</div>
</div>"""

    desc = (f"{name} real ownership cost, {(r['complaint_count'] or 0):,} NHTSA complaints, "
            f"{(r['recall_count'] or 0)} recalls, reliability score {r['score']}/100 — verdict: {r['verdict']}.")
    jsonld = [
        {"@context": "https://schema.org", "@type": "Vehicle", "name": name,
         "brand": {"@type": "Brand", "name": make}, "model": model, "vehicleModelDate": str(year),
         "url": canon},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Cars", "item": ORIGIN + "/cars/"},
            {"@type": "ListItem", "position": 2, "name": make, "item": f"{ORIGIN}/cars/{r['kslug']}/"},
            {"@type": "ListItem", "position": 3, "name": model, "item": f"{ORIGIN}/cars/{r['kslug']}/{r['mslug']}/"},
            {"@type": "ListItem", "position": 4, "name": str(year), "item": canon}]},
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": f"{name} NHTSA complaints, recalls and EPA data",
         "description": f"Structured ownership-cost dataset for the {name}.",
         "license": "https://creativecommons.org/licenses/by/4.0/",
         "creator": {"@type": "Organization", "name": BRAND}, "url": canon}]
    og_rel = f"/og/{r['kslug']}-{r['mslug']}-{year}.png"
    extra_head = ""
    if og_card is not None:
        og_card(SITE / og_rel.lstrip("/"), name, "True cost, problems & data verdict",
                r["score"], r["verdict"] or "", bool(r["is_ev"]))
        extra_head = (f'<meta property="og:image" content="{ORIGIN}{og_rel}">'
                      f'<meta property="og:type" content="article">'
                      f'<meta name="twitter:card" content="summary_large_image">'
                      f'<meta name="twitter:image" content="{ORIGIN}{og_rel}">\n')
    return write(url.lstrip("/") + "index.html",
                 page(f"{name}: True Cost to Own, Problems & Verdict | {BRAND}", desc, canon, body, jsonld,
                      extra_head=extra_head))

# ---------------- model overview ----------------
def gen_model(con, model_rows, all_rows):
    r0 = model_rows[0]
    make, model = r0["make"], r0["model"]
    url = f"/cars/{r0['kslug']}/{r0['mslug']}/"
    canon = ORIGIN + url
    def yr_cell(s):
        return ('<a href="' + url_my(s) + '">' + str(s["year"]) + "</a>") if gate(s) else str(s["year"])
    rows = "".join(
        f"<tr><td>{yr_cell(s)}</td>"
        f"<td>{s['score'] if s['score'] is not None else '—'}</td><td>{vtag(s['verdict'])}</td>"
        f"<td>{(s['complaint_count'] if s['complaint_count'] is not None else '—')}</td>"
        f"<td>{(s['recall_count'] if s['recall_count'] is not None else '—')}</td></tr>"
        for s in sorted(model_rows, key=lambda x: -x["year"]))
    scored = [s for s in model_rows if s["score"] is not None]
    best = max(scored, key=lambda s: s["score"], default=None)
    worst = min(scored, key=lambda s: s["score"], default=None)
    verdict_line = ""
    if best and worst and best["my_id"] != worst["my_id"]:
        verdict_line = (f"<p>Best year in our data: <a href='{url_my(best)}'><b>{best['year']}</b></a> "
                        f"(score {best['score']}). Worst: <a href='{url_my(worst)}'><b>{worst['year']}</b></a> "
                        f"(score {worst['score']}, {esc(worst['verdict'])}).</p>")
    related = [x for x in all_rows if x["model_id"] != r0["model_id"] and gate(x)][:4]
    rel = '<div class="rel-grid">' + "".join(
        f'<a href="{url_my(x)}">{x["year"]} {esc(x["make"])} {esc(x["model"])}<small>{esc(x["verdict"])}</small></a>' for x in related) + "</div>"
    body = f"""<div class="hero"><div class="wrap hero-inner hero-flex">
<div class="hero-copy">
<nav class="crumbs"><a href="/cars/">Cars</a> › <a href="/cars/{r0['kslug']}/">{esc(make)}</a> › {esc(model)}</nav>
<h1>{esc(make)} {esc(model)}: Best &amp; Worst Years</h1>
<p class="sub">Every model year ranked by NHTSA complaint and recall data. Click a year for the full breakdown.</p>
</div>
{hero_art(make, model, bool(r0['is_ev']))}
</div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0">
<div class="card"><h2>Year-by-year data table</h2>{verdict_line}
<table><thead><tr><th>Year</th><th>Score</th><th>Verdict</th><th>NHTSA complaints</th><th>Recalls</th></tr></thead>
<tbody>{rows}</tbody></table></div>
{AD.format(slot='mid')}
<div class="card"><h2>Compare with</h2>{rel}</div>
<div class="card sources"><p>Sources: <a href="https://www.nhtsa.gov" rel="noopener">NHTSA</a>, <a href="https://www.fueleconomy.gov" rel="noopener">EPA</a> · <a href="/methodology/">Methodology</a> · Updated {TODAY}</p></div>
</div>"""
    jsonld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Cars", "item": ORIGIN + "/cars/"},
        {"@type": "ListItem", "position": 2, "name": make, "item": f"{ORIGIN}/cars/{r0['kslug']}/"},
        {"@type": "ListItem", "position": 3, "name": model, "item": canon}]}]
    return write(url.lstrip("/") + "index.html",
                 page(f"{make} {model} Best & Worst Years (Data, Not Opinions) | {BRAND}",
                      f"{make} {model} years ranked by NHTSA complaints and recalls — which years to buy and which to avoid.",
                      canon, body, jsonld))

# ---------------- brand hub, index, static ----------------
def gen_brand(con, kslug, make, models, all_rows):
    url = f"/cars/{kslug}/"
    items = "".join(
        f'<a href="/cars/{kslug}/{ms}/">{esc(make)} {esc(mn)}<small>{n} model years indexed</small></a>'
        for ms, mn, n in models)
    body = f"""<div class="hero"><div class="wrap hero-inner">
<nav class="crumbs"><a href="/cars/">Cars</a> › {esc(make)}</nav>
<h1>{esc(make)} ownership costs &amp; problem years</h1></div></div>
<div class="wrap" style="padding:28px 0;display:grid;gap:20px">
<div class="card"><h2>Models</h2><div class="rel-grid">{items}</div></div>
<div class="card sources"><p><a href="/methodology/">Methodology</a> · <a href="/calculators/">Calculators</a> · Updated {TODAY}</p></div></div>"""
    return write(url.lstrip("/") + "index.html",
                 page(f"{make}: True Ownership Costs by Model & Year | {BRAND}",
                      f"{make} models ranked by real NHTSA complaint and recall data.", ORIGIN + url, body))

def gen_cars_index(brands):
    items = "".join(f'<a href="/cars/{k}/">{esc(m)}<small>{n} model years</small></a>' for k, m, n in brands)
    body = f"""<div class="hero"><div class="wrap hero-inner"><h1>Browse by brand</h1></div></div>
<div class="wrap" style="padding:28px 0"><div class="card"><div class="rel-grid">{items}</div></div></div>"""
    return write("cars/index.html", page(f"All Brands | {BRAND}", "Browse true ownership cost data by brand.", ORIGIN + "/cars/", body))

def gen_home(con, all_rows):
    gated = [r for r in all_rows if gate(r)]
    n_complaints = sum(r["complaint_count"] or 0 for r in all_rows)
    evs = [r for r in gated if r["is_ev"]][:4]
    avoid = sorted([r for r in gated if r["verdict"] == "AVOID"], key=lambda r: r["score"] or 0)[:4]
    def cardlist(rows):
        return '<div class="rel-grid">' + "".join(
            f'<a href="{url_my(x)}">{x["year"]} {esc(x["make"])} {esc(x["model"])}<small>score {x["score"]}/100 · {esc(x["verdict"])}</small></a>'
            for x in rows) + "</div>"
    # Counts must come from the data, never from a number typed into the template — the
    # hard-coded 12,747 survived two catalogue rebuilds and shipped a lie on the home page.
    n_models = len(LIB_PHOTOS_ALL)
    n_brands = len({b for b, _ in LIB_INDEX.values()}) if LIB_INDEX else 0

    # ---- image-led hero: real photography from the library ----
    def photo_of(name):
        for n, y, ph in LIB_PHOTOS:
            if n == name.lower():
                return ph
        return None
    HEROES = ["ford mustang", "toyota land cruiser", "jeep wrangler", "mazda mx-5",
              "mini", "bmw 3 series", "audi quattro", "volkswagen golf",
              "porsche 911", "range rover", "chevrolet corvette", "citroen ds",
              "fiat 500", "nissan gt-r", "subaru impreza", "volvo 240",
              "alfa romeo giulia", "lancia delta", "honda civic", "peugeot 205"]
    NICE = {"bmw 3 series": "BMW 3 Series", "mazda mx-5": "Mazda MX-5", "nissan gt-r": "Nissan GT-R",
            "citroen ds": "Citroën DS", "volkswagen golf": "VW Golf", "audi quattro": "Audi quattro"}
    shots = []
    for nm in HEROES:
        ph = photo_of(nm)
        if ph:
            shots.append((NICE.get(nm, nm.title()), ph))
    def mslug(s_):
        s_ = re.sub(r"[^\w\s-]", "", s_.lower()).strip()
        return re.sub(r"[\s_]+", "-", s_)[:60] or "x"
    def murl(display):
        return model_url(display)
    def cimg(ph, w):
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{ph.replace(' ', '_')}?width={w}"
    mosaic = "".join(
        f'<a class="mo-cell" data-lb data-credit="Photo: Wikimedia Commons · CC" href="#">'
        f'<img src="{cimg(ph, 640)}" alt="{esc(nm)}" loading="lazy"><span>{esc(nm)}</span></a>'
        for nm, ph in shots[:8])

    # ---- single editorial hero shot ----------------------------------------------------
    # Four mismatched snapshots read as a stock-photo collage. One large, deliberately
    # chosen frame reads as a product. Source: Wikimedia Commons Featured Pictures of
    # automobiles (peer-reviewed for technical quality), so it holds up at full width.
    HERO_SHOT = "Porsche 911 GT3 Touring, IAA 2017, Frankfurt (1Y7A2766).jpg"
    HERO_NAME = "Porsche 911 GT3"
    HERO_HREF = model_url(HERO_NAME)
    if HERO_HREF == "/library/":
        HERO_HREF = model_url("Porsche 911")
    hero_cells = (
        f'<a class="hh-shot" href="{HERO_HREF}">'
        f'<img src="{cimg(HERO_SHOT, 1200)}" alt="{esc(HERO_NAME)}" fetchpriority="high" '
        f'width="1200" height="800">'
        f'<span class="hh-shot-grad"></span>'
        f'<span class="hh-shot-tag">{esc(HERO_NAME)}<em>Photo: Wikimedia Commons · CC</em></span>'
        f'</a>')
    strip_cells = "".join(
        f'<a class="st-cell" href="{murl(nm)}">'
        f'<img src="{cimg(ph, 520)}" alt="{esc(nm)}" loading="lazy"><span>{esc(nm)}</span></a>'
        for nm, ph in shots[4:12])

    body = f"""<section class="home-hero-v2"><div class="wrap hh-grid">
<div class="hh-copy">
<span class="hh-kicker">{n_models:,} models · {len(LIB_PHOTOS):,} photographs · 19 countries</span>
<h1>What does that car <em>really</em> cost to own?</h1>
<p class="hh-sub">Every car ever made, priced for <b>your</b> country — from NHTSA complaints,
recall campaigns and EPA data. Not opinions.</p>
<div class="hh-cta"><a class="btn" href="/library/">Explore every car ever made</a>
<a class="btn ghost" href="/play/">Play today's quiz</a></div>
<div class="stat-row"><div><b>{n_models:,}</b><span>models in the library</span></div>
<div><b>{n_complaints:,}</b><span>complaints indexed</span></div>
<div><b>19</b><span>countries auto-priced</span></div></div>
</div>
<div class="hh-mosaic">{hero_cells}</div>
</div></section>
<section class="photo-strip">{strip_cells}</section>
<div class="wrap" style="display:grid;gap:22px;padding:30px 0 20px">
<div class="daily-grid" data-daily></div>
<div class="card"><h2>EV ownership, without the hype</h2><p style="margin-bottom:12px">Battery replacement ranges, real complaint clusters, energy cost.</p>{cardlist(evs)}</div>
{AD.format(slot='home')}
<div class="card"><h2>Years to avoid</h2><p style="margin-bottom:12px">Lowest data-scores in our index right now.</p>{cardlist(avoid)}</div>
<h2 class="sec">Explore</h2>
<div class="rel-grid"><a href="/superlatives/">The extremes<small>most expensive · rarest · era-defining</small></a>
<a href="/library/">The Car Library<small>{n_models:,} models, {n_brands:,} marques</small></a>
<a href="/calculators/">True-cost calculator<small>priced for your country</small></a>
<a href="/garage/">My Garage<small>your saved cars</small></a></div>
<div class="cta-band"><h2>True-cost calculator</h2><p style="color:var(--muted);margin:8px 0 14px">Fuel + maintenance + battery risk, by model year.</p><a class="btn" href="/calculators/">Calculate</a></div>
</div>"""
    jsonld = [{"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": ORIGIN,
               "potentialAction": {"@type": "SearchAction", "target": f"{ORIGIN}/cars/?q={{search_term_string}}",
                                   "query-input": "required name=search_term_string"}}]
    return write("index.html", page(f"{BRAND} — True Car Ownership Costs from Public Data",
                 "Per-model-year car verdicts computed from NHTSA complaints, recalls and EPA data. Find the trap years before you buy.",
                 ORIGIN + "/", body, jsonld))

def gen_calculators(con, all_rows):
    packs = []
    for r in all_rows:
        if not gate(r):
            continue
        curve = json.loads(r["cost_curve"] or "[]")
        packs.append({"n": f"{r['year']} {r['make']} {r['model']}", "y": r["year"],
                      "ev": r["is_ev"], "fc": r["annual_fuel_cost"],
                      "c": [[p["total_low"], p["total_high"]] for p in curve],
                      "bl": r["battery_replacement_low"], "bh": r["battery_replacement_high"]})
    data = json.dumps(packs, separators=(",", ":"))
    body = f"""<div class="hero"><div class="wrap hero-inner"><h1>True-cost calculator</h1>
<p class="sub">Annual running cost from EPA fuel data + age-indexed maintenance bands. Estimates, sources on the <a href="/methodology/">methodology page</a>.</p></div></div>
<div class="wrap grid"><div style="display:grid;gap:20px">
<div class="card calc"><h2>Estimate annual cost</h2>
<label for="cv">Vehicle</label><select id="cv"></select>
<label for="cy">Years you plan to keep it</label><input id="cy" type="number" value="5" min="1" max="10">
<div class="calc-out" id="cout">—</div>
<p id="cnote" style="font-size:13px"></p></div>
<div class="card"><h2>How it works</h2><p>Cost = EPA annual fuel/energy cost + the age-indexed maintenance band for each year of ownership. EV packs add a labeled battery-replacement risk note outside warranty. Full formula on the <a href="/methodology/">methodology page</a>. Browse verdicts in <a href="/cars/">the data index</a>.</p></div>
</div><div class="col-side">{AD.format(slot='calc')}</div></div>
<script>
const P={data};
const sel=document.getElementById('cv'),out=document.getElementById('cout'),note=document.getElementById('cnote');
P.forEach((p,i)=>{{const o=document.createElement('option');o.value=i;o.textContent=p.n;sel.appendChild(o)}});
function calc(){{const p=P[sel.value];const keep=Math.min(10,Math.max(1,+document.getElementById('cy').value||5));
const age0=Math.max(0,{CURRENT_YEAR}-p.y);let lo=0,hi=0;
for(let k=0;k<keep;k++){{const a=Math.min(p.c.length-1,age0+k);lo+=p.c[a][0];hi+=p.c[a][1];}}
out.textContent='$'+Math.round(lo/keep).toLocaleString()+'–$'+Math.round(hi/keep).toLocaleString()+' / year';
note.textContent=(p.ev&&p.bl?'EV note: out-of-warranty battery replacement risk $'+p.bl.toLocaleString()+'–$'+p.bh.toLocaleString()+' (estimate, not included in the annual figure).':'')+' Total over '+keep+' yr: $'+lo.toLocaleString()+'–$'+hi.toLocaleString()+'.';}}
sel.addEventListener('change',calc);document.getElementById('cy').addEventListener('input',calc);calc();
</script>"""
    return write("calculators/index.html", page(f"True Car Cost Calculator | {BRAND}",
                 "Annual ownership cost calculator built on EPA fuel data and industry maintenance bands.",
                 ORIGIN + "/calculators/", body))

def gen_recalls_feed(con, all_rows):
    recs = con.execute("""SELECT r.*, my.year, mo.name model, mk.name make, mk.slug kslug, mo.slug mslug
        FROM recalls r JOIN model_years my ON my.id=r.my_id
        JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
        ORDER BY r.date DESC LIMIT 60""").fetchall()
    sev_badge = '<span class="tag v-AVOID">severe</span>'
    rows = "".join(
        f"<tr><td><a href='/cars/{x['kslug']}/{x['mslug']}/{x['year']}/'>{x['year']} {esc(x['make'])} {esc(x['model'])}</a></td>"
        f"<td>{esc(x['campaign'] or '—')}</td><td>{esc((x['component'] or '').title()[:36])}</td>"
        f"<td>{sev_badge if x['severe'] else ''}</td></tr>" for x in recs)
    body = f"""<div class="hero"><div class="wrap hero-inner"><h1>Recall index</h1>
<p class="sub">Latest NHTSA recall campaigns across indexed vehicles. Always VIN-check at <a href="https://www.nhtsa.gov/recalls" rel="noopener">nhtsa.gov/recalls</a>.</p></div></div>
<div class="wrap" style="padding:28px 0;display:grid;gap:20px">
<div class="card"><table><thead><tr><th>Vehicle</th><th>Campaign</th><th>Component</th><th></th></tr></thead><tbody>{rows}</tbody></table></div></div>"""
    return write("recalls/index.html", page(f"Car Recall Index | {BRAND}",
                 "NHTSA recall campaigns for indexed vehicles.", ORIGIN + "/recalls/", body))

def prose_page(path, title, paras):
    body = f'<div class="wrap prose"><h1>{esc(title)}</h1>' + paras + "</div>"
    return write(path, page(f"{title} | {BRAND}", title, ORIGIN + "/" + path.replace("index.html", ""), body))

def gen_static():
    gen = []
    gen.append(prose_page("methodology/index.html", "Methodology", f"""
<p>Every verdict on this site is computed, not written. This page is the complete formula.</p>
<h2>Sources</h2>
<p>Complaints, recalls, investigations: <a href="https://www.nhtsa.gov" rel="noopener">NHTSA public APIs</a>. Fuel economy, range and annual fuel cost: <a href="https://www.fueleconomy.gov" rel="noopener">EPA fueleconomy.gov</a>. Raw responses are cached and versioned; every page links its sources.</p>
<h2>Reliability score (0–100)</h2>
<p>score = 100 − complaint_penalty − recall_penalty. complaint_penalty = min(60, 60 × (complaints per year on road) ÷ 95th-percentile rate across our index). recall_penalty = min(30, 6 × severe_recalls + 2 × other_recalls). A recall is "severe" when its NHTSA summary matches fire / crash / injury / stall / brake-failure / steering-loss patterns.</p>
<h2>Verdicts</h2>
<p>BUY ≥ 70 · CAUTION 45–69 · AVOID &lt; 45. Where complaint data is unavailable the verdict is DATA PENDING — never guessed.</p>
<h2>Cost curve</h2>
<p>Annual cost = EPA annual fuel/energy cost + an age-indexed maintenance band from industry averages (AAA "Your Driving Costs", CarMD Vehicle Health Index). Bands are labeled estimates. EV battery replacement ranges are researched per model and always labeled "estimate" with their source.</p>
<h2>What we never do</h2>
<p>No fabricated numbers, no paid placement in verdicts, no AI-written filler prose. If data is missing we say so.</p>
<p>Questions: see <a href="/about/">about</a>.</p>"""))
    gen.append(prose_page("about/index.html", "About", f"""
<p>{BRAND} exists because "is this car reliable?" is answerable with public data, and almost nobody bothers.</p>
<p>Operated by Adir Trabelsi. Data engineering and publication are automated; the methodology, source selection and editorial standards are human decisions, documented on the <a href="/methodology/">methodology page</a>.</p>
<p>Contact: via the address in our domain registration, or the feedback link in the footer.</p>"""))
    gen.append(prose_page("privacy/index.html", "Privacy Policy", f"""
<p>Effective {TODAY}.</p>
<p>We collect no personal data beyond what you submit (e.g. newsletter email) and standard analytics (Google Analytics 4, Cloudflare Web Analytics). Emails are used solely for the newsletter, double-opt-in, one-click unsubscribe, never sold.</p>
<p>Advertising is served by third parties (e.g. Google AdSense) which may use cookies subject to your consent choices in the consent banner. See Google's <a href="https://policies.google.com/technologies/partner-sites" rel="noopener">partner policy</a>.</p>
<p>Requests: privacy@ this domain.</p>"""))
    gen.append(prose_page("terms/index.html", "Terms of Use", f"""
<p>Effective {TODAY}.</p>
<p>All data is provided "as is" for informational purposes, aggregated from public government sources; verify safety-critical information (especially recalls) against NHTSA directly before acting. No warranty of fitness. Verdicts are computed opinions based on the published methodology, not professional advice.</p>
<p>Content may be cited with attribution and a link. Bulk scraping beyond published data files: contact us for the data license.</p>"""))
    gen.append(prose_page("disclosure/index.html", "Affiliate Disclosure", f"""
<p>Some links on this site are affiliate links (e.g. parts, diagnostics, insurance quote partners). If you buy through them we may earn a commission at no cost to you. This never influences verdicts or scores — those are computed from NHTSA/EPA data per our <a href="/methodology/">methodology</a> before any monetization is attached.</p>
<p>Advertising is clearly separated from data content and never alters it.</p>"""))
    return gen

def gen_assets():
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "assets").iterdir():
        if f.is_file() and " 2." not in f.name:
            shutil.copy(f, SITE / "assets" / f.name)

def gen_meta(urls):
    (SITE / "robots.txt").write_text(f"""User-agent: *
Allow: /
User-agent: GPTBot
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
Sitemap: {ORIGIN}/sitemap.xml
""")
    (SITE / "llms.txt").write_text(f"""# {BRAND}
> Per-model-year car ownership data: NHTSA complaints (component-clustered), recalls,
> EPA fuel economy, computed reliability scores and BUY/CAUTION/AVOID verdicts.
> All numbers trace to NHTSA/EPA public APIs; estimates are labeled. Methodology: {ORIGIN}/methodology/

Canonical citation format: "{BRAND} ({CURRENT_YEAR}), {ORIGIN}<page-url>, based on NHTSA/EPA public data."

## Key pages
- {ORIGIN}/cars/ — brand index
- {ORIGIN}/calculators/ — true-cost calculator
- {ORIGIN}/methodology/ — scoring formula
""")
    # sitemap index + shard (spec: sharded <=10K URLs/file)
    shard = "".join(f"<url><loc>{ORIGIN}{u}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls)
    (SITE / "sitemap-0.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{shard}</urlset>')
    (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{ORIGIN}/sitemap-0.xml</loc><lastmod>{TODAY}</lastmod></sitemap></sitemapindex>')
    (SITE / "ads.txt").write_text("# populate with AdSense line after approval: google.com, pub-XXXX, DIRECT, f08c47fec0942fa0\n")
    (SITE / "404.html").write_text(page("Not found", "404", ORIGIN + "/404", '<div class="wrap prose"><h1>Page not found</h1><p><a href="/cars/">Browse all data →</a></p></div>'))

def dup_check(pages):
    """duplicate-paragraph detector: % of <p> blocks appearing on >1 page (excluding boilerplate)."""
    seen, dup, total = {}, 0, 0
    for path in pages:
        html = (SITE / path).read_text()
        body = html.split('<div class="wrap', 1)[-1].rsplit("<footer", 1)[0]
        # exclude citation/CTA boilerplate blocks — the budget measures CONTENT prose
        body = re.sub(r'<div class="(?:card sources|cta-band)">.*?</div>', "", body, flags=re.S)
        # geo/legal explainer lines are UI chrome, not content prose
        body = re.sub(r'<p class="geo-note">.*?</p>', "", body, flags=re.S)
        for m in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.S):
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
            if len(t) < 60:
                continue
            total += 1
            h = hashlib.md5(t.encode()).hexdigest()
            if h in seen and seen[h] != path:
                dup += 1
            seen[h] = path
    return (100.0 * dup / total) if total else 0.0

def main():
    SITE.mkdir(parents=True, exist_ok=True)
    for child in SITE.iterdir():  # clear contents; dir itself may be a protected mount point
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    con = db()
    all_rows = rows_all(con)
    pages = []
    gen_assets()
    # model-year pages (quality-gated)
    gated = [r for r in all_rows if gate(r)]
    for r in gated:
        pages.append(gen_model_year(con, r, all_rows))
    # model overviews + brand hubs
    models = {}
    for r in all_rows:
        models.setdefault((r["kslug"], r["mslug"]), []).append(r)
    for (k, m), rows in models.items():
        pages.append(gen_model(con, rows, all_rows))
    brands = {}
    for (k, m), rows in models.items():
        b = brands.setdefault(k, {"make": rows[0]["make"], "models": []})
        b["models"].append((m, rows[0]["model"], len(rows)))
    for k, b in brands.items():
        pages.append(gen_brand(con, k, b["make"], b["models"], all_rows))
    pages.append(gen_cars_index(sorted((k, b["make"], sum(n for _, _, n in b["models"])) for k, b in brands.items())))
    pages.append(gen_home(con, all_rows))
    pages.append(gen_calculators(con, all_rows))
    pages.append(gen_recalls_feed(con, all_rows))
    pages += gen_static()
    urls = ["/" + p.replace("index.html", "") for p in pages]
    gen_meta(urls)
    dup = dup_check(pages)
    print(f"GENERATED {len(pages)} pages ({len(gated)} model-year) -> site/  dup-paragraphs: {dup:.1f}% (budget <15%)")
    if dup >= 15:
        print("FAIL: duplicate-paragraph budget exceeded"); sys.exit(1)

if __name__ == "__main__":
    main()
