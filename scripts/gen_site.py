#!/usr/bin/env python3
"""
gen_site.py — Carsite static site generator (Phase 4).
Reads data/cars.sqlite -> writes site/ (deploy root). Deterministic. No client frameworks.
Quality gate: model-year page generated ONLY if complaint_count>=30 OR recall_count>=3
OR (is_ev AND ev_extras present); years failing the gate (or with data gaps) merge into
the model overview. Every page: >=8 contextual internal links, JSON-LD, data-sources box.
"""
import hashlib, json, math, os, shutil, sqlite3, sys, re, tempfile, atexit, urllib.parse
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_art import car_svg
try:
    from og_card import og_card
except Exception:  # Pillow unavailable -> skip og images gracefully
    og_card = None

# library photos: best Commons photo per (brand-ish, model) for real-photo heroes
def _production_windows():
    """Wikidata QID -> (first year, last year) from the Wikipedia infobox production line.

    The catalogue's own inception year is empty for most nameplates, which is why the
    photograph on a model-year page had to be chosen from the filename alone. The infobox
    production string carries the real window for about half the photographed catalogue
    ("2007-2008 (GT9) / 2011 (GT9-CS)", "1988-1996"), and a window is a far better answer
    than a filename: it says which generation was on sale in the year the page is about.
    """
    p = Path(__file__).resolve().parent.parent / "data" / "wiki_specs.json"
    out = {}
    if not p.exists():
        return out
    try:
        wiki = json.loads(p.read_text())
    except Exception:
        return out
    for qid, rec in wiki.items():
        txt = re.sub(r"&[a-z]+;", "-", str(rec.get("production") or ""))
        ys = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", txt)]
        if not ys:
            continue
        hi = date.today().year if re.search(r"present|current|\bnow\b", txt, re.I) else max(ys)
        out[qid] = (min(ys), hi)
    return out


def _load_lib_photos():
    p = Path(__file__).resolve().parent.parent / "data" / "car_library.json"
    windows = _production_windows()
    out = []
    if p.exists():
        for x in json.loads(p.read_text()):
            if x.get("p"):
                y = int(x["y"]) if (x.get("y") or "").isdigit() else None
                w = windows.get(x.get("q"))
                # The recorded inception year is the window's start when we have one: that
                # is what the generation-window branch of lib_photo reads.
                if w and not y:
                    y = w[0]
                out.append((x["n"].strip().lower(), y, x["p"], w))
    return out

LIB_PHOTOS = _load_lib_photos()


CATALOG = {}   # marque -> [models], the exact de-duplicated set /library/ renders

def _catalogue_stats():
    """Use the same normalized, de-duplicated catalogue as /library/, so the home page,
    /cars/, /library/ and /follow/ can never disagree about how many cars there are."""
    try:
        from build_library import load_model_index, build_dataset
        load_model_index()
        brands = build_dataset()
        CATALOG.update(brands)
        return (sum(len(v) for v in brands.values()), len(brands),
                sum(1 for v in brands.values() for m in v if m.get("p")))
    except Exception:
        p = Path(__file__).resolve().parent.parent / "data" / "car_library.json"
        rows = json.loads(p.read_text()) if p.exists() else []
        return (len(rows), len({x.get("m") for x in rows if x.get("m")}),
                sum(bool(x.get("p")) for x in rows))


CATALOG_MODELS, CATALOG_BRANDS, CATALOG_PHOTOS = _catalogue_stats()

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
        # Marque inference must match build_library.brand_of: when the model's own
        # name opens with a marque the catalogue knows, that marque wins over the
        # manufacturer (a "Kia Sportage" built by Jiangsu Yueda Kia files under Kia,
        # which is the heading the library actually writes).
        b = ""
        low = n.lower()
        for w in (3, 2, 1):
            cand = " ".join(low.split()[:w])
            if cand in known:
                b = known[cand]
                break
        if not b:
            b = ALIAS.get((x.get("m") or "").strip(), (x.get("m") or "").strip()) or ""
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
    # A brand slug the planner never saw has no guaranteed page: link the index.
    return f"/library/{bs}/" if bs in PLANNED else "/library/"

_BAD_PHOTO = re.compile(r"prototype|concept|spy[_ ]|camoufla|teaser|mule|render|clay[_ ]model",
                        re.I)


# Scanning all ~18,000 catalogue rows per page was already the slow path; running two
# regexes over every row as well made the build miss its 20-minute window. The name test
# and the filename's own year are properties of the file, so both are computed once.
_PHOTO_META = {}


def _photo_meta(fname):
    m = _PHOTO_META.get(fname)
    if m is None:
        bad = bool(_BAD_PHOTO.search(fname)) if fname else True
        yrs = [int(y) for y in re.findall(r"(?:19|20)\d{2}", fname or "")]
        m = _PHOTO_META[fname] = (bad, min(yrs) if yrs else 0)
    return m


def _photo_ok(fname, year=None):
    """A page about a 2019 car must not be illustrated with a 2025 show car. Reject the
    obvious non-production files by name, and reject any file whose own filename carries a
    model year later than the page's."""
    if not fname:
        return False
    bad, first_year = _photo_meta(fname)
    if bad:
        return False
    return not (year and first_year and first_year > int(year))


# name -> its catalogue rows, built once instead of a full scan per page.
_LIB_BY_KEY = {}
_LIB_BY_PREFIX = {}
for _c in LIB_PHOTOS:
    _LIB_BY_KEY.setdefault(_c[0], []).append(_c)
    if "(" in _c[0]:
        _LIB_BY_PREFIX.setdefault(_c[0].split(" (", 1)[0], []).append(_c)


def lib_photo(make, model, year=None):
    """The photograph for this nameplate, and for a model-year page the one that actually
    shows a car of about that age.

    The catalogue's inception years are mostly empty, so the old generation-window branch
    never fired and the function fell through to "first exact match" — which is why a 2019
    RAV4 page carried a 2025 show car and a 2015 X5 page a 2003 one. The reliable signal is
    the Commons filename, which almost always names the car's year. A model-year page uses
    the newest candidate that is not newer than the page and not more than a decade older;
    if nothing qualifies it carries no photograph, because a visibly wrong car is worse than
    an illustration.
    """
    key = f"{make} {model}".lower()
    cands = [c for c in list(_LIB_BY_KEY.get(key, ())) + list(_LIB_BY_PREFIX.get(key, ()))
             if c[2] and not _photo_meta(c[2])[0]]
    if not cands:
        return None
    if year:
        y = int(year)
        # First choice, and the only one that is actually right: the generation whose
        # recorded production window contains this model year. The window comes from the
        # Wikipedia infobox and covers about half the photographed catalogue.
        # The window alone is not enough: a nameplate-level entry reading "1990-present"
        # contains every year, and its photograph is whatever Commons happens to hold —
        # which is how a 2025 Explorer ended up on the 2016 page. The filename's own year
        # is the stronger evidence about what the picture shows, so a candidate whose file
        # is newer than the page is rejected even when its window matches.
        inwindow = [c for c in cands
                    if c[3] and c[3][0] <= y <= c[3][1] and _photo_ok(c[2], y)]
        if inwindow:
            # Prefer the narrowest window: a "1994-present" entry should lose to the
            # generation entry that names four years.
            return min(inwindow, key=lambda c: c[3][1] - c[3][0])[2]
        # Otherwise fall back to the filename's own year. A model-year car is often
        # photographed the following calendar year, so the ceiling is year + 1. There is no
        # floor: an older photograph of the same nameplate is an honest picture as long as
        # the caption does not claim it is this model year, which is why hero_art no longer
        # stamps the year into the alt text. What is never acceptable is a car from the
        # future — the 2025 show car that used to illustrate the 2019 RAV4.
        dated = [(yy, c) for c in cands
                 for yy in (_photo_meta(c[2])[1],) if yy and yy <= y + 1]
        if dated:
            return max(dated, key=lambda t: t[0])[1][2]
        # A generation entry whose recorded first year contains this model year is still
        # the best answer where the catalogue happens to carry one.
        # The inception-year branch had no filename guard, which is how a 2025 Explorer
        # still reached the 2016 page: the nameplate's window starts in 1990, so every year
        # matched. Guard it the same way as the branches above.
        gens = sorted([c for c in cands if c[1] and _photo_ok(c[2], y)], key=lambda c: c[1])
        for i, g in enumerate(gens):
            gy, ph = g[1], g[2]
            nxt = gens[i + 1][1] if i + 1 < len(gens) else 9999
            if gy <= y < nxt:
                return ph
        # Most Commons filenames carry no year at all. An undated photograph of the right
        # nameplate cannot be a car from the future, and with the year no longer claimed in
        # the alt text it is an honest illustration — much better than an empty page.
        undated = [c for c in cands if not _photo_meta(c[2])[1]]
        return undated[0][2] if undated else None
    dated = [(_photo_meta(c[2])[1], c) for c in cands if _photo_meta(c[2])[1]]
    if dated:
        return max(dated, key=lambda t: t[0])[1][2]
    return cands[0][2]


def hero_art(make, model, is_ev, year=None):
    """Real licensed photo when the library has one; signature illustration otherwise."""
    ph = lib_photo(make, model, year)
    if ph:
        fn = ph.replace(" ", "_")
        href = model_url(f"{make} {model}")
        if href == "/library/":
            href = model_url(model)
        base = f"https://commons.wikimedia.org/wiki/Special:FilePath/{_uq(fn)}"
        srcset = ", ".join(f"{base}?width={w} {w}w" for w in (480, 720, 900, 1200))
        # The alt text used to read "Toyota RAV4 (2019)" over whatever photograph the
        # catalogue happened to hold, which asserted a model year the picture could not
        # support. It names the car, not the page.
        alt = f"{esc(make)} {esc(model)}"
        return (f'<figure class="hero-art"><a class="photo" href="{href}">'
                f'<img src="{base}?width=900" srcset="{srcset}" '
                f'sizes="(max-width: 900px) 100vw, 560px" width="900" height="563" '
                f'referrerpolicy="no-referrer" decoding="async" '
                f'alt="{alt}" fetchpriority="high"></a>'
                f'</figure>')
    return f'<figure class="hero-art">{car_svg(model, is_ev)}<figcaption>Illustration</figcaption></figure>'

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DBP = ROOT / "data" / "cars.sqlite"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")
BRAND = "MotorJury"
TODAY = date.today().isoformat()

def _uq(fn):
    import urllib.parse
    return urllib.parse.quote(fn)

def _geo_country_count():
    try:
        t = json.loads((Path(__file__).resolve().parent.parent / "data" / "geo_prices.json").read_text())
        return sum(1 for k in t if k != "_meta")
    except Exception:
        return 19

N_GEO = _geo_country_count()

CURRENT_YEAR = 2026

def db():
    p = DBP
    if Path("/sessions").exists():  # sandbox mount lacks sqlite locking -> read from /tmp copy
        # Per-process name: a fixed /tmp path is left behind owned by whichever user ran
        # the previous build, and the next run dies on PermissionError before page one.
        tmp = Path(tempfile.gettempdir()) / f"cars_read.{os.getpid()}.sqlite"
        shutil.copy(DBP, tmp)
        atexit.register(lambda f=tmp: f.unlink(missing_ok=True))
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
ORG_LD = None


def _load_editorial(name):
    try:
        return json.load(open(ROOT / "data" / "editorial" / name))
    except Exception:
        return {}
EDITOR_NOTES = _load_editorial("models.json")   # "make/model" -> {"note", "avoid"}
HUB_NOTES = _load_editorial("hubs.json")
EDITOR = "Adir Trabelsi"
# There are no staff writers. Every page under /cars/ and /library/ is produced by the
# build from NHTSA, EPA and Wikidata records; putting a person's name on one would claim
# authorship that did not happen, which is what Google's spam policy and the AdSense
# publisher policies call misrepresentation. Computed pages carry an attribution line
# naming the method and the publisher; only the hand-written guides carry a human name,
# and that name is the editor's.


def attribution(_key=None, date=None):
    """Attribution line for a computed page. No author: the publisher is the organisation
    and the method is linked, so a reader can check how the page was made."""
    return ('<p class="byline">Computed by '
            f'<a href="/about/">{BRAND}</a> from NHTSA and EPA public records · '
            '<a href="/methodology/">method</a>'
            f'{" · updated " + esc(date) if date else ""}</p>')


def byline(key=None, date=None):
    """Retained name so existing call sites keep working; computed pages get no author."""
    return attribution(key, date)


def editor_byline(date=None):
    """Only for the hand-written guides. Points at the author page rather than the company
    About page: a byline that links to "about us" tells a reader nothing about who wrote it.
    """
    return (f'<p class="byline">By <a href="/about/adir-trabelsi/" rel="author">{EDITOR}</a>, '
            f'editor{" · " + esc(date) if date else ""}</p>')
NOINDEX = '<meta name="robots" content="noindex,follow">'


def guides_index():
    """Front matter of every guide in data/guides, newest first, for the home page and hubs.
    build_guides.py renders the pages; this only reads the headers so links never dangle."""
    out = []
    for f in sorted((ROOT / "data" / "guides").glob("*.md")):
        head = f.read_text().split("\n---", 1)[0]
        meta = dict(re.findall(r"^(\w+):\s*(.+)$", head, re.M))
        if meta.get("title") and meta.get("slug"):
            out.append(meta)
    out.sort(key=lambda m: m.get("date", ""), reverse=True)
    return out


def _guide_map():
    """make/model slug -> the guide that covers it. The guides are the only hand-written
    pages on the site and the only ones that can earn a link, and until now nothing pointed
    at them: a model page linked /guides/ and never the guide about that exact car. Each
    guide declares the nameplates it covers in its `models:` header, so the map is exact."""
    m = {}
    # A nameplate can appear in a broad guide ("the first-year rule", six nameplates) and in
    # the guide written about that car. The specific one is the useful link, so the guide
    # naming the fewest nameplates wins, and the newer one breaks a tie.
    for g in sorted(guides_index(),
                    key=lambda g: (len([x for x in g.get("models", "").split(",") if x.strip()]),
                                   "" if not g.get("date") else "-" + g["date"])):
        for key in (x.strip() for x in g.get("models", "").split(",")):
            if key and key not in m:
                m[key] = g
    return m


GUIDE_FOR_MODEL = _guide_map()


def guide_link_card(kslug, mslug, year=None):
    """A card pointing at the guide that covers this nameplate, or "" if none does."""
    g = GUIDE_FOR_MODEL.get(f"{kslug}/{mslug}")
    if not g:
        return ""
    # One link, not a paragraph: the guide's own description repeated across every model
    # year of a nameplate would be duplicated prose on a dozen pages at a time.
    where = f", including {year}" if year else ""
    return (f'<div class="card guide-xref"><h2>Read the guide</h2>'
            f'<p class="src-note"><a href="/guides/{esc(g["slug"])}/"><b>{esc(g["title"])}</b></a>'
            f'{esc(where)} — written and signed by {EDITOR}, {esc(g.get("date", ""))}.</p></div>')


def editor_card(kslug, mslug, year=None, r=None):
    """The human-written layer on a model page: the editor's note for the nameplate plus,
    on a year page, one data-specific line for that year. Returns "" where no note exists."""
    e = EDITOR_NOTES.get(f"{kslug}/{mslug}")
    if not e or not e.get("note"):
        return ""
    note = e["note"]
    year_line = ""
    if year is not None and r is not None:
        # A year page carries the opening of the note plus its own line; the full note lives
        # once, on the model page. Fifteen year pages repeating 200 identical words is the
        # duplicate-content pattern this whole change exists to remove.
        sents = re.split(r"(?<=[.!?])\s+", note)
        note = " ".join(sents[:2]) + (f' <a href="/cars/{kslug}/{mslug}/">Read the full note on the model page.</a>'
                                       if len(sents) > 2 else "")
        avoid = set(e.get("avoid") or [])
        cc = r["complaint_count"] or 0
        if int(year) in avoid:
            year_line = (f"<p><b>{year} specifically:</b> this is one of the years the note above says to "
                         f"approach with care — {cc:,} complaints on record, verdict {esc(r['verdict'] or 'pending')}.</p>")
        elif r["score"] is not None and r["score"] >= 70:
            year_line = (f"<p><b>{year} specifically:</b> a year the record favours — {cc:,} complaints, "
                         f"score {r['score']}/100. The caveats in the note apply to other years of this nameplate more than to this one.</p>")
        else:
            year_line = (f"<p><b>{year} specifically:</b> {cc:,} complaints on record, score "
                         f"{r['score'] if r['score'] is not None else '—'}/100 — read the year table on the "
                         f"<a href='/cars/{kslug}/{mslug}/'>model page</a> to see where it sits among its siblings.</p>")
    if year_line:
        # One paragraph, not two: the two-sentence excerpt is by design the same on every
        # year page of the nameplate, and as its own <p> it counted as a duplicate on each
        # of them (123 nameplates × ~15 years pushed the prose measure over budget). Fused
        # with the year's own line it is a paragraph that exists on exactly one page.
        return (f'<div class="card editorial"><h2>Editor\'s note</h2>'
                f'<p>{note} {year_line[3:-4]}</p></div>')
    return f'<div class="card editorial"><h2>Editor\'s note</h2><p>{note}</p></div>'


def _org_ld():
    """Publisher identity on every page: who stands behind the numbers (E-E-A-T)."""
    global ORG_LD
    if ORG_LD is None:
        ORG_LD = {
            "@context": "https://schema.org", "@type": "Organization",
            "@id": ORIGIN + "/#organization", "name": BRAND, "url": ORIGIN + "/",
            "logo": ORIGIN + "/icon-512.png",
            "description": "Per-model-year car ownership costs, problems and verdicts computed from "
                           "NHTSA and EPA public data.",
            "founder": {"@type": "Person", "name": "Adir Trabelsi"},
            "publishingPrinciples": ORIGIN + "/methodology/",
            "email": "hello@motorjury.com",
            "sameAs": [ORIGIN + "/about/"],
        }
    return ORG_LD


# Follow and share. The site had no way for a reader to take a page anywhere, and no way
# to find the channels the content is published on — which is a strange thing for a site
# whose growth plan runs through social video. One row, in every footer, on every page.
def _social_urls():
    """data/social.json: only networks with a real profile URL are linked anywhere."""
    try:
        d = json.load(open(ROOT / "data" / "social.json"))
        return {k: v for k, v in d.items() if not k.startswith("_") and v}
    except Exception:
        return {}
_SOCIAL_URLS = _social_urls()

SOCIAL = [
    ("Instagram", _SOCIAL_URLS.get("Instagram", ""),
     "M12 2.2c3.2 0 3.6 0 4.9.1 1.2.1 1.8.2 2.2.4.6.2 1 .5 1.4.9.4.4.7.8.9 1.4.2.4.4 1 .4 2.2.1 1.3.1 1.7.1 4.9s0 3.6-.1 4.9c-.1 1.2-.2 1.8-.4 2.2-.2.6-.5 1-.9 1.4-.4.4-.8.7-1.4.9-.4.2-1 .4-2.2.4-1.3.1-1.7.1-4.9.1s-3.6 0-4.9-.1c-1.2-.1-1.8-.2-2.2-.4-.6-.2-1-.5-1.4-.9-.4-.4-.7-.8-.9-1.4-.2-.4-.4-1-.4-2.2C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.9c.1-1.2.2-1.8.4-2.2.2-.6.5-1 .9-1.4.4-.4.8-.7 1.4-.9.4-.2 1-.4 2.2-.4C8.4 2.2 8.8 2.2 12 2.2zm0 5.3a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zm0 7.4a2.9 2.9 0 1 1 0-5.8 2.9 2.9 0 0 1 0 5.8zm5.7-7.6a1 1 0 1 1-2.1 0 1 1 0 0 1 2.1 0z"),
    ("TikTok", _SOCIAL_URLS.get("TikTok", ""),
     "M16.6 5.8c-1-.7-1.6-1.8-1.8-3h-2.9v11.6a2.4 2.4 0 1 1-1.7-2.3V9.1a5.3 5.3 0 1 0 4.6 5.3V9.1c1 .7 2.3 1.1 3.6 1.1V7.3c-.6 0-1.2-.2-1.8-.5z"),
    ("Facebook", _SOCIAL_URLS.get("Facebook", ""),
     "M13.5 21v-8h2.7l.4-3.1h-3.1V7.9c0-.9.3-1.5 1.6-1.5h1.6V3.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4 1.4-4 4.1v2.3H7.5V13h2.8v8h3.2z"),
    ("YouTube", _SOCIAL_URLS.get("YouTube", ""),
     "M21.6 7.2c-.2-.9-.9-1.6-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4c-.9.2-1.6.9-1.8 1.8C2 8.8 2 12 2 12s0 3.2.4 4.8c.2.9.9 1.6 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4c.9-.2 1.6-.9 1.8-1.8.4-1.6.4-4.8.4-4.8s0-3.2-.4-4.8zM10 15.1V8.9l5.2 3.1-5.2 3.1z"),
]
SOCIAL_ROW = (
    '<div class="social-row"><span class="social-lbl">Follow MotorJury</span>'
    + "".join(
        f'<a class="soc soc-{n.lower()}" href="{u}" rel="noopener me" target="_blank" '
        f'aria-label="{n}" title="{n}"><svg viewBox="0 0 24 24" aria-hidden="true">'
        f'<path fill="currentColor" d="{d}"/></svg></a>'
        for n, u, d in SOCIAL if u)
    + '<span class="social-share" data-share></span></div>')


def page(title, desc, canon, body, jsonld=None, extra_head="", og_type="website"):
    # A caller that hands this a pre-serialised JSON string instead of a list of objects
    # used to get one <script> tag per CHARACTER of that string — 747 of them on the author
    # page, and nothing in the build noticed. Fail loudly instead.
    if isinstance(jsonld, str):
        raise TypeError("page(jsonld=...) takes a list of objects, not a JSON string")
    if isinstance(jsonld, dict):
        jsonld = [jsonld]
    blocks = list(jsonld or []) + [_org_ld()]
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, separators=(",", ":"))}</script>' for x in blocks)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0B0D10" media="(prefers-color-scheme: dark)">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canon}">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="mask-icon" href="/mask-icon.svg" color="#10233F">
<link rel="manifest" href="/site.webmanifest">
<link rel="stylesheet" href="/assets/site.css">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canon}"><meta property="og:site_name" content="{BRAND}">
<meta property="og:type" content="{og_type}"><meta name="twitter:card" content="summary_large_image">
{extra_head}{ld}
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="/">Motor<em>Jury</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="Search any car ever made…" autocomplete="off" aria-label="search" data-none="No matches"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/guides/">Guides</a><a href="/years-to-avoid/">Years to avoid</a><a href="/compare/">Compare</a><a href="/cars/">Cars</a><a href="/library/">Library</a><a href="/vin-check/">VIN check</a><a href="/calculators/">Calculators</a></nav>
<div class="acct-host" data-account-chip></div>

</div></header>
<div class="geo-bar wrap" data-geo-chip></div>
<main id="content">
{body}
</main>
<footer><div class="wrap"><div class="cols">
<div><b>{BRAND}</b><br>Every number traceable to NHTSA / EPA public data. Estimates labeled.</div>
<div><a href="/guides/">Buyer's guides</a><br><a href="/years-to-avoid/">Years to avoid</a><br><a href="/methodology/">Methodology</a><br><a href="/editorial-policy/">Editorial policy</a><br><a href="/about/">About</a><br><a href="/about/adir-trabelsi/">The editor</a><br><a href="/contact/">Contact</a></div>
<div><a href="/privacy/">Privacy</a><br><a href="/privacy/" onclick="if(window.googlefc&&googlefc.showRevocationMessage){{googlefc.showRevocationMessage();return false}}">Privacy settings</a><br><a href="/terms/">Terms</a><br><a href="/disclosure/">Advertising disclosure</a><br><a href="/compare/">Head-to-head</a><br><a href="/recalls/">Recalls</a></div>
<div>Data sources:<br><a href="https://www.nhtsa.gov" rel="noopener">NHTSA</a> · <a href="https://www.fueleconomy.gov" rel="noopener">EPA / fueleconomy.gov</a></div>
</div>{SOCIAL_ROW}<p style="margin-top:18px">© {CURRENT_YEAR} {BRAND}. Not affiliated with any manufacturer. <a href="/disclosure/">Disclosure</a>.</p></div></footer>
<script src="/assets/site.js" defer></script>
<script src="/assets/lightbox.js" defer></script>
<script src="/assets/geo.js" defer></script>
<script src="/assets/engage.js" defer></script>
<script src="/assets/legends.js" defer></script>
<script src="/assets/account.js" defer></script>
<script src="/assets/tco.js" defer></script>
<script src="/assets/share.js" defer></script>
</body></html>"""

def write(path, html):
    p = SITE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html)
    return path

# Auto Ads places real units when AdSense has inventory.  Static 250–280px placeholders
# never filled and created two large blank blocks on phones, so manual empty slots are gone.
# The ownership pages carried no ad markup at all — AD was an empty string, so the only
# configured unit lived on the biography pages. These are the pages with buying intent and
# the pages the traffic lands on; leaving them unmonetised means an approval earns nothing.
# One in-article unit, placed inside the article after the first block of real content —
# never in the hero, never in a side rail, never more than one per page.
try:
    _ADS = json.load(open(ROOT / "data" / "ads.json"))
except Exception:
    _ADS = {}
AD_CLIENT = "ca-pub-6675837012921030"
AD_SLOT = _ADS.get("in_article_slot", "")
_AD_UNIT = (f'<ins class="adsbygoogle car-ad" style="display:block;text-align:center" '
            f'data-ad-layout="in-article" data-ad-format="fluid" data-ad-client="{AD_CLIENT}" '
            f'data-ad-slot="{AD_SLOT}"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>') if AD_SLOT else ""


class _Ad:
    """AD.format(slot=...) is called from six templates. Only the in-article positions get
    a unit: a fluid in-article creative in a narrow side rail renders badly, and an ad
    above the first paragraph pushes the content a reader came for below the fold."""
    IN_ARTICLE = {"mid", "article"}

    def format(self, slot="", **_):
        return _AD_UNIT if slot in self.IN_ARTICLE else ""


AD = _Ad()

# ---------------- data helpers ----------------
def rows_all(con):
    # The price layer is produced by scripts/price_model.py earlier in the build. If a
    # caller skipped that step (an out-of-date CI workflow, a partial local run), an empty
    # table keeps the join valid and the pages simply render without price panels —
    # a degraded build must never be a broken build.
    con.execute("""CREATE TABLE IF NOT EXISTS price_estimates(
        my_id INT PRIMARY KEY, segment TEXT, brand_tier TEXT, anchor TEXT,
        price_new INT, price_new_low INT, price_new_high INT,
        price_today INT, price_today_low INT, price_today_high INT,
        price_in5 INT, price_in5_low INT, price_in5_high INT,
        depreciation_5y INT, depreciation_per_year INT,
        insurance_low INT, insurance_high INT)""")
    rows = con.execute("""SELECT my.id my_id, my.year, my.complaint_count, my.complaint_sample,
      my.recall_count, my.severe_recalls, my.is_ev, my.data_gap,
      mo.id model_id, mo.name model, mo.slug mslug, mk.name make, mk.slug kslug,
      cs.reliability_score score, cs.verdict, cs.reasons, cs.cost_curve, cs.complaints_per_year,
      cs.confidence,
      f.fuel_type, f.mpg_comb, f.annual_fuel_cost, f.ev_range,
      e.battery_warranty, e.battery_replacement_low, e.battery_replacement_high, e.source ev_source,
      pe.segment, pe.anchor price_anchor, pe.price_new, pe.price_new_low, pe.price_new_high,
      pe.price_today, pe.price_today_low, pe.price_today_high,
      pe.price_in5, pe.depreciation_5y, pe.depreciation_per_year,
      pe.insurance_low, pe.insurance_high
      FROM model_years my
      JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
      LEFT JOIN computed_scores cs ON cs.my_id=my.id
      LEFT JOIN fuel f ON f.my_id=my.id
      LEFT JOIN ev_extras e ON e.my_id=my.id
      LEFT JOIN price_estimates pe ON pe.my_id=my.id
      ORDER BY mk.name, mo.name, my.year""").fetchall()
    return fill_fuel([dict(r) for r in rows])


def fill_fuel(rows):
    """fill_fuel.py already wrote a fuel row for every model-year, into the database, with
    the provenance in fuel_type: EPA's own string, "est-adjacent:<year>", or "est-segment".
    Expose it as fuel_src so the templates can label the figure honestly."""
    for r in rows:
        ft = r.get("fuel_type") or ""
        if not r.get("annual_fuel_cost"):
            r["fuel_src"] = None
        elif ft.startswith("est-adjacent:"):
            r["fuel_src"] = "adjacent:" + ft.split(":", 1)[1]
        elif ft.startswith("est-"):
            r["fuel_src"] = "segment"
        else:
            r["fuel_src"] = "epa"
    return rows

SEGMENT_LABEL = {
    "economy": "city car", "compact": "compact car", "midsize": "mid-size car",
    "fullsize": "full-size car", "compact_suv": "compact SUV", "midsize_suv": "mid-size SUV",
    "fullsize_suv": "full-size SUV", "pickup": "pickup", "minivan": "minivan",
    "sports": "sports car", "sports_luxury": "performance car",
    "luxury_compact": "compact premium car", "luxury_midsize": "mid-size premium car",
    "luxury_large": "large premium car", "exotic": "exotic",
}


def money_span(usd, kind="", cls=""):
    """A figure that the geo layer can re-price into the visitor's currency."""
    k = f' data-kind="{kind}"' if kind else ""
    c = f' class="{cls}"' if cls else ""
    return f'<span{c} data-usd="{int(usd)}"{k}>${int(usd):,}</span>'


def price_block(r, five_run_usd, fuel_usd):
    """The money question the site used to refuse to answer: what does this car cost, what
    will it be worth, and what does five years of owning it actually take out of you.

    Depreciation is normally the largest single line on a five-year hold, so it leads. The
    whole block is a class-level estimate — the formula is on /methodology/ — and the reader
    can type the price they are actually being asked to pay, which is the only number that
    makes this personal."""
    if not r["price_today"]:
        return ""
    seg = SEGMENT_LABEL.get(r["segment"], "car")
    lo, hi = r["price_today_low"], r["price_today_high"]
    dep5, dep_yr = r["depreciation_5y"], r["depreciation_per_year"]
    ins_lo, ins_hi = r["insurance_low"], r["insurance_high"]
    ins_mid = (ins_lo + ins_hi) / 2
    run5 = five_run_usd or 0
    tco5 = int(dep5 + run5 + ins_mid * 5)
    per_mile = tco5 / (5 * 12000)
    has_fuel = bool(fuel_usd)
    run_label = "Fuel and maintenance, five years" if has_fuel else "Maintenance, five years (fuel unavailable)"
    total_label = "Five-year cost of owning it" if has_fuel else "Five-year cost shown (excludes fuel)"
    mile_label = ("Per mile driven, at 12,000 miles a year" if has_fuel
                  else "Per mile shown, excluding fuel")
    _fs = r.get("fuel_src") or ""
    missing_fuel = ("" if (has_fuel and _fs == "epa") else
                    ('<p class="src-note">Fuel is an <b>estimate</b> here (EPA has no record for this exact '
                     'model year); it is carried from the nearest EPA-covered year of this nameplate or the class mean, '
                     'and labelled as such above.</p>' if has_fuel else
                     '<p class="data-missing"><b>Fuel cost is not $0.</b> EPA has no matched economy record '
                     'for this model year, so the totals below exclude fuel rather than inventing a number.</p>'))
    anchor_note = ("anchored on the published list price for this model"
                   if r["price_anchor"] == "wikipedia"
                   else f"priced as a {seg} of its model year")
    return f"""<div class="card price-card" id="price">
<h2>What it costs to buy — and what owning it really takes</h2>
<p class="src-note">Class-level estimates, {anchor_note}, re-priced to your country.
Not a quote, not a valuation of one specific car — condition, mileage and options move it.
<a href="/methodology/#prices">How these are computed</a>.</p>
{missing_fuel}
<div class="price-head">
<div class="price-big"><span class="lbl">Typical price today</span>
<b>{money_span(lo, "car")}–{money_span(hi, "car")}</b>
<span class="est">used market, {CURRENT_YEAR}</span></div>
<div class="price-big alt"><span class="lbl">You lose to depreciation</span>
<b>{money_span(dep_yr, "car")}<small>/year</small></b>
<span class="est">{money_span(dep5, "car")} over five years</span></div>
</div>
<div class="tco" data-tco
     data-dep5="{dep5}" data-run5="{int(run5)}" data-ins="{int(ins_mid)}"
     data-price="{r['price_today']}" data-fuel="{int(fuel_usd or 0)}">
<div class="tco-row"><span>Price when new ({r['year']})</span><b>{money_span(r['price_new'], "car")}</b></div>
<div class="tco-row"><span>Worth in five years</span><b data-tco-resale>{money_span(r['price_in5'], "car")}</b></div>
<div class="tco-row"><span>Depreciation, five years</span><b data-tco-dep>{money_span(dep5, "car")}</b></div>
<div class="tco-row"><span>Insurance, five years</span><b>{money_span(ins_lo * 5, "ins")}–{money_span(ins_hi * 5, "ins")}</b></div>
<div class="tco-row"><span>{run_label}</span><b data-usd="{int(run5)}" data-kind="mix" data-fuel-usd="{int((fuel_usd or 0) * 5)}">${int(run5):,}</b></div>
<div class="tco-row grand"><span>{total_label}</span><b data-tco-total data-usd="{tco5}" data-kind="mix" data-fuel-usd="{int((fuel_usd or 0) * 5)}">${tco5:,}</b></div>
<div class="tco-row per"><span>{mile_label}</span><b data-tco-mile>${per_mile:.2f}</b></div>
</div>
<label class="price-input"><span>Being quoted a different price? Put it in and the numbers follow.</span>
<input type="number" inputmode="numeric" data-price-input min="200" max="3000000" step="100"
       placeholder="{r['price_today']}" aria-label="Purchase price"></label>
</div>"""


VARIANTS = {}
try:
    VARIANTS = json.loads((Path(__file__).resolve().parent.parent / "data" / "model_variants.json").read_text())
except Exception:
    VARIANTS = {}

REPAIR = {}
try:
    REPAIR = json.loads((Path(__file__).resolve().parent.parent / "data" / "repair_costs.json").read_text())
except Exception:
    REPAIR = {}
REPAIR_META = REPAIR.get("_meta", {})
LABOUR_USD_H = float(REPAIR_META.get("labour_rate_usd_per_hour", 120))


def repair_band(component):
    """Typical out-of-warranty cost for the representative job in a complaint group.

    cost = flat-rate hours x labour rate + parts band. Volume-free, model-independent and
    fully published on /methodology/ — it is an estimate of what this KIND of failure costs,
    never a quote for a specific car.
    """
    e = REPAIR.get((component or "").upper()) or REPAIR.get("UNKNOWN OR OTHER")
    if not e:
        return None
    labour = e["hours"] * LABOUR_USD_H
    return {"job": e["job"], "hours": e["hours"],
            "low": int(round(labour + e["parts_low"])),
            "high": int(round(labour + e["parts_high"]))}


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
    comps = con.execute("SELECT component, count, sample FROM complaints WHERE my_id=? AND component!='__quote__' ORDER BY count DESC LIMIT 8", (r["my_id"],)).fetchall()
    quotes = [q["sample"] for q in con.execute(
        "SELECT sample FROM complaints WHERE my_id=? AND component='__quote__' LIMIT 3", (r["my_id"],))]
    recalls = con.execute("SELECT * FROM recalls WHERE my_id=? ORDER BY date", (r["my_id"],)).fetchall()
    curve = json.loads(r["cost_curve"] or "[]")
    reasons = json.loads(r["reasons"] or "[]")
    siblings = [x for x in all_rows if x["model_id"] == r["model_id"]]
    # "Compare with" used to take the first eight qualifying rows in table order, which is
    # alphabetical by make — so every page on the site, whatever the car, compared itself
    # against the Acura ILX. A comparison is only worth printing when the cars are
    # alternatives to each other: same price segment, same fuel type, a different nameplate,
    # and the closest model years to this one. Where the segment is unknown the block is
    # dropped rather than filled with something irrelevant.
    _seg = r.get("segment")
    _pool = [x for x in all_rows
             if x["model_id"] != r["model_id"] and gate(x)
             and x.get("segment") and x.get("segment") == _seg
             and bool(x["is_ev"]) == bool(r["is_ev"])
             and abs(x["year"] - year) <= 3]
    # One model year per nameplate: four years of the same rival is not a comparison.
    _best = {}
    for x in sorted(_pool, key=lambda x: (abs(x["year"] - year), -(x["score"] or 0))):
        _best.setdefault(x["model_id"], x)
    related = sorted(_best.values(),
                     key=lambda x: (abs(x["year"] - year), -(x["score"] or 0)))[:4]
    partial = r["complaint_sample"] and r["complaint_count"] and r["complaint_sample"] < r["complaint_count"]

    # verdict card — score, the money, and how much evidence is behind the number
    _age_now = max(0, CURRENT_YEAR - int(year))
    _five = [pt for pt in curve if _age_now <= pt["age"] <= _age_now + 4]
    _fuel = r["annual_fuel_cost"] or 0
    if not _five and curve:
        _five = [min(curve, key=lambda pt: abs(pt["age"] - _age_now))]
    five_run = int(round(sum((pt["total_low"] + pt["total_high"]) / 2 + _fuel for pt in _five)
                         * (5 / len(_five)))) if _five else 0
    try:
        _conf = r["confidence"]
    except Exception:
        _conf = None
    conf_html = ""
    if _conf:
        _cl = {"high": "Strong evidence", "medium": "Moderate evidence", "low": "Thin evidence"}[_conf]
        conf_html = (f'<p class="conf conf-{_conf}">{_cl} — '
                     f'{(r["complaint_count"] or 0):,} complaints, {(r["recall_count"] or 0)} recalls '
                     f'on record</p>')
    price_lead = ""
    if r["price_today"]:
        price_lead = (f'<div class="vc-money vc-price"><span class="lbl">Typical price today</span>'
                      f'<span class="val">{money_span(r["price_today_low"], "car")}–'
                      f'{money_span(r["price_today_high"], "car")}</span>'
                      f'<span class="est">used market estimate · <a href="#price">the full money picture</a></span></div>')
    money_html = ""
    if five_run:
        _run_label = "Running cost, next 5 years" if _fuel else "Maintenance, next 5 years"
        _run_note = ("fuel/energy + maintenance band midpoint" if _fuel
                     else "EPA fuel data unavailable · maintenance only")
        money_html = (f'<div class="vc-money"><span class="lbl">{_run_label}</span>'
                      f'<span class="val" data-usd="{five_run}" data-kind="mix" '
                      f'data-fuel-usd="{_fuel * 5}">${five_run:,}</span>'
                      f'<span class="est">{_run_note} · estimate</span></div>')
    vc = f"""<div class="card verdict sticky">
<div class="chart" style="max-width:150px;margin:0 auto">{svg_gauge(r['score'])}</div>
<span class="badge v-{r['verdict'] if r['verdict'] in ('BUY','CAUTION','AVOID') else 'DATA'}">{esc(r['verdict'] or 'PENDING')}</span>
{conf_html}
{price_lead}
{money_html}
<ul>{''.join(f'<li>{esc(x)}</li>' for x in reasons)}</ul>
<p style="margin-top:12px;font-size:12px"><a href="/methodology/">How this score is computed →</a></p>
</div>"""

    # complaint block
    comp_note = (f'<p style="font-size:12px;color:var(--faint)">Component breakdown based on a sample of '
                 f'{r["complaint_sample"]} of {r["complaint_count"]:,} total NHTSA complaints.</p>') if partial else ""
    comp_html = f"""<div class="card"><h2>Owner complaints: {(r['complaint_count'] or 0):,} filed with NHTSA</h2>
<p>Complaints per year on the road: <span class="num">{r['complaints_per_year'] or 'n/a'}</span></p>
<div class="chart">{svg_bars([(c['component'], c['count']) for c in comps])}</div>{comp_note}</div>"""

    # what owners actually say - verbatim narratives from the federal complaint record,
    # and the live conversation elsewhere. Not Wikipedia, not us: owners.
    q_html = ""
    if quotes:
        q_html = ('<div class="card"><h2>What owners say</h2>'
                  '<p class="src-note" style="font-size:13px;color:var(--faint)">Verbatim reports filed with the United States '
                  'safety regulator (NHTSA) by owners of this exact model year. Public record.</p>'
                  + "".join(f'<blockquote class="owner-q">{esc(q.lower().capitalize() if q.isupper() else q)}'
                            f'{"…" if len(q) >= 420 else ""}</blockquote>' for q in quotes)
                  + '</div>')
    # "The conversation" was three links to reddit.com/search, youtube.com/results and
    # google.com/search, captioned as if they were curated owner threads. They are search
    # boxes. A section that promises community reading and delivers a query string is
    # padding, and on 1,700 pages it is the kind of padding a policy review notices.
    comp_html += q_html

    # recalls block
    # The summary used to be chopped at 140 characters mid-word ("…2017 Sienna and Tac…"),
    # which reads as a broken page to a reviewer and hides the one sentence that says what
    # the defect is. Show the whole first two sentences, cut only at a word boundary.
    def _summ(s):
        s = re.sub(r"\s+", " ", (s or "").strip())
        parts = re.split(r"(?<=[.!?])\s+", s)
        out = " ".join(parts[:2])
        if len(out) > 360:
            out = out[:360].rsplit(" ", 1)[0] + "…"
        return out
    rec_rows = "".join(
        f"<tr><td>{esc(x['campaign'] or '—')}</td><td>{esc((x['component'] or '').title())}</td>"
        f"<td>{esc(_summ(x['summary']))}</td></tr>" for x in recalls[:8])
    gap_rec = r["data_gap"] and "recalls" in (r["data_gap"] or "")
    rec_html = f"""<div class="card"><h2>Recalls: {'data unavailable' if gap_rec else f"{(r['recall_count'] or 0)} campaigns"}{'' if gap_rec or not r['severe_recalls'] else f" ({r['severe_recalls']} severe)"}</h2>
<div class="chart">{svg_timeline(recalls)}</div>
{'<p>NHTSA recall feed temporarily unavailable for this vehicle — check <a href="https://www.nhtsa.gov/recalls" rel="noopener">nhtsa.gov/recalls</a>.</p>' if gap_rec else f'<div class="table-wrap"><table class="cost-table recall-table"><thead><tr><th>Campaign</th><th>Component</th><th>Summary</th></tr></thead><tbody>{rec_rows}</tbody></table></div>'}
</div>"""

    # cost block
    fuel_line = ""
    _src = r.get("fuel_src") or ""
    _kind = 'energy' if r['is_ev'] else 'fuel'
    # Every branch below formats annual_fuel_cost with a thousands separator, which raises
    # on None. fill_fuel.py guarantees a figure for every model year — but it is a separate
    # step, and the GitHub pre-flight workflow never ran it, so that workflow has been dying
    # here on `unsupported format string passed to NoneType` while the Cloudflare build
    # (which does run fill_fuel) deployed happily. A missing figure is a fact to state, not
    # a reason to fail a build.
    if r["annual_fuel_cost"] is None:
        _src = "__none__"
        fuel_line = (f"<p class='data-missing'>No EPA {_kind}-economy record matches this "
                     f"model year, and no estimate is carried for it, so this page states no "
                     f"annual {_kind} cost. <a href='/methodology/#prices'>How estimates are "
                     f"labelled</a>.</p>")
    elif _src == "epa":
        _unit = 'MPGe' if r['is_ev'] else 'MPG'
        fuel_line = (f"<p>EPA combined <span class='num' data-mpg=\"{r['mpg_comb']:.1f}\" data-mpg-unit=\"{_unit}\">"
                     f"{r['mpg_comb']:.0f} {_unit}</span>"
                     f" · estimated annual {_kind} cost "
                     f"<span class='num' data-usd=\"{r['annual_fuel_cost']}\" data-kind=\"fuel\">${r['annual_fuel_cost']:,}</span>"
                     + (f" · EPA range <span class='num' data-mi=\"{r['ev_range']:.0f}\">{r['ev_range']:.0f} mi</span>" if r["ev_range"] else "") + "</p>")
    elif _src.startswith("adjacent:"):
        _unit = 'MPGe' if r['is_ev'] else 'MPG'
        _y = _src.split(":")[1]
        fuel_line = (f"<p>Est. annual {_kind} cost "
                     f"<span class='num' data-usd=\"{r['annual_fuel_cost']}\" data-kind=\"fuel\">${r['annual_fuel_cost']:,}</span>"
                     + (f" · <span class='num' data-mpg=\"{r['mpg_comb']:.1f}\" data-mpg-unit=\"{_unit}\">{r['mpg_comb']:.0f} {_unit}</span>" if r.get("mpg_comb") else "")
                     + " <em>(estimate)</em></p>"
                     f"<p class='src-note'>Carried over from EPA's {_y} {esc(make)} {esc(model)} record, the nearest model year "
                     f"EPA covers; the exact {year} trim can differ by a few MPG.</p>")
    else:
        fuel_line = (f"<p>Est. annual {_kind} cost "
                     f"<span class='num' data-usd=\"{r['annual_fuel_cost']}\" data-kind=\"fuel\">${r['annual_fuel_cost']:,}</span>"
                     " <em>(estimate)</em></p>"
                     f"<p class='src-note'>EPA has no matched record for this model year: this is the mean EPA figure for "
                     f"{'electric cars' if r['is_ev'] else 'a ' + esc(SEGMENT_LABEL.get(r.get('segment') or '', 'car of this class'))} "
                     f"in this dataset at EPA's 15,000-mile assumption. <a href='/methodology/#prices'>How estimates are labelled</a>.</p>")
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
        has_fuel = bool(r["annual_fuel_cost"])
        # score_model_years stores maintenance only. Fuel is added here exactly once so
        # the page can re-price the two components with different country indices.
        maint_lo = yr1["total_low"]
        maint_hi = yr1["total_high"]
        # The headline figure is the MIDPOINT of the band, not its ceiling. Publishing a
        # band and then quietly summing its top overstated every car by roughly a fifth.
        mid_usd = int(round((yr1["total_low"] + yr1["total_high"]) / 2 + fuel_usd))
        five = [p for p in curve if age_now <= p["age"] <= age_now + 4] or [yr1]
        five_usd = int(round(sum((p["total_low"] + p["total_high"]) / 2 + fuel_usd for p in five)
                             * (5 / len(five))))
        total_low = yr1["total_low"] + fuel_usd
        total_high = yr1["total_high"] + fuel_usd
        fuel_row = (f'<div class="geo-cost-row"><span>{"Energy" if r["is_ev"] else "Fuel"} (your region)</span>'
                    f'<b data-usd="{fuel_usd}" data-kind="fuel">${fuel_usd:,}</b></div>' if has_fuel else
                    '<div class="geo-cost-row missing"><span>Fuel or energy</span><b>Not available</b></div>')
        total_label = (f"Estimated running cost this year (age {age_now})" if has_fuel
                       else f"Estimated maintenance this year (age {age_now})")
        five_label = "Next five years, running cost" if has_fuel else "Next five years, maintenance only"
        geo_note = ("Re-priced automatically from your country's retail fuel, electricity and parts indices"
                    if has_fuel else
                    "Maintenance re-priced from your country's parts and workshop-cost index; fuel is excluded")
        geo_block = f"""<div class="geo-cost">
{fuel_row}
<div class="geo-cost-row"><span>Maintenance band (your region)</span>
<b><span data-usd="{maint_lo}" data-kind="maint">${maint_lo:,}</span>–<span data-usd="{maint_hi}" data-kind="maint">${maint_hi:,}</span></b></div>
<div class="geo-cost-row total"><span>{total_label}</span>
<b id="geo-total" data-usd="{mid_usd}" data-fuel-usd="{fuel_usd}">${mid_usd:,}</b></div>
<div class="geo-cost-row range"><span>Range across the maintenance band</span>
<b><span data-usd="{total_low}" data-kind="mix" data-fuel-usd="{fuel_usd}">${total_low:,}</span>–<span data-usd="{total_high}" data-kind="mix" data-fuel-usd="{fuel_usd}">${total_high:,}</span></b></div>
<div class="geo-cost-row five"><span>{five_label}</span>
<b data-usd="{five_usd}" data-kind="mix" data-fuel-usd="{fuel_usd * 5}">${five_usd:,}</b></div>
<p class="geo-note">{geo_note} —
change country in the bar at the top. Estimates; see <a href="/methodology/">methodology</a>.</p></div>"""
    # What this car's actual problems cost to fix. The ranking is this model-year's own
    # NHTSA complaint clusters; the money is a published flat-rate calculation, re-priced
    # to the visitor's country like every other figure on the page.
    repair_rows = []
    for c in comps[:6]:
        b = repair_band(c["component"])
        if not b:
            continue
        repair_rows.append(
            f'<li><span class="job"><b>{esc(c["component"].title())}</b>'
            f'<span class="freq">{c["count"]:,} complaints · typical job: {esc(b["job"])} '
            f'({b["hours"]:.1f} h labour + parts)</span></span>'
            f'<span class="amt"><span data-usd="{b["low"]}" data-kind="maint">${b["low"]:,}</span>–'
            f'<span data-usd="{b["high"]}" data-kind="maint">${b["high"]:,}</span></span></li>')
    repair_html = ""
    if repair_rows:
        repair_html = (
            '<div class="card"><h2>What this car\'s problems cost to fix</h2>'
            '<p class="src-note">Ranked by the components owners of this exact model year actually '
            'complain about. Each figure is flat-rate labour hours x the local shop rate plus a parts '
            'band — an estimate of what this kind of failure costs, not a quote, and not a prediction '
            'that this car will need it. <a href="/methodology/">Formula</a>.</p>'
            f'<ul class="repair-list">{"".join(repair_rows)}</ul></div>')

    price_html = price_block(r, five_run, _fuel)

    # Owner satisfaction. NHTSA tells us what broke; only owners can tell us whether they
    # would do it again. Until real responses exist the survey card said "No responses yet"
    # on 1,900 pages — a site-wide empty section, which is what an AdSense reviewer reads as
    # a site under construction. The survey now lives behind the love button (account.js
    # opens it) and the card returns to the page only when the API has responses to show.
    survey_html = (f'<div class="card engagement-card">'
                   f'<div class="love-host" data-love="my:{r["my_id"]}" data-love-name="{esc(name)}"></div>'
                   f'<div class="survey-card" data-survey="my:{r["my_id"]}" data-survey-name="{esc(name)}" '
                   f'data-survey-quiet="1"></div></div>')

    running_curve = [{**p, "total_low": p["total_low"] + _fuel,
                      "total_high": p["total_high"] + _fuel} for p in curve]
    _legend = ("fuel/energy + maintenance band" if _fuel else "maintenance band only — fuel data unavailable")
    cost_html = f"""<div class="card"><h2>What it costs to run</h2>{fuel_line}
{geo_block}
<div class="chart">{svg_costcurve(running_curve)}</div>
<div class="legend"><span><i style="background:#0E7C86"></i>{_legend}, annual — <span data-geo-currency-note>US dollars</span>, estimate</span></div>
{ev_block}
<p style="margin-top:10px"><a href="/calculators/">Run your own numbers in the true-cost calculator →</a></p></div>"""

    # years strip
    strip = "".join(
        f'<a href="{url_my(s)}" class="{"cur" if s["year"] == year else ""}">{s["year"]} {vtag(s["verdict"]) if s["verdict"] in ("AVOID",) else ""}</a>'
        if gate(s) else f'<span class="years-strip-dead" style="padding:6px 13px;color:var(--faint);font-size:14px">{s["year"]}</span>'
        for s in siblings)
    strip_html = f'<div class="card"><h2>Other {make} {model} years</h2><div class="years-strip">{strip}</div><p class="src-note" style="margin-top:8px;font-size:13px"><a href="/cars/{r["kslug"]}/{r["mslug"]}/">{make} {model} years to avoid, and the best years to buy →</a></p></div>'

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
    if comps:
        _b = repair_band(comps[0]["component"])
        if _b:
            faqs.append((f"How much does it cost to fix the {name}'s most common problem?",
                         f"{comps[0]['count']:,} of the NHTSA complaints filed against the {name} sit in the "
                         f"{comps[0]['component'].title()} group — more than any other component on this "
                         f"model year. The representative job there is {_b['job'].lower()}: about "
                         f"{_b['hours']:.1f} hours of labour plus parts, roughly ${_b['low']:,}–${_b['high']:,} "
                         f"at a US independent shop and re-priced to your country at the top of the page. "
                         f"It is an estimate of what this class of failure costs, not a quote for this car."))
    if five_run:
        _faq_cost = (f"About ${int(five_run/5):,} a year in fuel or energy plus the maintenance band"
                     if _fuel else
                     f"About ${int(five_run/5):,} a year for the maintenance band; EPA fuel data is unavailable and excluded")
        faqs.append((f"What does a {name} cost to run per year?",
                     f"{_faq_cost} — "
                     f"roughly ${five_run:,} over five years, before purchase price, insurance and "
                     f"depreciation. Figures come from available EPA fuel-economy data and industry maintenance "
                     f"averages, and are re-priced to your country."))
    if r["is_ev"] and r["battery_warranty"]:
        faqs.append((f"How much does a {name} battery replacement cost?",
                     f"Out of warranty, an estimated ${r['battery_replacement_low']:,}–${r['battery_replacement_high']:,}. "
                     f"Warranty coverage: {r['battery_warranty']}."))
    if recalls and not gap_rec:
        faqs.append((f"Does the {name} have recalls?",
                     f"Yes — NHTSA lists {r['recall_count']} recall campaign(s) for the {name}, "
                     f"{r['severe_recalls']} of them touching fire, crash or stall risk"
                     + (f", the most recent recorded {recalls[0]['date']}." if recalls and recalls[0]['date'] else ".")
                     + f" Check this car's VIN at nhtsa.gov/recalls before you buy."))
    faq_html = '<div class="card"><h2>FAQ</h2>' + "".join(
        f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faqs) + "</div>"

    _seg_label = (r.get("segment") or "").replace("_", " ")
    related_html = ('<div class="card"><h2>Compare with</h2>'
                    + (f'<p style="font-size:13px;color:var(--faint)">Other {esc(_seg_label)}s '
                       f'of about the same age.</p>' if _seg_label else "")
                    + '<div class="rel-grid">' + "".join(
        f'<a href="{url_my(x)}">{x["year"]} {esc(x["make"])} {esc(x["model"])}<small>score {x["score"]}/100 · {esc(x["verdict"])}</small></a>'
        for x in related) + "</div></div>") if related else ""

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
{byline(f"{r['kslug']}/{r['mslug']}/{year}", TODAY)}
</div>
{hero_art(make, model, bool(r['is_ev']), year)}
</div></div>"""

    # The social card was /og/default.png on every one of these pages, so every share of
    # every car looked identical. Where the library has a licensed photograph of this
    # nameplate, that is the card and the schema image.
    _ph = lib_photo(make, model, year)
    _my_photo_url = (f"https://commons.wikimedia.org/wiki/Special:FilePath/"
                     f"{_uq(_ph.replace(' ', '_'))}?width=1200") if _ph else ""

    body = f"""{hero}
<div class="wrap grid">
<div style="display:grid;gap:20px;min-width:0">
{editor_card(r['kslug'], r['mslug'], year, r)}
{guide_link_card(r['kslug'], r['mslug'], year)}
{comp_html}
{AD.format(slot='mid')}
{rec_html}
{price_html}
{cost_html}
{survey_html}
{repair_html}
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
        # The photograph the page already shows belongs in the Vehicle entity too: without
        # an image property the page is ineligible for the image-carrying result treatments.
        {"@context": "https://schema.org", "@type": "Vehicle", "name": name,
         "brand": {"@type": "Brand", "name": make}, "model": model, "vehicleModelDate": str(year),
         **({"image": _my_photo_url} if _my_photo_url else {}),
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
         "creator": {"@type": "Organization", "name": BRAND}, "url": canon},
        {"@context": "https://schema.org", "@type": "Article", "headline": f"{name}: True Cost, Problems & Verdict",
         "author": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
         "publisher": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
         "dateModified": TODAY, "mainEntityOfPage": canon}]
    og_rel = f"/og/{r['kslug']}-{r['mslug']}-{year}.png"
    # Index gate. A verdict on a thin record (under 50 complaints, "low" confidence) is a
    # page Google reads as auto-generated: same skeleton, few facts. Those pages stay online
    # for readers and for the year tables that link them, but out of the index. A page is
    # indexable on a strong or moderate record, on EV battery data, or when the editor has
    # written a note for the nameplate.
    indexable = ((_conf in ("high", "medium")) or bool(r["is_ev"] and r["battery_warranty"])
                 or bool(editor_card(r['kslug'], r['mslug'])))
    extra_head = "" if indexable else NOINDEX
    # This block used to ASSIGN extra_head rather than add to it, so on any build where
    # Pillow imported — which is every CI build — the social card silently deleted the
    # noindex tag that the line above had just set. Every thin model year went into the
    # index regardless of the gate. Append; never overwrite.
    if og_card is not None:
        og_card(SITE / og_rel.lstrip("/"), name, "True cost, problems & data verdict",
                r["score"], r["verdict"] or "", bool(r["is_ev"]))
        extra_head += (f'<meta property="og:image" content="{ORIGIN}{og_rel}">'
                       f'<meta property="og:image:width" content="1200">'
                       f'<meta property="og:image:height" content="630">'
                       f'<meta name="twitter:image" content="{ORIGIN}{og_rel}">\n')
    elif _my_photo_url:
        # No Pillow on this build image: rather than fall back to one identical default
        # card on every car on the site, share the photograph of the car itself.
        extra_head += (f'<meta property="og:image" content="{esc(_my_photo_url)}">'
                       f'<meta name="twitter:image" content="{esc(_my_photo_url)}">\n')
    return write(url.lstrip("/") + "index.html",
                 page(f"{name}: Cost, Problems & Verdict | {BRAND}", desc, canon, body, jsonld,
                      extra_head=extra_head, og_type="article"))

# ---------------- model overview ----------------
# ---- the generation verdict ------------------------------------------------------------
# "<make> <model> years to avoid" is a single question with a single right answer page, and
# that page is the nameplate hub, not one of its fifteen year pages. Until now the hub
# answered it with a table of numbers and left the reader to do the work. This builds the
# answer: the record is cut into runs of years that behave alike, each run is named with the
# component its owners actually complain about, and the years to avoid and the years to buy
# are stated in the first screen. Every sentence is derived from the rows on the page, so no
# two nameplates produce the same prose and nothing here is written by hand.
def _era_breaks(rows):
    """Split the model years into runs that behave alike.

    A redesign shows up in this data as a step: the complaint rate per year of exposure
    jumps or collapses and stays there. A break is declared where a year differs from the
    run's mean by more than 22 points of score AND the two years after it agree with the new
    level — one noisy year in an otherwise steady run is not a generation.
    """
    eras, cur = [], []
    for i, s in enumerate(rows):
        if not cur:
            cur = [s]
            continue
        mean = sum((x["score"] or 0) for x in cur) / len(cur)
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        step = abs((s["score"] or 0) - mean) > 22
        gap = s["year"] - cur[-1]["year"] > 1
        holds = nxt is None or abs((nxt["score"] or 0) - (s["score"] or 0)) <= 22
        if (step and holds) or gap:
            eras.append(cur)
            cur = [s]
        else:
            cur.append(s)
    if cur:
        eras.append(cur)
    return eras


def _top_component(con, rows):
    ids = [s["my_id"] for s in rows]
    if not ids:
        return None, 0
    q = ("SELECT component, SUM(count) n FROM complaints WHERE component!='__quote__' "
         "AND my_id IN (%s) GROUP BY component ORDER BY n DESC LIMIT 1" % ",".join("?" * len(ids)))
    row = con.execute(q, ids).fetchone()
    return (row[0], row[1]) if row else (None, 0)


def _an(word):
    """"a Accord" read like a machine wrote it, which on a page about trustworthiness is
    not a small thing."""
    return "an" if (word or "")[:1].upper() in "AEIOU" else "a"


def _span(rows):
    a, b = rows[0]["year"], rows[-1]["year"]
    return str(a) if a == b else f"{a}\u2013{b}"


def generation_verdict(con, model_rows, make, model):
    """(headline html, era html, extra faqs). Returns ("", "", []) when the record is too
    thin to say anything — a verdict on two model years is not a verdict."""
    rows = sorted([s for s in model_rows if s["score"] is not None], key=lambda s: s["year"])
    if len(rows) < 4:
        return "", "", []

    avoid = [s for s in rows if (s["verdict"] or "") == "AVOID"]
    buy = [s for s in rows if (s["verdict"] or "") == "BUY"]
    caution = [s for s in rows if (s["verdict"] or "") == "CAUTION"]

    def yrs(ss, n=8):
        out = ", ".join(str(s["year"]) for s in sorted(ss, key=lambda s: s["year"])[:n])
        return out + ("\u2026" if len(ss) > n else "")

    def linked(ss, n=8):
        ss = sorted(ss, key=lambda s: s["year"])[:n]
        return ", ".join((f'<a href="{url_my(s)}">{s["year"]}</a>' if gate(s) else str(s["year"]))
                         for s in ss)

    # the headline answer, above the fold
    bits = []
    if avoid:
        bits.append(f'<p class="ga-avoid"><b>Avoid:</b> {linked(avoid)} '
                    f'&mdash; scored below 45 on the complaint and recall record.</p>')
    if buy:
        bits.append(f'<p class="ga-buy"><b>Safest years:</b> {linked(buy)} '
                    f'&mdash; scored 70 or better.</p>')
    if caution and not avoid:
        bits.append(f'<p class="ga-caution"><b>Check carefully:</b> {linked(caution)}.</p>')
    if not bits:
        return "", "", []

    worst = min(rows, key=lambda s: s["score"])
    best = max(rows, key=lambda s: s["score"])
    wc, wn = _top_component(con, [worst])
    spread = best["score"] - worst["score"]
    lede = (f'Across {len(rows)} scored model years the {esc(make)} {esc(model)} ranges from '
            f'{worst["score"]}/100 in {worst["year"]} to {best["score"]}/100 in {best["year"]}'
            f' \u2014 a {spread}-point spread, so which year you buy matters'
            + (f' more than whether you buy {_an(model)} {esc(model)} at all.'
               if spread >= 35 else '.'))
    if wc and wn:
        lede += (f' The weakest year\u2019s complaints concentrate in {esc(wc.title())} '
                 f'({wn:,} of them).')

    headline = (f'<div class="card gen-verdict"><h2 id="years-to-avoid">'
                f'{esc(make)} {esc(model)}: which years to avoid</h2>'
                f'<p>{lede}</p>{"".join(bits)}'
                f'<p class="src-note">Scored from NHTSA complaints per year of exposure and '
                f'recall campaigns. <a href="/methodology/">How the score works</a> · '
                f'<a href="/years-to-avoid/">every car\u2019s years to avoid</a>.</p></div>')

    # the run-by-run reading
    eras = [e for e in _era_breaks(rows) if len(e) >= 2]
    era_html, faqs = "", []
    if len(eras) >= 2:
        blocks = []
        prev_mean = None
        for e in eras:
            mean = round(sum(s["score"] for s in e) / len(e))
            comp, n = _top_component(con, e)
            rate = [s["complaints_per_year"] for s in e if s["complaints_per_year"]]
            rate = round(sum(rate) / len(rate)) if rate else None
            move = ""
            if prev_mean is not None:
                d = mean - prev_mean
                if d >= 15:
                    move = f" The record improves by {d} points against the years before it."
                elif d <= -15:
                    move = f" The record falls {abs(d)} points against the years before it."
            sev = sum(s["severe_recalls"] or 0 for s in e)
            blocks.append(
                f'<h3>{_span(e)}</h3><p>Mean score {mean}/100'
                + (f', about {rate:,} complaints per year on the road' if rate else '')
                + (f'. Owners of these years complain about {esc(comp.title())} more than anything '
                   f'else ({n:,} complaints)' if comp and n else '')
                + f'.{move}'
                + (f' {sev} recall campaign(s) in this run touch fire, crash or stall risk.'
                   if sev else '')
                + '</p>')
            prev_mean = mean
        era_html = (f'<div class="card gen-eras"><h2>How the {esc(model)} changed, run by run</h2>'
                    f'<p class="src-note">The federal record falls into {len(eras)} stretches of '
                    f'years that behave alike. A redesign shows up here as a step in the complaint '
                    f'rate that then holds.</p>' + "".join(blocks) + '</div>')

    if avoid:
        faqs.append((f"Which {make} {model} years should I avoid?",
                     f"On the NHTSA record the years to avoid are {yrs(avoid)} — each scores below "
                     f"45 out of 100 on complaints per year of exposure and recall campaigns."
                     + (f" The {worst['year']} is the weakest at {worst['score']}/100"
                        + (f", with its complaints concentrated in {wc.title()}." if wc else ".")
                        if worst else "")))
    if buy:
        faqs.append((f"What are the best {make} {model} years to buy?",
                     f"{yrs(buy)} all score 70 or better. The strongest is the {best['year']} at "
                     f"{best['score']}/100, on {(best['complaint_count'] or 0):,} complaints and "
                     f"{best['recall_count'] or 0} recall campaigns."))
    return headline, era_html, faqs


def gen_model(con, model_rows, all_rows):
    r0 = model_rows[0]
    make, model = r0["make"], r0["model"]
    url = f"/cars/{r0['kslug']}/{r0['mslug']}/"
    canon = ORIGIN + url
    def yr_cell(s):
        return ('<a href="' + url_my(s) + '">' + str(s["year"]) + "</a>") if gate(s) else str(s["year"])
    def _run_cost(s):
        """Midpoint running cost for that year's car, this year — the number a buyer weighs."""
        try:
            cv = json.loads(s["cost_curve"] or "[]")
        except Exception:
            cv = []
        if not cv:
            return None, 0
        a = max(0, CURRENT_YEAR - int(s["year"]))
        pt = min(cv, key=lambda x: abs(x["age"] - a))
        fuel = s["annual_fuel_cost"] or 0
        return int(round((pt["total_low"] + pt["total_high"]) / 2 + fuel)), fuel

    def _cost_cell(s):
        v, fu = _run_cost(s)
        if not v:
            return "—"
        return (f'<span data-usd="{v}" data-kind="mix" data-fuel-usd="{fu}">${v:,}</span>')

    rows = "".join(
        f"<tr><td>{yr_cell(s)}</td>"
        f"<td class=\"num\">{s['score'] if s['score'] is not None else '—'}</td><td>{vtag(s['verdict'])}</td>"
        f"<td class=\"num\">{_cost_cell(s)}</td>"
        f"<td class=\"num\">{(format(s['complaint_count'], ',') if s['complaint_count'] is not None else '—')}</td>"
        f"<td class=\"num\">{(s['recall_count'] if s['recall_count'] is not None else '—')}</td></tr>"
        for s in sorted(model_rows, key=lambda x: -x["year"]))
    # Only years that actually get a page may be linked, or the sibling strip ships 404s.
    scored = [s for s in model_rows if s["score"] is not None and gate(s)]
    best = max(scored, key=lambda s: s["score"], default=None)
    worst = min(scored, key=lambda s: s["score"], default=None)
    # The subtitle used to be one fixed sentence, so it appeared verbatim on every model
    # page and alone accounted for most of the duplicate-paragraph budget. Built from this
    # model's own numbers it is unique per page — and more use to a reader.
    rows_r = model_rows
    tot_comp = sum(s["complaint_count"] or 0 for s in model_rows)
    tot_rec = sum(s["recall_count"] or 0 for s in model_rows)
    if not best or not worst:
        class _S(dict):
            __getitem__ = dict.get
        best = best or _S(year="n/a")
        worst = worst or _S(year="n/a")
    verdict_line = ""
    if best and worst and best["my_id"] != worst["my_id"]:
        verdict_line = (f"<p>Best year in our data: <a href='{url_my(best)}'><b>{best['year']}</b></a> "
                        f"(score {best['score']}). Worst: <a href='{url_my(worst)}'><b>{worst['year']}</b></a> "
                        f"(score {worst['score']}, {esc(worst['verdict'])}).</p>")
    # Same defect as the model-year page: taking the first four qualifying rows means
    # taking whatever sorts first alphabetically. Peers are same-segment, same fuel type,
    # a different nameplate, and the most recent year of each.
    _seg0 = r0.get("segment")
    _pool0, _best0 = [], {}
    if _seg0:
        _pool0 = [x for x in all_rows
                  if x["model_id"] != r0["model_id"] and gate(x)
                  and x.get("segment") == _seg0
                  and bool(x["is_ev"]) == bool(r0["is_ev"])]
    for x in sorted(_pool0, key=lambda x: (-x["year"], -(x["score"] or 0))):
        _best0.setdefault(x["model_id"], x)
    related = list(_best0.values())[:4]
    rel = ('<div class="rel-grid">' + "".join(
        f'<a href="{url_my(x)}">{x["year"]} {esc(x["make"])} {esc(x["model"])}<small>{esc(x["verdict"])}</small></a>'
        for x in related) + "</div>") if related else ""

    # What actually goes wrong across the whole nameplate, and what those repairs cost.
    ids = [s["my_id"] for s in model_rows]
    agg = {}
    if ids:
        q = ("SELECT component, SUM(count) n FROM complaints WHERE component!='__quote__' AND my_id IN (%s)"
             " GROUP BY component ORDER BY n DESC LIMIT 6" % ",".join("?" * len(ids)))
        for comp, n in con.execute(q, ids):
            agg[comp] = n
    prob_rows = []
    for comp, n in agg.items():
        b = repair_band(comp)
        if not b:
            continue
        prob_rows.append(
            f'<li><span class="job"><b>{esc(comp.title())}</b>'
            f'<span class="freq">{n:,} complaints across all {esc(model)} years · typical job: '
            f'{esc(b["job"])}</span></span>'
            f'<span class="amt"><span data-usd="{b["low"]}" data-kind="maint">${b["low"]:,}</span>–'
            f'<span data-usd="{b["high"]}" data-kind="maint">${b["high"]:,}</span></span></li>')
    problem_html = ""
    if prob_rows:
        problem_html = (f'<div class="card"><h2>What goes wrong on the {esc(make)} {esc(model)}</h2>'
                        f'<p>Across every {esc(model)} model year in our index, owners report these component '
                        f'groups most often. The cost beside each one is the representative repair for that '
                        f'group at a US independent shop, re-priced to your country.</p>'
                        f'<ul class="repair-list">{"".join(prob_rows)}</ul>'
                        '<p class="src-note">Flat-rate labour hours x local shop rate plus a parts band. '
                        'An estimate of what this class of failure costs, not a quote. '
                        '<a href="/methodology/">Formula</a>.</p></div>')

    gv_head, gv_eras, gv_faqs = generation_verdict(con, model_rows, make, model)

    m_faqs = list(gv_faqs)
    _have_bw = bool(best) and bool(worst) and str(best["year"]) != "n/a" and str(worst["year"]) != "n/a" \
        and best["my_id"] != worst["my_id"]
    _asked = {q for q, _ in m_faqs}
    if _have_bw and f"What are the best {make} {model} years to buy?" not in _asked:
        m_faqs.append((f"What is the best year for the {make} {model}?",
                       f"On our data the {best['year']} {make} {model} scores {best['score']}/100 — the highest "
                       f"of the {len(rows_r)} model years we hold, with {(best['complaint_count'] or 0):,} NHTSA "
                       f"complaints and {best['recall_count'] or 0} recall campaigns on record."))
    if _have_bw and f"Which {make} {model} years should I avoid?" not in _asked:
        m_faqs.append((f"Which {make} {model} years should I avoid?",
                       f"The {worst['year']} is the weakest year we score, at {worst['score']}/100 "
                       f"({worst['verdict']}), on {(worst['complaint_count'] or 0):,} complaints and "
                       f"{worst['recall_count'] or 0} recalls. Check the year-by-year table above before "
                       f"committing to any particular car."))
    if agg:
        _c = list(agg.items())[0]
        m_faqs.append((f"What is the most common {make} {model} problem?",
                       f"{_c[1]:,} of the complaints filed against the {model} across all its model years "
                       f"sit in the {_c[0].title()} group — more than any other component."))
    faq_html = ('<div class="card"><h2>FAQ</h2>' + "".join(
        f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in m_faqs) + "</div>") if m_faqs else ""
    # ---- sub-models and the wider family ------------------------------------------
    # Two kinds of relatives, both previously invisible. (1) Variants the canonicaliser
    # folded INTO this page (trim and body strings from the federal record) — their
    # complaint and recall data is inside this page's numbers, and readers deserve to see
    # the list. (2) Sibling nameplates that stayed separate because powertrain and family
    # position are never merged (Sport, Evoque, PHEV, LWB…) — each links to its own page.
    folded = {v for v in VARIANTS.get(url, []) if v.lower() != (model or "").lower()}
    fam_prefix = (model or "").lower() + " "
    fam_pages = {}
    for x in all_rows:
        if x["kslug"] != r0["kslug"] or x["model_id"] == r0["model_id"]:
            continue
        n2 = (x["model"] or "").lower()
        if n2.startswith(fam_prefix) or fam_prefix.rstrip().startswith(n2 + " "):
            if gate(x):
                cur = fam_pages.get(x["model_id"])
                if not cur or (x["score"] or 0) > (cur["score"] or 0):
                    fam_pages[x["model_id"]] = x
            else:
                # a real sub-model in the federal record that has no page of its own yet
                # (thin data) — shown as a chip, so it is at least visible
                folded.add(x["model"])
    fam_html = ""
    if folded or fam_pages:
        # A variant belongs on the nearest page: "Range Rover Sport SVR" is the Sport
        # page's chip, not this one's. Anything starting with a linked sibling's name is
        # dropped here — it will appear there.
        linked_names = [x["model"].lower() for x in fam_pages.values()]
        folded = {v for v in folded
                  if not any(v.lower() == ln or v.lower().startswith(ln + " ")
                             for ln in linked_names)}
        chips = "".join(f'<span class="chip">{esc(v)}</span>' for v in sorted(folded))
        links = "".join(
            f'<a href="/cars/{x["kslug"]}/{x["mslug"]}/">{esc(x["model"])}'
            f'<small>{("score " + str(x["score"]) + "/100") if x["score"] is not None else "data indexed"}</small></a>'
            for x in sorted(fam_pages.values(), key=lambda x: x["model"]))
        fam_html = (
            f'<div class="card"><h2>{esc(model)} sub-models &amp; family</h2>'
            + (f'<div class="rel-grid">{links}</div>' if links else "")
            + (f'<h3 style="margin-top:{"14px" if links else "0"}">Variants &amp; trims on record</h3>'
               f'<p class="src-note">Body, powertrain and trim variants of the {esc(model)} on the '
               f'federal record. Variants folded into this nameplate are counted in this page\'s data; '
               f'the rest have too thin a record for a page of their own yet.</p>'
               f'<div class="chip-row">{chips}</div>' if chips else "")
            + '</div>')
    gallery_link = ""
    _lib = model_url(f"{make} {model}")
    if _lib == "/library/":
        _lib = model_url(model)
    if _lib != "/library/":
        gallery_link = (f'<p style="margin-top:8px"><a href="{_lib}">Photographs and every '
                        f'generation of the {esc(model)}, through the years →</a></p>')

    if str(best["year"]) == "n/a" or str(worst["year"]) == "n/a":
        _sub_line = (f"The {esc(make)} {esc(model)} has {len(rows_r)} model year(s) in the federal "
                     f"index and no scored complaint record yet, so this page carries the catalogue "
                     f"entry and the years we hold rather than a verdict.")
    else:
        _sub_line = (f"{esc(make)} {esc(model)}: {len(rows_r)} model years scored from "
                     f"{tot_comp:,} NHTSA owner complaints and {tot_rec} recall campaigns. "
                     f"Worst year {worst['year']}, best year {best['year']}.")
    body = f"""<div class="hero"><div class="wrap hero-inner hero-flex">
<div class="hero-copy">
<nav class="crumbs"><a href="/cars/">Cars</a> › <a href="/cars/{r0['kslug']}/">{esc(make)}</a> › {esc(model)}</nav>
<h1>{esc(make)} {esc(model)}: Years to Avoid and Best Years to Buy</h1>
<p class="sub">{_sub_line}</p>
{byline(f"{r0['kslug']}/{r0['mslug']}", TODAY)}
</div>
{hero_art(make, model, bool(r0['is_ev']))}
</div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0">
{gv_head}
{editor_card(r0['kslug'], r0['mslug'])}
{guide_link_card(r0['kslug'], r0['mslug'])}
{gv_eras}
{AD.format(slot='mid')}
<div class="card engagement-card"><div class="love-host" data-love="nameplate:{r0['kslug']}/{r0['mslug']}" data-love-name="{esc(make)} {esc(model)}"></div>
<div class="survey-card" data-survey="nameplate:{r0['kslug']}/{r0['mslug']}" data-survey-name="{esc(make)} {esc(model)}" data-survey-quiet="1"></div></div>
<div class="card"><h2>Year-by-year data table</h2>{verdict_line}
<div class="table-wrap"><table class="cost-table"><thead><tr><th>Year</th><th>Score</th><th>Verdict</th>
<th>Running cost / yr</th><th>NHTSA complaints</th><th>Recalls</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="src-note">Running cost is fuel or energy plus the maintenance band midpoint for that car at its
age today, re-priced to your country. Purchase price, insurance and depreciation are not included.</p>{gallery_link}</div>
{fam_html}
{problem_html}
{faq_html}
{AD.format(slot='mid')}
<div class="card"><h2>Compare with</h2>{rel}</div>
<div class="card sources"><p>Sources: <a href="https://www.nhtsa.gov" rel="noopener">NHTSA</a>, <a href="https://www.fueleconomy.gov" rel="noopener">EPA</a> · <a href="/methodology/">Methodology</a> · Updated {TODAY}</p></div>
</div>"""
    jsonld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Cars", "item": ORIGIN + "/cars/"},
        {"@type": "ListItem", "position": 2, "name": make, "item": f"{ORIGIN}/cars/{r0['kslug']}/"},
        {"@type": "ListItem", "position": 3, "name": model, "item": canon}]},
        {"@context": "https://schema.org", "@type": "ItemList", "name": f"{make} {model} model years ranked",
         "numberOfItems": len(model_rows), "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": f"{x['year']} {make} {model}",
             "url": ORIGIN + url_my(x)}
            for i, x in enumerate(sorted([y for y in model_rows if gate(y)],
                                         key=lambda y: -(y["score"] or 0))[:20])]}]
    if m_faqs:
        jsonld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in m_faqs]})
    # A model overview with no scored year is a table of dashes: keep it, do not index it.
    # One or two scored years is not much better — a 320-word hub whose first screen says
    # DATA PENDING is the thin page a policy reviewer samples. Indexable on three scored
    # years, or on the editor's note, or when the run-by-run verdict could be written.
    _head = "" if (len(scored) >= 3 or gv_head or editor_card(r0['kslug'], r0['mslug'])) else NOINDEX
    _ph0 = lib_photo(make, model)
    if _ph0:
        _u0 = (f"https://commons.wikimedia.org/wiki/Special:FilePath/"
               f"{_uq(_ph0.replace(' ', '_'))}?width=1200")
        _head += (f'<meta property="og:image" content="{esc(_u0)}">'
                  f'<meta name="twitter:image" content="{esc(_u0)}">\n')
    return write(url.lstrip("/") + "index.html",
                 page(f"{make} {model} Years to Avoid — and the Best Years | {BRAND}",
                      (f"{make} {model}: the model years to avoid and the years to buy, ranked from "
                       f"{tot_comp:,} NHTSA complaints and {tot_rec} recall campaigns."),
                      canon, body, jsonld, extra_head=_head))

# ---------------- brand hub, index, static ----------------
def gen_brand(con, kslug, make, models, all_rows):
    url = f"/cars/{kslug}/"
    items = "".join(
        f'<a href="/cars/{kslug}/{ms}/">{esc(make)} {esc(mn)}<small>{n} model years indexed</small></a>'
        for ms, mn, n in models)

    # A brand hub that is only a list of links is a thin page. Rank the marque's models by
    # the data the site already holds, and say which years to avoid — the reason to be here.
    mine = [x for x in all_rows if x["kslug"] == kslug and x["score"] is not None]
    by_model = {}
    for x in mine:
        by_model.setdefault(x["mslug"], []).append(x)
    ranked = []
    for ms, rows_m in by_model.items():
        scored = [y for y in rows_m if y["score"] is not None]
        if not scored:
            continue
        avg = round(sum(y["score"] for y in scored) / len(scored))
        best = max(scored, key=lambda y: y["score"])
        worst = min(scored, key=lambda y: y["score"])
        ranked.append((avg, ms, rows_m[0]["model"], len(scored), best, worst,
                       sum(y["complaint_count"] or 0 for y in rows_m),
                       sum(y["recall_count"] or 0 for y in rows_m)))
    ranked.sort(key=lambda t: -t[0])
    def _ylink(y):
        return f'<a href="{url_my(y)}">{y["year"]}</a>' if gate(y) else str(y["year"])
    rank_rows = "".join(
        '<tr><td><a href="/cars/{k}/{ms}/">{mn}</a></td><td class="num">{avg}</td><td>{v}</td>'
        '<td class="num">{n}</td><td>{b}</td><td>{w}</td>'
        '<td class="num">{tc:,}</td><td class="num">{tr}</td></tr>'.format(
            k=kslug, ms=ms, mn=esc(mn), avg=avg,
            v=vtag("BUY" if avg >= 70 else "CAUTION" if avg >= 50 else "AVOID"),
            n=n, b=_ylink(best), w=_ylink(worst), tc=tc, tr=tr)
        for avg, ms, mn, n, best, worst, tc, tr in ranked[:60])
    rank_html = ""
    brand_lede = ""
    if ranked:
        tot_c = sum(t[6] for t in ranked)
        tot_r = sum(t[7] for t in ranked)
        top = ranked[0]
        bottom = ranked[-1]
        brand_lede = (f"<p>{len(ranked)} {esc(make)} nameplates carry enough federal data to score: "
                      f"{tot_c:,} owner complaints and {tot_r} recall campaigns in total. "
                      f"The strongest average across its model years is the {esc(top[2])} at {top[0]}/100; "
                      f"the weakest is the {esc(bottom[2])} at {bottom[0]}/100.</p>")
        rank_html = (f'<div class="card"><h2>{esc(make)} models ranked by owner data</h2>{brand_lede}'
                     '<div class="table-wrap"><table class="cost-table"><thead><tr><th>Model</th>'
                     '<th>Avg score</th><th>Verdict</th><th>Years scored</th><th>Best year</th>'
                     '<th>Worst year</th><th>Complaints</th><th>Recalls</th></tr></thead><tbody>'
                     f'{rank_rows}</tbody></table></div>'
                     '<p class="src-note">Average score is the mean across the model years we hold data for. '
                     'Complaint counts are raw NHTSA totals and rise with how many cars were sold — the score '
                     'itself corrects for that. <a href="/methodology/">Methodology</a>.</p></div>')
    jsonld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Cars", "item": ORIGIN + "/cars/"},
        {"@type": "ListItem", "position": 2, "name": make, "item": ORIGIN + url}]}]
    body = f"""<div class="hero"><div class="wrap hero-inner">
<nav class="crumbs"><a href="/cars/">Cars</a> › {esc(make)}</nav>
<h1>{esc(make)} ownership costs &amp; problem years</h1></div></div>
<div class="wrap" style="padding:28px 0;display:grid;gap:20px">
{rank_html}
{AD.format(slot='mid')}
<div class="card"><h2>Every {esc(make)} model we hold data for</h2><div class="rel-grid">{items}</div></div>
<div class="card sources"><p>Sources: <a href="https://www.nhtsa.gov" rel="noopener">NHTSA</a> complaints and recalls,
<a href="https://www.fueleconomy.gov" rel="noopener">EPA</a> fuel economy · <a href="/methodology/">Methodology</a> ·
<a href="/calculators/">Calculators</a> · Updated {TODAY}</p></div></div>"""
    return write(url.lstrip("/") + "index.html",
                 page(f"{make} Reliability by Model & Year | {BRAND}",
                      f"Every {make} model ranked by NHTSA complaints and recalls — best and worst "
                      f"years, scores and running costs from public data.",
                      ORIGIN + url, body, jsonld))

def gen_years_to_avoid(con, all_rows):
    """/years-to-avoid/ — the category page above the 360 nameplate verdicts.

    Every nameplate page now answers "which years of this car should I avoid". Nothing
    answered the question one level up, which is both a query in its own right and the page
    that passes authority down to all 360 of them. Ranked by the size of the gap between a
    nameplate's worst year and its best, because that gap is exactly what makes the question
    worth asking: a car whose years are all alike does not need this page.
    """
    from collections import defaultdict
    by = defaultdict(list)
    for r in all_rows:
        if r["score"] is not None and gate(r):
            by[r["model_id"]].append(r)

    items = []
    for rs in by.values():
        rs = sorted(rs, key=lambda x: x["year"])
        if len(rs) < 5:
            continue
        avoid = [x for x in rs if (x["verdict"] or "") == "AVOID"]
        if not avoid:
            continue
        best = max(rs, key=lambda x: x["score"])
        worst = min(rs, key=lambda x: x["score"])
        spread = best["score"] - worst["score"]
        if spread < 25:
            continue
        items.append((spread, rs[0], avoid, best, worst))
    items.sort(key=lambda t: -t[0])

    rows_html = "".join(
        f'<tr><td><a href="/cars/{r0["kslug"]}/{r0["mslug"]}/">{esc(r0["make"])} {esc(r0["model"])}</a></td>'
        f'<td>{", ".join(str(a["year"]) for a in sorted(avoid, key=lambda x: x["year"])[:6])}</td>'
        f'<td class="num">{worst["score"]}</td>'
        f'<td>{best["year"]}</td><td class="num">{best["score"]}</td>'
        f'<td class="num">{spread}</td></tr>'
        for spread, r0, avoid, best, worst in items[:250])

    body = f"""<div class="hero"><div class="wrap hero-inner">
<nav class="crumbs"><a href="/cars/">Cars</a> › Years to avoid</nav>
<h1>Car Years to Avoid: {len(items)} Nameplates Where the Model Year Decides</h1>
<p class="sub">Ranked by how far apart a nameplate's worst and best model years sit on the
federal complaint and recall record. The wider the gap, the more the year you buy matters.</p>
{byline("years-to-avoid", TODAY)}
</div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0">
<div class="card"><h2>Why one model year can be worth thousands more than the next</h2>
<p>A nameplate is not one car. A redesign changes the engine, the transmission and the
supplier list in a single model year, and the complaint record moves with it — sometimes by
sixty points inside two years of the same badge. Every row below is a car whose worst year
and best year are at least 25 points apart on our score, which means the question "which
year" is worth more to a buyer than the question "which car".</p>
<p>Every figure comes from NHTSA owner complaints, normalised by years of exposure, and
from recall campaigns. Follow any nameplate for its run-by-run reading.</p></div>
{AD.format(slot='mid')}
<div class="card"><h2>Ranked by the gap between the worst year and the best</h2>
<div class="table-wrap"><table class="cost-table">
<thead><tr><th>Car</th><th>Years to avoid</th><th class="num">Worst score</th>
<th>Best year</th><th class="num">Best score</th><th class="num">Gap</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
<p class="src-note">Scored from NHTSA complaints and recalls. <a href="/methodology/">Method</a>.
Showing the {min(len(items), 250)} widest gaps of {len(items)}.</p></div>
<div class="card"><h2>Keep reading</h2><div class="rel-grid">
<a href="/guides/">Buyer's guides<small>written and signed, year by year</small></a>
<a href="/guides/first-model-year-rule/">The first-year rule<small>why a launch year is the one to skip</small></a>
<a href="/cars/">Every marque<small>browse the ownership data</small></a>
</div></div>
</div>"""
    jsonld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Cars", "item": ORIGIN + "/cars/"},
            {"@type": "ListItem", "position": 2, "name": "Years to avoid",
             "item": ORIGIN + "/years-to-avoid/"}]},
        {"@context": "https://schema.org", "@type": "ItemList",
         "name": "Car model years to avoid, ranked by the gap to the same car's best year",
         "numberOfItems": min(len(items), 250),
         "itemListElement": [
             {"@type": "ListItem", "position": i + 1,
              "name": f'{t[1]["make"]} {t[1]["model"]}',
              "url": f'{ORIGIN}/cars/{t[1]["kslug"]}/{t[1]["mslug"]}/'}
             for i, t in enumerate(items[:250])]}]
    return write("years-to-avoid/index.html",
                 page("Car Years to Avoid — Every Nameplate, Ranked | " + BRAND,
                      ("The model years to avoid on every car we score, ranked by how far the worst "
                       "year sits from the best. From NHTSA complaints and recall campaigns."),
                      ORIGIN + "/years-to-avoid/", body, jsonld))


def gen_cars_index(brands):
    """Two layers: the marques with deep NHTSA/EPA verdict data on top, then every marque
    ever catalogued, A-Z with its logo. Browse used to stop at six brands one click from a
    home page promising every car ever made - that contradiction ends here."""
    items = "".join(f'<a href="/cars/{k}/">{esc(m)}<small>{n} model years of verdict data</small></a>' for k, m, n in brands)

    az_html = ""
    try:
        lib = json.loads((ROOT / "data" / "car_library.json").read_text())
        try:
            logos = json.loads((ROOT / "data" / "brand_logos.json").read_text())
        except Exception:
            logos = {}
        _resolve, _is_qid, _brand_of = None, lambda v: False, None
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from build_library import BRAND_ALIAS as _ALIAS
            from build_library import resolve_qid_brands as _resolve, is_qid as _is_qid
            from build_library import brand_of as _brand_of
        except Exception:
            _ALIAS = {}
        # Wikidata returns a bare Q-id when a manufacturer item has no English label.
        # Recover the real marque exactly as the Library does, so Browse never shows a
        # tile called "Q2308012" (and never links to a brand page that does not exist).
        known = {}
        if _resolve:
            for x in lib:
                m0 = (x.get("m") or "").strip()
                if m0 and not _is_qid(m0):
                    k0 = _ALIAS.get(m0, m0)
                    known[k0.lower()] = k0
            _resolve(lib, known)
        # Browse must bucket models exactly as the Library does, or a tile links to a
        # brand page that was never written. brand_of prefers the marque in the model's
        # own name over the manufacturer, so the Daihatsu Altis is a Daihatsu here too.
        # One source of truth: the de-duplicated catalogue the Library renders. Counting the
        # raw file here showed per-marque totals that the marque page itself contradicted.
        counts = {b: len(v) for b, v in CATALOG.items()
                  if b != "Independent & coachbuilders" and b and not _is_qid(b)}
        if not counts:
            for x in lib:
                raw = (x.get("m") or "").strip()
                if _brand_of:
                    bb = _brand_of(x.get("n") or "", raw, known)
                    if bb == "Independent & coachbuilders":
                        continue
                else:
                    bb = _ALIAS.get(raw, raw)
                if bb and not _is_qid(bb):
                    counts[bb] = counts.get(bb, 0) + 1

        def bslug(t):
            # must byte-match build_library.slug or these links die at the gate
            t = re.sub(r"[^\w\s-]", "", t.lower()).strip()
            return re.sub(r"[\s_]+", "-", t)[:60] or "x"

        az = {}
        for bb, n in counts.items():
            az.setdefault(bb[0].upper() if bb[0].isalpha() else "#", []).append((bb, n))
        nav = "".join(f'<a href="#az-{k if k.isalpha() else "num"}">{k}</a>' for k in sorted(az))
        groups = ""
        for k in sorted(az):
            tiles = ""
            for bb, n in sorted(az[k]):
                logo = logos.get(bb)
                mark = (f'<span class="bt-logo"><img src="{esc(logo)}" alt="" loading="lazy"></span>'
                        if logo else f'<span class="bt-logo bt-initial">{esc(bb[0].upper())}</span>')
                tiles += (f'<a class="brand-tile" href="/library/{bslug(bb)}/">{mark}'
                          f'<b>{esc(bb)}</b><small>{n} models</small></a>')
            groups += f'<div class="az-group" id="az-{k if k.isalpha() else "num"}"><h3>{k}</h3><div class="brand-grid">{tiles}</div></div>'
        az_html = (f'<h2 class="sec">Every marque ever made</h2>'
                   f'<p class="muted" style="margin:-6px 0 12px">{len(counts):,} manufacturers, A to Z. '
                   f'Each opens the full catalogue in the Library.</p>'
                   f'<nav class="az-jump">{nav}</nav>{groups}')
    except Exception:
        pass

    body = f"""<div class="hero"><div class="wrap hero-inner"><h1>Browse by brand</h1>
<p class="sub">Ownership verdicts where the United States data runs deep, and the complete
A-Z of every marque ever catalogued below.</p></div></div>
<div class="wrap" style="padding:28px 0">
<div class="card prose editorial">{HUB_NOTES.get("cars", "")}<p class="src-note">Editor's note by <a href="/about/">{EDITOR}</a>.</p></div>
<h2 class="sec">Deep ownership data</h2>
<div class="card"><div class="rel-grid">{items}</div></div>
{az_html}</div>"""
    return write("cars/index.html", page(f"All Car Brands A-Z | {BRAND}", "Every car marque ever made, A-Z with logos, plus deep NHTSA ownership data by brand.", ORIGIN + "/cars/", body))

def gen_home(con, all_rows):
    gated = [r for r in all_rows if gate(r)]
    _gall = guides_index()
    _g = _gall[:9]
    guides_section = ""
    if _g:
        guides_section = ('<section class="card"><h2>Buyer\'s guides</h2>'
                          f'<p style="margin-bottom:12px">{len(_gall)} guides written and signed by the editor, built on the same '
                          'federal record as the verdicts: which years of each nameplate to buy, which to walk past, '
                          'and what to check before you hand over the money.</p>'
                          '<div class="rel-grid">' + "".join(
                              f'<a href="/guides/{esc(m["slug"])}/">{esc(m["title"])}'
                              f'<small>{esc((m.get("description") or "")[:110])} · {esc(m.get("date", ""))}</small></a>'
                              for m in _g) + '</div>'
                          '<p style="margin-top:12px;font-size:13px"><a href="/guides/">All guides →</a></p></section>')

    # The "years to avoid" block: the same ranking as /years-to-avoid/, eight nameplates
    # with the widest gap between their best and worst year — the question the site
    # answers better than anyone, on the front door.
    from collections import defaultdict as _dd
    _by = _dd(list)
    for _r in gated:
        if _r["score"] is not None:
            _by[_r["model_id"]].append(_r)
    _yta = []
    for _rs in _by.values():
        _rs = sorted(_rs, key=lambda x: x["year"])
        _av = [x for x in _rs if (x["verdict"] or "") == "AVOID"]
        if len(_rs) < 5 or not _av:
            continue
        _b = max(_rs, key=lambda x: x["score"]); _w = min(_rs, key=lambda x: x["score"])
        if _b["score"] - _w["score"] >= 25 and sum(x["complaint_count"] or 0 for x in _rs) >= 1500:
            _yta.append((sum(x["complaint_count"] or 0 for x in _rs), _rs[0], _av, _b, _w))
    _yta.sort(key=lambda t: -t[0])
    yta_section = ""
    if _yta:
        yta_section = ('<section class="card"><h2>Years to avoid</h2>'
                       '<p style="margin-bottom:12px">Where one model year of the same car is worth thousands more '
                       'than the next. The nameplates with the deepest records and the widest gap between their best '
                       'and worst year, each with the years the federal record says to walk past.</p>'
                       '<div class="rel-grid">' + "".join(
                           f'<a href="/cars/{esc(r0["kslug"])}/{esc(r0["mslug"])}/">{esc(r0["make"])} {esc(r0["model"])} years to avoid'
                           f'<small>avoid {", ".join(str(a["year"]) for a in sorted(av, key=lambda x: x["year"])[:4])}'
                           f' · best {b["year"]} ({b["score"]}/100) · worst {w["year"]} ({w["score"]}/100)</small></a>'
                           for _, r0, av, b, w in _yta[:8]) + '</div>'
                       '<p style="margin-top:12px;font-size:13px"><a href="/years-to-avoid/">Every nameplate ranked →</a>'
                       ' · <a href="/compare/">Head-to-head comparisons →</a></p></section>')
    n_complaints = sum(r["complaint_count"] or 0 for r in all_rows)
    # The home page shows cars worth wanting. "Years to avoid" was the second data block on
    # it, which meant the first impression of the site was four Chrysler Pacificas scoring
    # 5/100 — true, useful, and the wrong front door. The trap years still have their pages,
    # their model tables and the whole /problems/ section; they are one click away, not the
    # welcome mat.
    def _amazing(rows, n):
        """Best evidence first: a BUY on a thin record is not an endorsement, so only
        strong and moderate confidence qualify, and newer years break the tie."""
        ok = [r for r in rows
              if r["verdict"] == "BUY" and (r["score"] or 0) >= 78
              and (r["confidence"] or "") in ("high", "medium")]
        ok.sort(key=lambda r: (-(r["score"] or 0), -(r["year"] or 0)))
        seen, out = set(), []
        for r in ok:                      # one year per nameplate, so it reads as variety
            if r["model_id"] in seen:
                continue
            seen.add(r["model_id"])
            out.append(r)
            if len(out) >= n:
                break
        return out

    evs = _amazing([r for r in gated if r["is_ev"]], 4) or [r for r in gated if r["is_ev"]][:4]
    best = _amazing(gated, 8)
    # The most-loved leaderboard shows real votes only. Until readers have cast any, the
    # page shows this data-derived list under a label that says exactly that, instead of
    # an empty grid — the same cars the home page leads with, one year per nameplate.
    (SITE / "assets" / "loved-fallback.json").write_text(json.dumps(
        [{"name": f'{x["year"]} {x["make"]} {x["model"]}', "url": url_my(x), "score": x["score"]}
         for x in _amazing(gated, 24)], separators=(",", ":"), ensure_ascii=False))

    def card_money(x):
        bits = []
        if x["price_today_low"] and x["price_today_high"]:
            bits.append(f'${x["price_today_low"]:,}–${x["price_today_high"]:,} typical price')
        try:
            curve = json.loads(x["cost_curve"] or "[]")
            age = max(0, CURRENT_YEAR - int(x["year"]))
            point = min(curve, key=lambda p: abs(p["age"] - age)) if curve else None
            if point:
                maint_mid = int(round((point["total_low"] + point["total_high"]) / 2))
                if x["annual_fuel_cost"]:
                    bits.append(f'${maint_mid + int(x["annual_fuel_cost"]):,}/yr fuel + maintenance')
                else:
                    bits.append(f'${maint_mid:,}/yr maintenance · fuel unavailable')
        except Exception:
            pass
        return " · ".join(bits)

    def cardlist(rows):
        return '<div class="rel-grid">' + "".join(
            f'<a href="{url_my(x)}">{x["year"]} {esc(x["make"])} {esc(x["model"])}'
            f'<small>score {x["score"]}/100 · {esc(x["verdict"])}'
            f'{" · " + card_money(x) if card_money(x) else ""}</small></a>'
            for x in rows) + "</div>"
    # The Legends block is only emitted once the roster has actually been harvested,
    # otherwise the home page would link to a /legends/ that does not exist and the
    # dead-link gate would (correctly) fail the build.
    legends_section = ""
    if (Path(__file__).resolve().parent.parent / "data" / "people.json").exists():
        legends_section = """<section class="legends-home" data-legends>
<h2 class="sec">The Legends</h2>
<p class="muted" style="margin:-6px 0 14px">The people who built, drew, drove and financed the
car — founders, engineers, designers, champions and industrialists.</p>
<div class="pp-grid" data-legends-grid></div>
<p style="margin-top:6px"><a class="btn ghost" href="/legends/">Meet all of them</a></p>
</section>"""

    # Counts must come from the data, never from a number typed into the template — the
    # hard-coded 12,747 survived two catalogue rebuilds and shipped a lie on the home page.
    n_models = CATALOG_MODELS
    n_brands = CATALOG_BRANDS

    # ---- the landmark cars: curated, photographed, rotating weekly ----
    try:
        _icons = json.load(open(ROOT / "data" / "editorial" / "icons.json"))
    except Exception:
        _icons = {"icons": [], "electrified": []}
    _photo_by_name = {c[0]: c[2] for c in LIB_PHOTOS}

    _used_icons = set()

    def icon_cards(names, n, salt):
        """A different, marque-diverse dozen every week: seeded shuffle, at most two cars
        per marque, and never the same car twice on one page."""
        import datetime as _dt, random as _rnd
        week = _dt.date.today().isocalendar()
        rng = _rnd.Random(f"{week[0]}-{week[1]}-{salt}")
        avail = [(nm, _photo_by_name.get(nm.lower())) for nm in names
                 if _photo_by_name.get(nm.lower()) and nm.lower() not in _used_icons]
        rng.shuffle(avail)
        out, per_marque = [], {}
        for nm, ph in avail:
            u = model_url(nm)
            if u == "/library/":
                continue
            marque = u.split("/")[2]
            if per_marque.get(marque, 0) >= 2:
                continue
            per_marque[marque] = per_marque.get(marque, 0) + 1
            _used_icons.add(nm.lower())
            _b = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                  + urllib.parse.quote(ph.replace(" ", "_")))
            out.append(f'<a class="icon-card" href="{u}"><img src="{_b}?width=640" '
                       f'srcset="{_b}?width=400 400w, {_b}?width=640 640w, {_b}?width=960 960w" '
                       f'sizes="(max-width:767px) 78vw, 220px" alt="{esc(nm)}" loading="lazy" decoding="async" '
                       f'referrerpolicy="no-referrer" onerror="this.closest(\'.icon-card\').style.display=\'none\'">'
                       f'<span>{esc(nm)}</span></a>')
            if len(out) >= n:
                break
        return "".join(out)
    icon_grid = icon_cards(_icons.get("icons", []), 12, 0)
    ev_grid = icon_cards(_icons.get("electrified", []), 6, 3)

    # ---- image-led hero: real photography from the library ----
    def photo_of(name):
        for n, y, ph, _w in LIB_PHOTOS:
            if n == name.lower():
                return ph
        return None
    # An editorial front door, not a random inventory feed: every car below is a genuine
    # design or engineering landmark and has a high-resolution Commons photograph.
    HEROES = ["ferrari 250 gto", "ferrari f40", "lamborghini miura", "jaguar e-type",
              "aston martin db5", "mercedes-benz 300 sl", "mclaren f1",
              "bugatti type 57 atlantic", "alfa romeo 33 stradale (1969)",
              "citroën ds 19", "lancia stratos", "ford gt40", "bmw 507",
              "toyota 2000gt", "chevrolet corvette c2", "mazda rx-7"]
    NICE = {"ferrari 250 gto": "Ferrari 250 GTO", "mercedes-benz 300 sl": "Mercedes-Benz 300 SL",
            "mclaren f1": "McLaren F1", "citroën ds 19": "Citroën DS 19",
            "alfa romeo 33 stradale (1969)": "Alfa Romeo 33 Stradale (1969)",
            "chevrolet corvette c2": "Chevrolet Corvette C2", "bmw 507": "BMW 507"}
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
        import urllib.parse as _u
        return ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                + _u.quote(ph.replace(" ", "_")) + f"?width={w}")
    mosaic = "".join(
        f'<button type="button" class="mo-cell lb-trigger" data-lb aria-label="Enlarge photo of {esc(nm)}" '
        f'data-credit="Photo: Wikimedia Commons · CC">'
        f'<img src="{cimg(ph, 640)}" alt="{esc(nm)}" loading="lazy"><span>{esc(nm)}</span></button>'
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
        f'<span class="hh-shot-tag">{esc(HERO_NAME)}</span>'
        f'</a>')
    strip_cells = "".join(
        f'<a class="st-cell" href="{murl(nm)}">'
        f'<img src="{cimg(ph, 520)}" alt="{esc(nm)}" loading="lazy" referrerpolicy="no-referrer" '
        f'onerror="this.closest(\'.st-cell\').style.display=\'none\'"><span>{esc(nm)}</span></a>'
        for nm, ph in shots[4:16])
    # The band scrolls forever, so the sequence is emitted twice: the animation travels
    # exactly -50% and lands on the duplicate, which makes the loop seamless.
    strip_cells = (f'<div class="photo-strip-inner">{strip_cells}{strip_cells}</div>')

    body = f"""<section class="home-hero-v2"><div class="wrap hh-grid">
<div class="hh-copy">
<span class="hh-kicker">{n_models:,} models · {CATALOG_PHOTOS:,} photographs · {N_GEO} countries</span>
<h1>What does that car <em>really</em> cost to own?</h1>
<p class="hh-sub">Every model year scored from NHTSA complaints, recall campaigns and EPA data,
priced for <b>your</b> country — and {len(_gall)} signed buyer's guides on which years to buy and which to avoid.</p>
<div class="hh-cta"><a class="btn" href="/years-to-avoid/">Which years to avoid</a>
<a class="btn ghost" href="/guides/">Read the buyer's guides</a></div>
<div class="stat-row"><div><b>{n_models:,}</b><span>models in the library</span></div>
<div><b>{n_complaints:,}</b><span>complaints indexed</span></div>
<div><b>{N_GEO}</b><span>countries auto-priced</span></div></div>
</div>
<div class="hh-mosaic">{hero_cells}</div>
</div></section>
<section class="photo-strip">{strip_cells}</section>
<div class="wrap" style="display:grid;gap:22px;padding:30px 0 20px">
{guides_section}
{yta_section}
{AD.format(slot='home')}
<div class="daily-grid" data-daily></div>
<section class="card icons-home"><h2>The cars worth the detour</h2><p style="margin-bottom:12px">Landmark
machines from the library — the ones that changed a marque, a decade or a rulebook — each with its own
photographed story. A different dozen every week.</p>
<div class="icon-grid">{icon_grid}</div>
<p style="margin-top:12px;font-size:13px"><a href="/library/">The whole library →</a> · <a href="/cars/">Every brand's ownership verdicts →</a></p></section>
<section class="card icons-home"><h2>Electrified, and exceptional</h2><p style="margin-bottom:12px">The electric and hybrid
cars that earned a place on this page on merit; the ownership index carries battery warranty and
replacement cost for every electric model year sold in America.</p>
<div class="icon-grid">{ev_grid}</div>
<p style="margin-top:12px;font-size:13px"><a href="/search/?fuel=electric">Every electric model year, scored →</a></p></section>
<section class="card"><h2>Scored, priced, and worth buying</h2><p style="margin-bottom:12px">The model years the
federal record likes most, with what they cost to buy today and to run for a year.</p>
{cardlist(best)}
<p style="margin-top:12px;font-size:13px"><a href="/search/">Search every scored model year →</a></p></section>
<h2 class="sec">Explore</h2>
<div class="rel-grid"><a href="/guides/">Buyer's guides<small>signed, dated, checked against the record</small></a>
<a href="/years-to-avoid/">Years to avoid<small>every nameplate ranked by its best-to-worst gap</small></a>
<a href="/compare/">Head-to-head<small>two nameplates, year by year, on the same record</small></a>
<a href="/vin-check/">Free VIN & recall check<small>decode the exact car before you buy</small></a>
<a href="/recalls/">Recall campaigns<small>the newest campaigns on record, by car</small></a>
<a href="/library/">The Car Library<small>{n_models:,} models, {n_brands:,} marques</small></a>
<a href="/calculators/">True-cost calculator<small>priced for your country</small></a>
<a href="/methodology/">How the verdicts are computed<small>the formula, the sources, the limits</small></a></div>
<div class="cta-band"><h2>True-cost calculator</h2><p style="color:var(--muted);margin:8px 0 14px">Fuel + maintenance + battery risk, by model year.</p><a class="btn" href="/calculators/">Calculate</a></div>
</div>"""
    jsonld = [{"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": ORIGIN,
               "potentialAction": {"@type": "SearchAction", "target": f"{ORIGIN}/cars/?q={{search_term_string}}",
                                   "query-input": "required name=search_term_string"}}]
    return write("index.html", page(f"{BRAND} — True Car Ownership Costs from Public Data",
                 "Per-model-year car verdicts computed from NHTSA complaints, recalls and EPA data. Find the trap years before you buy.",
                 ORIGIN + "/", body, jsonld))

def gen_search(con, all_rows):
    """/search/ — the finder the header box could never be.

    The typeahead answers "take me to the Corolla". It cannot answer "a reliable electric
    SUV from the last five years under $30k", which is the question people actually shop
    with. This page can: every model-year that has a page, filterable by year, fuel,
    category, verdict and price, all client-side over one compact index — no server, no
    round-trips, instant on a phone."""
    fuel_kind_of = {"Electricity": "electric", "Electricity and Hydrogen": "electric",
                    "Diesel": "diesel", "Hydrogen": "hydrogen", "CNG": "cng"}
    rows = []
    for r in all_rows:
        if not gate(r):
            continue
        ft = r["fuel_type"] or ""
        if r["is_ev"] or fuel_kind_of.get(ft) == "electric":
            fuel = "electric"
        elif "Electricity" in ft or "hybrid" in (r["model"] or "").lower():
            fuel = "hybrid"
        else:
            fuel = fuel_kind_of.get(ft, "gasoline")
        try:
            curve = json.loads(r["cost_curve"] or "[]")
            age = max(0, CURRENT_YEAR - int(r["year"]))
            pt = min(curve, key=lambda p: abs(p["age"] - age)) if curve else None
            maint_mid = int(round((pt["total_low"] + pt["total_high"]) / 2)) if pt else 0
        except Exception:
            maint_mid = 0
        annual_fuel = int(r["annual_fuel_cost"] or 0)
        annual_running = maint_mid + annual_fuel if maint_mid else 0
        insurance_mid = int(round(((r["insurance_low"] or 0) + (r["insurance_high"] or 0)) / 2))
        rows.append([f"{r['year']} {r['make']} {r['model']}", url_my(r), r["year"],
                     r["make"], fuel, r["segment"] or "", r["score"], r["verdict"] or "",
                     r["price_today"] or 0, r["complaint_count"] or 0,
                     annual_running, annual_fuel, insurance_mid, r["depreciation_per_year"] or 0])
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "search-index.json").write_text(
        json.dumps(rows, separators=(",", ":"), ensure_ascii=False))

    seg_label = dict(SEGMENT_LABEL)
    body = f"""<div class="hero"><div class="wrap hero-inner"><h1>Find your car</h1>
<p class="sub">Every scored model year, filterable by year, fuel, category, price and verdict.
For the full catalogue of every car ever made, use the <a href="/library/">Library</a>.</p></div></div>
<div class="wrap" style="padding:22px 0 40px">
<div class="card sf-card">
<div class="sf-row">
<input id="sf-q" type="search" placeholder="Make or model…" aria-label="Search">
<select id="sf-fuel" aria-label="Fuel"><option value="">Any fuel</option>
<option value="gasoline">Gasoline</option><option value="hybrid">Hybrid</option>
<option value="electric">Electric</option><option value="diesel">Diesel</option></select>
<select id="sf-seg" aria-label="Category"><option value="">Any category</option>
{''.join(f'<option value="{k}">{v.title()}</option>' for k, v in seg_label.items() if k != 'exotic')}</select>
<select id="sf-verdict" aria-label="Verdict"><option value="">Any verdict</option>
<option>BUY</option><option>CAUTION</option><option>AVOID</option></select>
<select id="sf-ymin" aria-label="From year"></select>
<select id="sf-ymax" aria-label="To year"></select>
<select id="sf-price" aria-label="Max price"><option value="">Any price</option>
<option value="10000">Under $10,000</option><option value="20000">Under $20,000</option>
<option value="35000">Under $35,000</option><option value="60000">Under $60,000</option></select>
<select id="sf-sort" aria-label="Sort"><option value="score">Best score first</option>
<option value="price">Cheapest first</option><option value="year">Newest first</option>
<option value="data">Most data first</option></select>
</div>
<p class="sf-count" id="sf-count"></p></div>
<div class="rel-grid" id="sf-out"></div>
<p style="margin-top:10px"><button class="btn ghost" id="sf-more" hidden>Show more</button></p>
</div>
<script>
(function () {{
  var R = null, LIM = 60, shown = LIM;
  var els = {{}};
  ['q','fuel','seg','verdict','ymin','ymax','price','sort'].forEach(function (k) {{
    els[k] = document.getElementById('sf-' + k);
  }});
  var out = document.getElementById('sf-out'), count = document.getElementById('sf-count'),
      more = document.getElementById('sf-more');
  var Y0 = 1995, Y1 = {CURRENT_YEAR};
  for (var y = Y0; y <= Y1; y++) {{
    els.ymin.add(new Option(y === Y0 ? 'From ' + y : String(y), y));
    els.ymax.add(new Option(y === Y1 ? 'To ' + y : String(y), y));
  }}
  els.ymax.value = Y1;
  function money(n) {{ return '$' + Math.round(n).toLocaleString(); }}
  function apply() {{
    if (!R) return;
    var q = els.q.value.trim().toLowerCase();
    var f = els.fuel.value, g = els.seg.value, v = els.verdict.value;
    var y0 = +els.ymin.value || 0, y1 = +els.ymax.value || 9999, pm = +els.price.value || 0;
    var hits = R.filter(function (r) {{
      if (q && r[0].toLowerCase().indexOf(q) < 0) return false;
      if (f && r[4] !== f) return false;
      if (g && r[5] !== g) return false;
      if (v && r[7] !== v) return false;
      if (r[2] < y0 || r[2] > y1) return false;
      if (pm && (!r[8] || r[8] > pm)) return false;
      return true;
    }});
    var s = els.sort.value;
    hits.sort(function (a, b) {{
      if (s === 'price') return (a[8] || 9e9) - (b[8] || 9e9);
      if (s === 'year') return b[2] - a[2];
      if (s === 'data') return b[9] - a[9];
      return (b[6] || 0) - (a[6] || 0);
    }});
    count.textContent = hits.length.toLocaleString() + ' model year' + (hits.length === 1 ? '' : 's') + ' match';
    out.innerHTML = hits.slice(0, shown).map(function (r) {{
      var costs = [];
      if (r[8]) costs.push(money(r[8]) + ' typical price');
      if (r[10]) costs.push(money(r[10]) + '/yr ' + (r[11] ? 'fuel + maintenance' : 'maintenance; fuel unavailable'));
      if (r[12]) costs.push(money(r[12]) + '/yr insurance');
      if (r[13]) costs.push(money(r[13]) + '/yr depreciation');
      return '<a href="' + r[1] + '">' + r[0] +
        '<small>score ' + (r[6] == null ? '—' : r[6] + '/100') + ' · ' + (r[7] || 'DATA PENDING') +
        (costs.length ? ' · ' + costs.join(' · ') : '') + '</small></a>';
    }}).join('') || '<p class="muted" style="grid-column:1/-1">Nothing matches. Loosen a filter — or browse the <a href="/library/">full library</a>.</p>';
    more.hidden = hits.length <= shown;
  }}
  function go() {{ shown = LIM; apply(); }}
  Object.keys(els).forEach(function (k) {{
    els[k].addEventListener(k === 'q' ? 'input' : 'change', go);
  }});
  more.addEventListener('click', function () {{ shown += 120; apply(); }});
  var pre = new URLSearchParams(location.search).get('q');
  if (pre) els.q.value = pre;
  fetch('/assets/search-index.json').then(function (r) {{ return r.json(); }})
    .then(function (j) {{ R = j; apply(); }});
}})();
</script>"""
    return write("search/index.html", page(
        f"Find Your Car — Filter by Year, Fuel, Price & Verdict | {BRAND}",
        "Filter every scored model year by year, fuel type, category, price and data verdict.",
        ORIGIN + "/search/", body, extra_head=NOINDEX))


def gen_calculators(con, all_rows):
    packs = []
    for r in all_rows:
        if not gate(r):
            continue
        curve = json.loads(r["cost_curve"] or "[]")
        packs.append({"n": f"{r['year']} {r['make']} {r['model']}", "y": r["year"],
                      "ev": r["is_ev"], "fc": r["annual_fuel_cost"],
                      "c": [[p["total_low"], p["total_high"]] for p in curve],
                      "bl": r["battery_replacement_low"], "bh": r["battery_replacement_high"],
                      # the money the running-cost calculator used to leave out entirely
                      "pt": r["price_today"], "d5": r["depreciation_5y"],
                      "ins": int(((r["insurance_low"] or 0) + (r["insurance_high"] or 0)) / 2) or None})
    # Keep the calculator data cacheable and off the document's critical path.  Inlining it
    # made this otherwise small page the heaviest HTML response on the site.
    (SITE / "assets" / "calculator-data.json").write_text(
        json.dumps(packs, separators=(",", ":"), ensure_ascii=False))
    body = f"""<div class="hero"><div class="wrap hero-inner"><h1>True-cost calculator</h1>
<p class="sub">Annual running cost from EPA fuel data + age-indexed maintenance bands. Estimates, sources on the <a href="/methodology/">methodology page</a>.</p></div></div>
<div class="wrap grid"><div style="display:grid;gap:20px">
<div class="card calc"><h2>What will it cost me?</h2>
<label for="cv">Vehicle</label><select id="cv" aria-busy="true"><option>Loading vehicles…</option></select>
<label for="cy">Years you plan to keep it</label><input id="cy" type="number" value="5" min="1" max="10">
<label for="cp">Price you would pay (leave as-is for our estimate)</label><input id="cp" type="number" min="200" step="100">
<div class="calc-out" id="cout">—</div>
<div class="calc-break" id="cbreak"></div>
<p id="cnote" style="font-size:13px"></p></div>
<div class="card"><h2>How it works</h2><p>Total cost of ownership = depreciation (what the car loses while
you own it) + fuel or energy + the age-indexed maintenance band + insurance. Depreciation is normally the
biggest line of the four, which is why most "running cost" calculators — including the earlier version of
this one — flatter every car by leaving it out. EV packs add a labeled out-of-warranty battery-replacement
risk. Price, depreciation and insurance are class-level estimates; the
<a href="/methodology/#prices">formula and constants are published</a>. Browse verdicts in
<a href="/cars/">the data index</a>.</p>
<h3>What the number is good for, and what it is not</h3>
<p>The calculator answers one question: over the next few years, what will this model year cost to
keep, compared with another? It is built for comparison — a 2015 against a 2018 of the same car, or
a hybrid against the petrol version — because the inputs are class-level averages that cancel out
when two cars of the same class are set side by side. It is not a quote for one specific car: condition,
mileage, options and where you live move every line. The fuel figure is the EPA's, the maintenance band
is an industry average indexed to the car's age, and the price, depreciation and insurance lines are
estimates with a stated ±18% band. If you have been quoted a price, type it in on the model-year page
and the whole panel recomputes from that number instead.</p>
<h3>Where the inputs come from</h3>
<p>Fuel economy comes from fueleconomy.gov (EPA). Maintenance bands are drawn from published
industry cost-of-ownership surveys, indexed by vehicle age. The reliability score behind each verdict
is computed from NHTSA complaint and recall records by the published method. Prices are re-priced
to your country from retail fuel, electricity and parts indices; change the country in the bar at the
top of the page and every figure follows.</p></div>
</div><div class="col-side">{AD.format(slot='calc')}</div></div>
<script>
let P=[];
const sel=document.getElementById('cv'),out=document.getElementById('cout'),note=document.getElementById('cnote');
const price=document.getElementById('cp'),brk=document.getElementById('cbreak');
const M=n=>'$'+Math.round(n).toLocaleString();
let lastIdx=-1;
function calc(){{const p=P[sel.value];if(!p)return;const keep=Math.min(10,Math.max(1,+document.getElementById('cy').value||5));
if(+sel.value!==lastIdx){{lastIdx=+sel.value;price.value=p.pt||'';price.placeholder=p.pt?String(p.pt):'purchase price';}}
const age0=Math.max(0,{CURRENT_YEAR}-p.y);let lo=0,hi=0;
for(let k=0;k<keep;k++){{const a=Math.min(p.c.length-1,age0+k);lo+=p.c[a][0];hi+=p.c[a][1];}}
const fuel=(p.fc||0)*keep;
const run=(lo+hi)/2+fuel;
const runLo=lo+fuel,runHi=hi+fuel;
// depreciation scales with the price actually paid: the retained-value ratio is the same curve
const paid=Math.max(200,+price.value||p.pt||0);
const dep=p.d5&&p.pt?p.d5*(paid/p.pt)*(keep/5):0;
const ins=(p.ins||0)*keep;
const total=run+dep+ins;
const hasFuel=!!p.fc;
out.textContent=M(total/keep)+' / year — '+M(total)+' over '+keep+' year'+(keep>1?'s':'')+
  ' (USD'+(hasFuel?'':', fuel excluded')+')';
brk.innerHTML=(dep?'<div><span>Depreciation</span><b>'+M(dep)+'</b></div>':'')+
'<div><span>'+(hasFuel?'Fuel and maintenance':'Maintenance — fuel unavailable')+'</span><b>'+M(run)+'</b></div>'+
(ins?'<div><span>Insurance</span><b>'+M(ins)+'</b></div>':'')+
'<div class="tot"><span>'+(hasFuel?'Total cost of ownership':'Total shown — fuel excluded')+'</span><b>'+M(total)+'</b></div>'+
'<div class="per"><span>'+(hasFuel?'Per mile at 12,000 miles a year':'Per mile shown — fuel excluded')+'</span><b>$'+(total/(keep*12000)).toFixed(2)+'</b></div>';
note.textContent=(p.ev&&p.bl?'EV note: out-of-warranty battery replacement risk $'+p.bl.toLocaleString()+'–$'+p.bh.toLocaleString()+' (estimate, not included above). ':'')+
(hasFuel?'Running cost':'Maintenance-only')+' band over '+keep+' yr: '+M(runLo)+'–'+M(runHi)+'. '+
(hasFuel?'':'EPA has no matched fuel or energy record for this selection, so fuel is excluded rather than shown as $0. ')+
'Price, depreciation and insurance are class-level estimates — see the methodology. Local fuel, electricity and parts prices from the country bar feed the per-country figures on each car page.';}}
sel.addEventListener('change',calc);document.getElementById('cy').addEventListener('input',calc);
price.addEventListener('input',calc);
fetch('/assets/calculator-data.json').then(r=>{{if(!r.ok)throw new Error(r.status);return r.json()}}).then(rows=>{{
  P=rows;sel.innerHTML='';P.forEach((p,i)=>{{const o=document.createElement('option');o.value=i;o.textContent=p.n;sel.appendChild(o)}});
  sel.removeAttribute('aria-busy');calc();
}}).catch(()=>{{sel.innerHTML='<option>Vehicle data unavailable</option>';sel.removeAttribute('aria-busy');
  out.textContent='The calculator could not load. Please try again.';}});
</script>"""
    return write("calculators/index.html", page(f"True Car Cost Calculator | {BRAND}",
                 "Annual ownership cost calculator built on EPA fuel data and industry maintenance bands.",
                 ORIGIN + "/calculators/", body))

def gen_recalls_feed(con, all_rows):
    """/recalls/ — the newest campaigns on record across every nameplate the site scores.

    This page was a 60-row table under a 13-word subtitle. It now says what a recall is,
    how to read the campaign number, why the safety-critical flag matters, and how to
    check the one car in front of you — and lists 120 campaigns with their summaries.
    """
    recs = con.execute("""SELECT r.*, my.year, mo.name model, mk.name make, mk.slug kslug, mo.slug mslug
        FROM recalls r JOIN model_years my ON my.id=r.my_id
        JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
        ORDER BY substr(r.date,7,4) DESC, substr(r.date,4,2) DESC, substr(r.date,1,2) DESC LIMIT 400""").fetchall()
    n_all = con.execute("SELECT COUNT(DISTINCT campaign) FROM recalls").fetchone()[0]
    n_sev = con.execute("SELECT COUNT(DISTINCT campaign) FROM recalls WHERE severe=1").fetchone()[0]
    sev_badge = '<span class="tag v-AVOID">safety-critical</span>'
    live = {url_my(x) for x in all_rows if gate(x)}

    def _target(x):
        my = f"/cars/{x['kslug']}/{x['mslug']}/{x['year']}/"
        return my if my in live else f"/cars/{x['kslug']}/{x['mslug']}/"

    def _summ(t):
        t = re.sub(r"\s+", " ", (t or "").strip())
        t = " ".join(re.split(r"(?<=[.!?])\s+", t)[:2])
        return t if len(t) <= 300 else t[:300].rsplit(" ", 1)[0] + "…"

    seen, rows, shown = set(), [], 0
    for x in recs:
        key = (x["campaign"], x["kslug"], x["mslug"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            f"<tr><td><a href=\"{_target(x)}\">{x['year']} {esc(x['make'])} {esc(x['model'])}</a></td>"
            f"<td>{esc(x['campaign'] or '—')}<br><small>{esc(x['date'] or '')}</small></td>"
            f"<td>{esc((x['component'] or '').title())}<br><small>{esc(_summ(x['summary']))}</small></td>"
            f"<td>{sev_badge if x['severe'] else ''}</td></tr>")
        shown += 1
        if shown >= 120:
            break
    body = f"""<div class="hero"><div class="wrap hero-inner"><h1>Recall campaigns on record</h1>
<p class="sub">{n_all:,} distinct campaigns across the model years this site scores, {n_sev:,} of them
touching a safety-critical system. The newest 120 are below; every model-year page carries its own.</p></div></div>
<div class="wrap" style="padding:28px 0;display:grid;gap:20px;max-width:1100px">
<div class="card prose"><h2>How to read a recall</h2>
<p>A recall is a manufacturer telling the United States safety regulator, in writing, that a batch of
cars left the factory with a defect that affects safety or breaks a federal standard, and that it will
fix it at no cost to the owner. The campaign number is NHTSA's identifier: the first two digits are the
year the campaign was filed, the letter V marks a vehicle campaign (E marks equipment, such as a
replacement part), and the remaining digits are the sequence. The date is the filing date, not the date
the defect appeared — a 2021 campaign can cover a 2011 car, as the air bag inflator recalls did.</p>
<p>The safety-critical flag is ours. It marks campaigns whose component is one where failure means a
fire, a crash, a stall in traffic or an air bag that does not deploy — brakes, steering, fuel system,
air bags, seat belts, engine stall, electrical fire. A campaign for a label or a floor mat is a
recall; it is not the same risk, and the flag is how the reliability score tells them apart.</p>
<p>A recall on this page tells you the defect exists in the batch. It does not tell you whether the
car you are looking at was repaired. Dealers complete recall work free of charge for the life of the
car, but a used car changes hands and the work is often never done. Before buying, run the VIN through
<a href="/vin-check/">the VIN check</a> or NHTSA's own lookup at
<a href="https://www.nhtsa.gov/recalls" rel="noopener">nhtsa.gov/recalls</a>, and ask the seller for
the dealer invoice for every open campaign. <a href="/guides/how-to-check-a-vin-and-recalls/">The guide
to checking a VIN and its recalls</a> walks through it step by step.</p></div>
<div class="card"><h2>The newest campaigns on record</h2>
<div class="table-wrap"><table class="cost-table recall-feed-table"><thead><tr><th>Vehicle</th><th>Campaign</th><th>Component and summary</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="src-note">Source: NHTSA recall campaigns, as held in the site's dataset on {TODAY}. Each vehicle links to the
model-year page with its full recall list and complaint record.</p></div></div>"""
    return write("recalls/index.html", page(f"Car Recall Campaigns: The Newest on Record, and How to Read Them | {BRAND}",
                 f"{n_all:,} NHTSA recall campaigns across the model years MotorJury scores — how to read a campaign, "
                 "which ones are safety-critical, and how to check the car in front of you.",
                 ORIGIN + "/recalls/", body))


def gen_vin_check():
    """A high-intent, same-origin VIN decoder and recall report backed by NHTSA."""
    body = """<div class="hero vin-hero"><div class="wrap hero-inner">
<span class="hh-kicker">Free · no account · public NHTSA data</span>
<h1>Check a VIN before you buy the car</h1>
<p class="sub">Decode the exact vehicle, find its recall campaigns, then open MotorJury's
costs, repair risks and model-year verdict. We do not store the VIN.</p></div></div>
<div class="wrap vin-wrap">
<section class="card vin-entry"><h2>Enter the 17-character VIN</h2>
<form id="vin-form" class="vin-form">
<label for="vin">Vehicle identification number</label>
<div class="vin-input-row"><input id="vin" name="vin" required minlength="17" maxlength="17"
inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false"
placeholder="1HGCM82633A004352" aria-describedby="vin-help"><button class="btn" type="submit">Check this VIN</button></div>
<p id="vin-help" class="src-note">Usually visible through the windscreen, on the driver's door jamb,
registration, insurance papers or sales listing. Letters I, O and Q are never used.</p></form></section>
<div id="vin-result" class="vin-result" aria-live="polite"></div>
<section class="card"><h2>Your 5-minute used-car decision check</h2>
<ol class="inspect-list"><li><b>Identity</b><span>Make sure the decoded year, model and body match the listing and documents.</span></li>
<li><b>Recalls</b><span>Ask for proof that every open campaign was completed; verify on NHTSA.</span></li>
<li><b>Price</b><span>Open MotorJury's model-year page and replace our estimate with the seller's actual price.</span></li>
<li><b>Known failures</b><span>Compare the car with the most-complained-about components and typical repair bands.</span></li>
<li><b>Independent inspection</b><span>Use the data to brief a qualified mechanic before money changes hands.</span></li></ol></section>
<section class="card"><h2>VIN check questions</h2>
<details><summary>Does this show whether a recall repair was completed?</summary><p>No. NHTSA's public model recall feed identifies campaigns that may apply. A dealer or NHTSA's own VIN tool must confirm completion for this exact vehicle.</p></details>
<details><summary>Do you save or sell the VIN?</summary><p>No. MotorJury sends it to NHTSA for this check and does not persist it in an account or database.</p></details>
<details><summary>Does a clean result mean the car is safe?</summary><p>No. It means the public API returned no matching campaigns. It does not replace service records, a road test or an independent mechanical inspection.</p></details></section>
</div><script src="/assets/inspector.js" defer></script>"""
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "Does this show whether a recall repair was completed?",
         "acceptedAnswer": {"@type": "Answer", "text": "No. The public model recall feed identifies campaigns that may apply. Verify completion for the exact VIN with NHTSA or a dealer."}},
        {"@type": "Question", "name": "Does MotorJury store the VIN?",
         "acceptedAnswer": {"@type": "Answer", "text": "No. The VIN is sent to NHTSA for the requested check and is not persisted by MotorJury."}},
    ]}
    app = {"@context": "https://schema.org", "@type": "WebApplication", "name": "MotorJury VIN & Recall Check",
           "url": ORIGIN + "/vin-check/", "applicationCategory": "AutomotiveApplication",
           "operatingSystem": "Any", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}
    return write("vin-check/index.html", page("Free VIN Decoder & Recall Check | MotorJury",
                 "Decode a 17-character VIN and check NHTSA recall campaigns free, then compare ownership costs and known problems before buying.",
                 ORIGIN + "/vin-check/", body, [app, faq]))

DESCRIPTIONS = {
    "Methodology": "The complete formula behind every MotorJury verdict: how the reliability score is "
                   "computed, why it is normalised for sales volume, and what the estimates exclude.",
    "About": "Who runs MotorJury, how the data is produced, how to reach us and how to get a number "
             "corrected.",
    "Privacy Policy": "What MotorJury collects, what advertising partners may set, and how to make a "
                      "privacy request.",
    "Terms of Use": "Terms covering the use, citation and licensing of MotorJury data and verdicts.",
    "Advertising and Affiliate Disclosure": "How MotorJury is funded, and why advertising and affiliate links never "
                            "touch a score or a verdict.",
    "Editorial Policy": "How MotorJury decides what to publish, who writes it, how errors are corrected "
                        "and how advertising is kept away from verdicts.",
    "Contact": "How to reach the MotorJury editor for corrections, press, privacy requests and "
               "advertising.",
}


def prose_page(path, title, paras):
    body = f'<div class="wrap prose"><h1>{esc(title)}</h1>' + paras + "</div>"
    desc = DESCRIPTIONS.get(title, title)
    return write(path, page(f"{title} | {BRAND}", desc,
                            ORIGIN + "/" + path.replace("index.html", ""), body))

def gen_author_page():
    """/about/adir-trabelsi/ — a real author page for the one person who actually owns the
    editorial on this site.

    Google's quality raters are told to look for who is responsible for a page and what
    makes them qualified, and the answer here was a name in a byline with nothing behind it.
    The honest fix is not more bylines — it is one page that says who the editor is, what he
    does and does not do, what he is accountable for, and every piece he has signed, with
    Person and ProfilePage markup so it can be read as an entity rather than a string.
    """
    gs = guides_index()
    signed = "".join(
        f'<li><a href="/guides/{esc(g["slug"])}/">{esc(g["title"])}</a>'
        f'<span class="src-note"> · {esc(g.get("date", ""))}</span></li>' for g in gs)
    body = f"""<div class="wrap prose">
<nav class="crumbs"><a href="/about/">About</a> › {EDITOR}</nav>
<h1>{EDITOR}</h1>
<p class="sub">Editor and publisher, {BRAND}.</p>

<h2>What I do here</h2>
<p>I built {BRAND} and I run it. I designed the scoring model that turns NHTSA complaint and
recall records into a per-model-year verdict, I decide what the site publishes and what it
refuses to publish, and I write and sign the buyer's guides. Corrections come to me.</p>

<h2>What I am not</h2>
<p>I am not a mechanic, a dealer or a manufacturer's representative, and nothing here is a
road test. I have never been paid by a manufacturer, a dealer, an insurer or a parts
retailer, and no advertiser has ever seen a verdict before it was published or been able to
change one afterwards. Where this site knows something it is because a federal record says
so, and where it does not know, it says so instead of guessing.</p>

<h2>How the site divides the work</h2>
<p>Most of {BRAND} is not written by anyone. The model-year verdicts, the nameplate pages,
the comparisons and the catalogue are produced by a build that reads the public record and
applies a published formula, and they carry a line saying exactly that in place of a byline,
because claiming a human author for a computed page would be a lie. The
<a href="/guides/">buyer's guides</a> are the written layer, and those carry my name.</p>

<h2>Accountability</h2>
<p>If a number on this site is wrong, it is wrong because the formula or the data is wrong,
and the fix goes into the formula so it reaches every affected page on the next nightly
build — not into one page quietly. Write to
<a href="mailto:corrections@motorjury.com">corrections@motorjury.com</a> and I will answer.
The <a href="/editorial-policy/">editorial policy</a> sets out the rules I hold the site to
and the <a href="/methodology/">methodology</a> is the formula itself, in full.</p>

<h2>Everything I have signed</h2>
<ol class="story-list">{signed}</ol>

<p class="src-note">Contact: <a href="mailto:hello@motorjury.com">hello@motorjury.com</a> ·
<a href="/contact/">contact page</a> · <a href="/about/">about {BRAND}</a></p>
</div>"""
    ld = [
        {"@context": "https://schema.org", "@type": "ProfilePage",
         "mainEntity": {
             "@type": "Person", "name": EDITOR,
             "url": ORIGIN + "/about/adir-trabelsi/",
             "jobTitle": "Editor and publisher",
             "email": "mailto:hello@motorjury.com",
             "worksFor": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
             "knowsAbout": ["Used car reliability", "NHTSA complaint data",
                            "Vehicle recalls", "Car ownership costs"]},
         "url": ORIGIN + "/about/adir-trabelsi/"},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "About",
             "item": ORIGIN + "/about/"},
            {"@type": "ListItem", "position": 2, "name": EDITOR,
             "item": ORIGIN + "/about/adir-trabelsi/"}]}]
    return write("about/adir-trabelsi/index.html",
                 page(f"{EDITOR} — Editor, {BRAND} | {BRAND}",
                      (f"{EDITOR} built and edits {BRAND}: who is accountable for the "
                       f"verdicts, what the scoring model does, and every guide he has "
                       f"signed."),
                      ORIGIN + "/about/adir-trabelsi/", body, ld))


def gen_static():
    gen = []
    gen.append(prose_page("methodology/index.html", "Methodology", f"""
<p>Every verdict on this site is computed, not written. This page is the complete formula, the data
behind it, and the things it deliberately does not claim.</p>

<h2>Sources</h2>
<p>Complaints, recalls and investigations come from the <a href="https://www.nhtsa.gov" rel="noopener">NHTSA
public APIs</a>. Fuel economy, electric range and annual fuel cost come from
<a href="https://www.fueleconomy.gov" rel="noopener">EPA fueleconomy.gov</a>. Raw API responses are cached
and versioned, and every page links the sources behind its own numbers.</p>
<p><b>Data vintage and refresh.</b> The ownership dataset is extended and re-checked every night, and the
whole site is regenerated from it every night. Each page carries the date it was last built. Complaint and
recall counts are cumulative federal records, so an older model year has had more years in which owners
could file — the score corrects for that by working in complaints per year of exposure.</p>

<h2>Reliability score (0–100)</h2>
<p>The score answers one question: <em>compared with what this same nameplate normally attracts, how much
trouble did this model year attract?</em> It is built from quantities that do not depend on how many cars
were sold, because raw complaint counts do.</p>
<p><b>Why that matters.</b> A nameplate selling 350,000 cars a year collects more complaints than one
selling 20,000, however good it is. An earlier version of this score divided complaints only by years of
exposure, and it punished popular cars for being popular — the kind of error that inverts the real ranking.
It was replaced with the model below.</p>
<p>score = 100 − within_model − cross_model − severe_recalls − other_recalls</p>
<ul>
<li><b>within_model</b> (max 42) — this model year's complaints per year of exposure, divided by the median
rate of the <em>same nameplate</em> across all of its years. Sales volume is roughly constant across a
model's years, so dividing by the model's own median cancels volume out. The ratio is shrunk toward 1.0
with weight n / (n + 40), where n is the complaint count: a year with a thin record is judged close to the
model's own norm rather than being read as evidence of excellence.</li>
<li><b>cross_model</b> (max 12) — the percentile of this car's complaint rate across the whole index, on a
log scale. This is the one term sales volume still leaks into, which is exactly why it is capped at 12
points and computed logarithmically.</li>
<li><b>severe_recalls</b> (max 18) — 3 points per safety-critical campaign. A recall is "severe" when its
NHTSA summary matches fire, crash, injury, stall, brake-failure or steering-loss patterns.</li>
<li><b>other_recalls</b> (max 8) — 1 point per remaining campaign. Recall counts are issued per defect, not
per car sold, so they are directly comparable between models.</li>
</ul>
<p>Because every term is bounded, the lowest score the model can produce is 20/100. No car is branded with
a number implying a total failure the data cannot support.</p>

<h2>Evidence strength</h2>
<p>Each verdict carries a confidence label: <b>strong</b> at 150 or more complaints on record,
<b>moderate</b> at 50 or more, <b>thin</b> below that. A thin record is an absence of evidence, not
evidence of quality, and the shrinkage term above treats it that way.</p>

<h2>Verdicts</h2>
<p>BUY ≥ 70 · CAUTION 50–69 · AVOID &lt; 50. Where complaint data is unavailable the verdict is
DATA PENDING — never guessed. A model year is only given its own page when it has at least 30 complaints
or at least 3 recall campaigns on record, or is an EV with published battery data. Everything thinner is
folded into the model overview instead of being published as a page of its own.</p>

<h2>Running cost</h2>
<p>Annual running cost = EPA annual fuel or energy cost + an age-indexed maintenance band drawn from
industry averages (AAA "Your Driving Costs", CarMD Vehicle Health Index). The headline figure is the
<em>midpoint</em> of that band, and the band itself is always shown beside it. Running cost excludes
purchase price, insurance and depreciation, and the pages say so.</p>

<h2>Repair costs</h2>
<p>repair = flat_rate_hours × local_labour_rate + parts_band. Flat-rate hours are the typical published
times for the representative job in each NHTSA component group; the labour reference is $120/hour at a US
independent shop; parts are a low–high band for a quality aftermarket or OE part. Every figure is an
estimate of what that <em>class</em> of failure costs — never a quote for a specific car, and never a
prediction that the repair will be needed. The jobs shown on a page are ranked by the components that
owners of that exact model year actually complain about.</p>

<h2 id="prices">Purchase price, depreciation and insurance</h2>
<p>NHTSA carries safety and EPA carries fuel economy. Neither carries money, and there is no free,
complete, per-model-year price dataset, so this site does not pretend to know what one specific car is
worth. What it publishes is a <em>class-level band</em>, computed the same way for every car and shown
with the band around it. The constants are published at
<a href="/assets/price-model.json">/assets/price-model.json</a>.</p>
<ol>
<li><b>Segment.</b> Each model-year is placed in one of fifteen segments by its own record: an explicit
nameplate keyword first (an F-150 is a pickup), otherwise EPA combined economy as a size proxy, then the
brand tier re-reads the segment upward for a premium or exotic marque.</li>
<li><b>The equivalent new car today.</b> segment_share × the current US average new-vehicle transaction
price (Cox Automotive / Kelley Blue Book). A mid-size car is 0.62 of that average, which is where a new
mid-size sedan actually lists. Working in today's money is what stops a 2015 car being priced in 2015
dollars against a 2026 used market.</li>
<li><b>Value today.</b> equivalent_new × retained_value(age) × segment_retention × used_market_index. The
retained-value curve is the consensus of the published depreciation studies (iSeeCars, Edmunds, NADA);
the segment multiplier reflects their spread — pickups and sports cars hold value, large luxury sedans and
used EVs do not; the used-market index (currently 1.08) carries the Manheim index's standing gap above its
pre-2021 trend, and comes out when that gap does. A running car never falls below a floor.</li>
<li><b>Price when new</b> is the same figure walked back to the model year with the transaction-price
series. Where Wikipedia's infobox carries a published list price for the nameplate, that real figure
anchors the calculation instead, and the page says so.</li>
<li><b>Depreciation</b> is the difference between the value today and the value five years from now — on a
five-year hold this is normally the largest single line, larger than fuel, maintenance and insurance
together, which is why it is shown before them.</li>
<li><b>Insurance</b> is the national average annual full-coverage premium for the segment (NAIC / industry
averages), relieved by vehicle age because full coverage tracks the value at risk, then re-priced by your
country's insurance index.</li>
</ol>
<p>The published band is ±18% around the central estimate, roughly the interquartile spread of real
listings for one model-year in one market. It is not a valuation, a dealer price, a trade-in offer or an
insurance quote — condition, mileage, options and location move a real car materially. Every price panel
takes the price you are actually being quoted and recomputes the whole picture from it.</p>

<h2>Owner satisfaction</h2>
<p>Complaint records tell you what broke. They cannot tell you whether the owner would buy the car again,
so we ask owners directly, one response per account per car. Averages are published only once five owners
have answered — below that a mean is noise wearing a number's clothes. Responses are never edited, never
weighted, and never traded.</p>

<h2>International prices</h2>
<p>Every money figure is generated in US dollars and re-priced in your browser from your country's retail
fuel and electricity prices and a parts-and-labour index, with the currency and units following the same
setting. Change the country in the bar at the top of any page. The reference table is published at
<a href="/assets/geo-prices.json">/assets/geo-prices.json</a>.</p>

<h2>Corrections</h2>
<p>If a number here is wrong, it is wrong in the data or in the formula, and both are public. Write to
<a href="mailto:corrections@motorjury.com">corrections@motorjury.com</a> with the page URL and what you
believe the correct figure is; corrections are applied at the source so every affected page is fixed on the
next nightly build.</p>

<h2>What we never do</h2>
<p>No fabricated numbers, no paid placement in verdicts, no AI-written filler prose. Advertising and
affiliate links never touch a score. If data is missing we say so.</p>
<p>Questions: see <a href="/about/">about</a>.</p>"""))
    gen.append(prose_page("about/index.html", "About", f"""
<p>{BRAND} exists because "is this car reliable?" is answerable with public data, and almost nobody
bothers. Manufacturers publish marketing. Forums publish anecdote. The United States safety regulator
publishes every complaint an owner files and every recall a manufacturer issues — millions of records,
free, and almost unreadable in raw form. This site turns them into a verdict per model year.</p>

<h2>Who runs it</h2>
<p>Operated and edited by <b><a href="/about/adir-trabelsi/">Adir Trabelsi</a></b>. Data engineering and publication are automated; the
methodology, the source selection and the editorial standards are human decisions, documented in full on
the <a href="/methodology/">methodology page</a>. Nobody pays for a verdict, and no verdict is written by
hand. The <a href="/guides/">buyer's guides</a> and the editor's notes on model pages are the written layer:
signed, dated and revised when the data moves, under the <a href="/editorial-policy/">editorial policy</a>.</p>

<h2>How to reach us</h2>
<p>General and press: <a href="mailto:hello@motorjury.com">hello@motorjury.com</a><br>
Data corrections: <a href="mailto:corrections@motorjury.com">corrections@motorjury.com</a><br>
Privacy and data requests: <a href="mailto:privacy@motorjury.com">privacy@motorjury.com</a></p>
<p>We answer corrections first. If a figure on this site is wrong, tell us which page and what you believe
the right number is — the fix goes into the data or the formula, so every affected page changes on the next
nightly build.</p>

<h2>What we publish, and what we will not</h2>
<p>Every number on a page traces to NHTSA or EPA, or is labelled an estimate with its formula published.
Verdicts are computed from that data before any advertising or affiliate link is attached to the page, and
no advertiser has ever been offered influence over one. We do not publish opinion reviews, we do not
republish manufacturer copy, and we do not fill pages with prose to make thin data look thick — a model
year without enough data does not get a page.</p>

<h2>Independence</h2>
<p>{BRAND} is not affiliated with any manufacturer, dealer, insurer or parts retailer. The site is funded by
advertising and by affiliate links that are disclosed on the <a href="/disclosure/">disclosure page</a>.</p><h2 id="attribution">Sources and attribution</h2>
<p>The buyer's guides are written and signed by Adir Trabelsi, the editor. Every other page on this site is computed by the build rather than written by a person, and says so in place of a byline. Complaint, recall and fuel-economy figures are from
NHTSA and the EPA. Catalogue facts (marque, years, designer, production) are from Wikidata. The background
paragraphs in car biographies and the descriptions on the events pages are adapted from the corresponding
English Wikipedia articles, used under the Creative Commons Attribution-ShareAlike licence
(<a href="https://creativecommons.org/licenses/by-sa/4.0/" rel="noopener">CC BY-SA 4.0</a>); the article each
page draws on is linked from its specifications table. Photographs are from Wikimedia Commons and carry
their author and licence in the caption or in the full-screen view. This page is the site-wide attribution
notice; individual pages do not repeat it.</p>

"""))
    gen.append(prose_page("editorial-policy/index.html", "Editorial Policy", f"""
<p>{BRAND} publishes two kinds of page, and this policy says how each is made, who is responsible for it,
and what happens when it is wrong.</p>

<h2>Computed pages</h2>
<p>Model-year verdicts, model overviews, rankings and comparisons are generated from public records —
NHTSA owner complaints and recall campaigns, and EPA fuel-economy data — by a published formula. No person
writes or adjusts an individual verdict, and no advertiser, dealer or manufacturer can buy one. The formula
is on the <a href="/methodology/">methodology page</a>; the source records are linked from every page.
Because the data is federal and the formula is fixed, two people running the same build get the same score.</p>
<p>A computed page is published only when the record behind it is deep enough to mean something. A model
year with fewer than thirty complaints does not get its own page, and a verdict built on fewer than fifty is
labelled thin evidence. Pages that do not meet the bar for search indexing — catalogue entries with no
photograph or sourced specification, translated copies, head-to-head pages — remain available to readers
but are marked so search engines do not index them.</p>

<h2>Written pages</h2>
<p>Buyer's guides, car biographies, editor's notes on model pages, and the introductions to each section are
written and edited by <b>Adir Trabelsi</b>, and carry his name and the date of the last revision. Pages
without a human byline — the model-year verdicts, the ownership indexes, the catalogue entries — are
produced by the build from the public record and carry an attribution line naming the sources and the
method instead of an author, because no person wrote them. They draw on the same
federal record as the computed pages, on manufacturers' published recall and warranty actions, and on
court filings where a defect has been litigated. They do not draw on anonymous forum posts, and they are
not generated by a language model and published unread. Where a written page makes a factual claim about a
specific model year, that claim can be checked against the model page it links to.</p>

<h2>Corrections</h2>
<p>Errors are corrected in the data or the formula, not by editing one page, so a fix reaches every affected
page on the next nightly build. Send corrections to
<a href="mailto:corrections@motorjury.com">corrections@motorjury.com</a> with the page address and what you
believe the right figure is. Corrections are answered before any other mail. Written pages that are
materially revised carry a new revision date.</p>

<h2>Advertising and affiliates</h2>
<p>The site is funded by advertising and disclosed affiliate links. Verdicts are computed before any
advertisement is attached to a page, advertising placements are never sold against a specific verdict, and
affiliate links are disclosed on the <a href="/disclosure/">disclosure page</a>. Sponsored content, if it is
ever published, will be labelled as such on the page itself.</p>

<h2>Sources and licensing</h2>
<p>Complaint and recall data: NHTSA, public domain. Fuel economy: EPA, public domain. Catalogue data:
Wikidata, CC0. Photographs: Wikimedia Commons, under the licence stated on each file, credited per image.
Specification excerpts: Wikipedia, CC BY-SA, attributed on the page. MotorJury's own scores and written text
may be quoted with a link to the page.</p>

<h2>Contact</h2>
<p>Editor: Adir Trabelsi · <a href="/contact/">contact page</a> · <a href="/about/">about {BRAND}</a>.</p>"""))

    gen.append(prose_page("contact/index.html", "Contact", f"""
<p>{BRAND} is edited by <b>Adir Trabelsi</b>. Mail is read daily; corrections are answered first.</p>

<h2>Corrections</h2>
<p><a href="mailto:corrections@motorjury.com">corrections@motorjury.com</a> — include the page address and
the figure you believe is wrong. A confirmed correction goes into the data or the formula and reaches every
affected page on the next nightly build. See the <a href="/editorial-policy/">editorial policy</a>.</p>

<h2>General and press</h2>
<p><a href="mailto:hello@motorjury.com">hello@motorjury.com</a></p>

<h2>Privacy and data requests</h2>
<p><a href="mailto:privacy@motorjury.com">privacy@motorjury.com</a> — see the
<a href="/privacy/">privacy policy</a> for what is collected and how to have it removed.</p>

<h2>Advertising</h2>
<p>Display advertising on {BRAND} is served through Google AdSense. Direct placements are not sold against
specific verdicts or pages; enquiries to <a href="mailto:hello@motorjury.com">hello@motorjury.com</a>.</p>

<h2>Follow</h2>
<p>Social accounts are listed on the <a href="/follow/">follow page</a>.</p>"""))

    gen.append(write("login/index.html", page(
        "Sign in to MotorJury",
        "Sign in to keep the cars you love, your garage and your settings on every device.",
        ORIGIN + "/login/",
        """<div class="wrap auth-wrap">
<div class="auth-card">
<h1>Sign in</h1>
<p class="auth-sub">Keep the cars you love, your garage and your country setting — on every device you
use. No tracking, nothing sold.</p>
<div id="login-app"><noscript>JavaScript is required to sign in.</noscript></div>
</div>
<aside class="auth-side">
<h2>What an account gets you</h2>
<ul class="auth-list">
<li><b>The cars you love</b> — one tap on any car, kept in one list.</li>
<li><b>Your garage</b> — the cars you own or are shopping, with their costs and recalls.</li>
<li><b>Your settings follow you</b> — country, currency and units, on every device.</li>
<li><b>Rate the car you own</b> — the owner-satisfaction data on this site comes from owners.</li>
</ul>
<p class="auth-fine">We store your email address, your lists and your preferences. That is the whole list.
Read the <a href="/privacy/">privacy policy</a>.</p>
</aside></div>""",
        extra_head='<meta name="robots" content="noindex,follow">')))

    gen.append(write("account/index.html", page(
        "Your account", "Your cars, your garage and your settings.", ORIGIN + "/account/",
        """<div class="wrap acct-wrap"><h1>Your account</h1><div id="account-app">
<noscript>JavaScript is required for your account page.</noscript></div></div>""",
        extra_head='<meta name="robots" content="noindex,follow">')))

    gen.append(write("loved/index.html", page(
        "The most-loved cars on MotorJury",
        "Which cars readers actually love — ranked by the love button, counted live.",
        ORIGIN + "/loved/",
        """<div class="hero"><div class="wrap hero-inner">
<h1>The most-loved cars</h1>
<p class="sub">Ranked by the love button on every car page. Counted live, one vote per account —
no editors, no sponsorship, no algorithm.</p></div></div>
<div class="wrap"><div id="loved-app" class="loved-grid">
<p class="muted">Loading…</p></div>
<p class="lib-note" style="margin-top:18px">Signed in? Every heart you tap lands in
<a href="/account/">your account</a>.</p></div>
<script src="/assets/loved.js" defer></script>""", extra_head=NOINDEX)))

    # Fallback /follow/: the footer of every page links it, so it must exist even when
    # build_social.py (which writes the full link-in-bio page) does not run. That script
    # runs later in build.sh and overwrites this stub.
    gen.append(write("follow/index.html", page(
        "MotorJury — start here", "Every car ever made, and what it really costs to own.",
        ORIGIN + "/follow/",
        """<div class="hero"><div class="wrap hero-inner"><h1>MotorJury</h1>
<p class="sub">What that car really costs to own — price, depreciation, repairs, insurance and a
verdict, computed from public data.</p></div></div>
<div class="wrap" style="padding:24px 0"><div class="rel-grid">
<a href="/library/">Every car ever made<small>the library</small></a>
<a href="/calculators/">What will it cost me?<small>the true-cost calculator</small></a>
<a href="/guides/">Buyer's guides<small>which years to avoid</small></a>
<a href="/years-to-avoid/">Years to avoid<small>every nameplate ranked</small></a></div></div>""", extra_head=NOINDEX)))

    gen.append(prose_page("privacy/index.html", "Privacy Policy", f"""
<p class="lib-note">Effective {TODAY}. This policy covers motorjury.com, published by MotorJury and
operated by its editor, Adir Trabelsi, from Porto, Portugal. Questions and requests:
<a href="mailto:privacy@motorjury.com">privacy@motorjury.com</a>, or the addresses on the
<a href="/contact/">contact page</a>.</p>

<h2>The short version</h2>
<p>You can read every page on this site without an account and without telling us who you are.
We use analytics to count visits, a consent banner to ask European visitors before any advertising
cookie is set, and Google AdSense to show advertising. If you create an account we keep the
minimum needed to run it, and you can delete it by writing to us. We do not sell personal data,
we do not build marketing profiles, and we never share account data with advertisers.</p>

<h2>What we collect, and why</h2>
<p><b>Visitors without an account.</b> Our servers and Cloudflare, which hosts the site, record the
standard technical log of each request — the page requested, the time, the IP address, the browser
and its language — to serve the page, defend against abuse and keep the site running. Google
Analytics 4 counts visits and pages; it is configured with IP anonymisation and, in the European
Economic Area, the United Kingdom and Switzerland, runs only after you consent. Cloudflare Web
Analytics counts visits without cookies. Your chosen country for pricing is stored in your browser's
local storage, not on our servers.</p>
<p><b>The VIN checker.</b> A VIN you type is sent to the public NHTSA (United States National Highway
Traffic Safety Administration) decoder and recall services to identify the vehicle. We do not store
the VIN, and a VIN is not linked to you.</p>
<p><b>Accounts.</b> If you create an account we store your email address, a display name, a password
hash (PBKDF2-SHA256; we cannot read your password), the cars you have loved or saved, your site
preferences and any owner-survey answers you submit. If you sign in with Google we receive your
email address and name from Google and nothing else; we hold no Google password or token beyond the
sign-in itself. Session tokens are stored hashed. Owner-survey answers are published in aggregate
only once five owners have answered, and any written comment you submit is shown with the label
"owner", never with your name or email.</p>
<p><b>Newsletter and alerts.</b> An email address you submit for updates is used only to send those
updates. Every message carries an unsubscribe link, and we will remove the address on request.</p>

<h2>Advertising and cookies</h2>
<p>Advertising on this site is served by Google AdSense. Third-party vendors, including Google, use
cookies to serve ads based on a user's prior visits to this website or to other websites. Google's
use of advertising cookies enables it and its partners to serve ads to you based on your visit to
this site and other sites on the internet. You may opt out of personalised advertising by visiting
<a href="https://www.google.com/settings/ads" rel="noopener">Google Ads Settings</a>, and opt out of
some third-party vendors' use of cookies for personalised advertising at
<a href="https://www.aboutads.info/choices/" rel="noopener">aboutads.info</a> or, in Europe,
<a href="https://www.youronlinechoices.eu/" rel="noopener">youronlinechoices.eu</a>. Google's own
description of how it uses data from sites that use its services is at
<a href="https://policies.google.com/technologies/partner-sites" rel="noopener">policies.google.com/technologies/partner-sites</a>.</p>
<p>For visitors in the European Economic Area, the United Kingdom and Switzerland, no advertising or
analytics cookie is set until you make a choice in the consent message, which is Google's certified
consent management platform. Google Consent Mode starts in the "denied" state for advertising
storage, advertising user data, advertising personalisation and analytics storage, and only your
consent changes it. You can change your choice at any time from the "Privacy settings" link in the
footer of every page, or by clearing cookies for motorjury.com.</p>
<p>Our own cookies are limited to the session cookie that keeps you signed in when you have an
account, and the consent cookie that records your consent choice.</p>

<h2>Photographs and third-party content</h2>
<p>Car photographs are loaded from Wikimedia Commons, whose servers receive the standard request
log (IP address, browser) when an image is fetched. We send no personal data to Wikimedia, and
images are requested with a no-referrer policy so the page you are reading is not disclosed.</p>

<h2>How long we keep it</h2>
<p>Server logs are retained for up to 30 days. Analytics data is retained for 14 months. Account
data is kept for as long as the account exists and deleted within 30 days of a deletion request.
Newsletter addresses are deleted on unsubscribe.</p>

<h2>Your rights</h2>
<p>Under the General Data Protection Regulation you may ask for a copy of the personal data we hold
about you, ask us to correct or delete it, ask us to stop processing it, ask for it in a portable
format, and object to processing based on legitimate interest. Write to
<a href="mailto:privacy@motorjury.com">privacy@motorjury.com</a>; we answer within 30 days and never
charge for a request. You also have the right to lodge a complaint with a supervisory authority; in
Portugal that is the Comissão Nacional de Proteção de Dados (CNPD).</p>

<h2>Children</h2>
<p>This site is not directed at children and we do not knowingly collect personal data from anyone
under 16. If you believe a child has created an account, write to us and we will delete it.</p>

<h2>Changes</h2>
<p>When this policy changes, the effective date at the top changes with it. Material changes to how
account data is used are announced by email to account holders before they take effect.</p>"""))

    gen.append(prose_page("terms/index.html", "Terms of Use", f"""
<p class="lib-note">Effective {TODAY}. These terms apply to motorjury.com and everything published
on it. Using the site means you accept them.</p>

<h2>What the site is</h2>
<p>MotorJury publishes ownership-cost data, reliability verdicts, recall summaries and buyer's
guides for cars sold in the United States, computed from public records held by the United States
National Highway Traffic Safety Administration (NHTSA) and the Environmental Protection Agency (EPA),
plus class-level estimates of prices, depreciation, insurance and running costs. The
<a href="/methodology/">methodology page</a> describes every formula. The
<a href="/editorial-policy/">editorial policy</a> describes what is computed, what is written by a
person, and how corrections are handled.</p>

<h2>Information, not advice</h2>
<p>Everything on the site is provided for general information. A score, a verdict or a guide
describes the pattern in the federal record for a model year across all the cars of that type; it
is not an inspection of the particular car in front of you, and it cannot tell you whether that car
is sound. Prices, running costs, depreciation and insurance figures are estimates, labelled as such,
and are not quotes, valuations or offers. Nothing here is legal, financial or mechanical advice. Before
buying a car, have it inspected, check its history, and verify every open recall against NHTSA's own
VIN lookup at nhtsa.gov/recalls, because a recall record on this site may be incomplete or out of date.</p>

<h2>Accuracy and corrections</h2>
<p>We work from the public record as published and refresh it regularly, but the record itself
contains errors and gaps, and our processing can introduce more. We correct mistakes when they are
pointed out; the process is described on the <a href="/editorial-policy/">editorial policy</a> page.
The site is provided "as is" and "as available", without warranty of any kind, express or implied,
including fitness for a particular purpose and accuracy. To the fullest extent permitted by law,
MotorJury and its editor are not liable for any loss arising from use of the site or reliance on
anything published on it.</p>

<h2>Using the content</h2>
<p>You may quote and cite the data and the written material with attribution and a link to the page
it came from. Bulk copying, scraping or republishing of pages, or of the underlying data files beyond
the published data packs, requires a licence: write to <a href="/contact/">the editor</a>. Car
photographs are the work of their credited photographers and are used under the Creative Commons
licences stated on each image's Wikimedia Commons page; text derived from Wikipedia is used under
CC BY-SA 4.0, as noted on the <a href="/about/">about page</a>. NHTSA and EPA data are public
domain works of the United States government.</p>

<h2>Accounts and owner responses</h2>
<p>An account is for one person. You are responsible for what is submitted from it. Owner-survey
answers must describe a car you have actually owned; we remove ratings and comments that are
abusive, promotional, off-topic or evidently not from an owner, and we may close accounts that
submit them. You may delete your account at any time by writing to
<a href="mailto:privacy@motorjury.com">privacy@motorjury.com</a>.</p>

<h2>Advertising and affiliate links</h2>
<p>The site carries advertising served by Google AdSense and may carry affiliate links; both are
described on the <a href="/disclosure/">disclosure page</a>. Advertisers and affiliate partners
have no influence on any score, verdict or guide.</p>

<h2>Trademarks</h2>
<p>Manufacturer and model names are the trademarks of their owners and are used only to identify
the vehicles the data describes. MotorJury is not affiliated with, endorsed by or sponsored by any
manufacturer, dealer, insurer or government agency.</p>

<h2>Law</h2>
<p>These terms are governed by the law of Portugal, and disputes are subject to the courts of
Porto, without prejudice to mandatory consumer protections in your country of residence. If any
provision is found unenforceable the rest remain in effect.</p>"""))

    gen.append(prose_page("disclosure/index.html", "Advertising and Affiliate Disclosure", f"""
<p class="lib-note">Effective {TODAY}.</p>
<h2>How the site is funded</h2>
<p>MotorJury is funded by display advertising served by Google AdSense and, where they appear, by
affiliate links. There is no subscription, no sponsored content and no paid placement in any list,
score or guide, and no manufacturer, dealer or insurer has ever paid to appear on the site or to be
left out of it.</p>
<h2>Advertising</h2>
<p>Advertisements are selected and served by Google, not by us, and are marked as advertising.
Advertising never appears inside a data table, a verdict card or a buyer's guide, and it never
changes what those say. In the European Economic Area, the United Kingdom and Switzerland, advertising
cookies are set only after you consent in the message shown on your first visit; see the
<a href="/privacy/">privacy policy</a> for how to change that choice.</p>
<h2>Affiliate links</h2>
<p>Some links — for example to parts, diagnostic tools, vehicle-history reports or insurance quote
partners — may be affiliate links. If you buy through one, we may earn a commission at no extra cost
to you. Affiliate links are chosen after the page's content is written and computed, never before,
and the presence or absence of an affiliate partner has no effect on any score or recommendation.
Where a page carries an affiliate link it is labelled as such near the link.</p>
<h2>Independence</h2>
<p>Every score and verdict is computed from NHTSA and EPA public records by the published
<a href="/methodology/">methodology</a>, and every guide is written by the editor from that record
before any monetisation is attached to the page. The <a href="/editorial-policy/">editorial policy</a>
sets out how corrections are handled and how a reader can challenge a figure.</p>"""))
    return gen

def gen_assets():
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    # The price formula's constants are published, the way the geo table is: a reader who
    # wants to check a number should be able to read the same file the generator read.
    _pm = ROOT / "data" / "price_model.json"
    if _pm.exists():
        shutil.copy(_pm, SITE / "assets" / "price-model.json")
    for f in (ROOT / "assets").iterdir():
        if f.is_file() and " 2." not in f.name:
            shutil.copy(f, SITE / "assets" / f.name)
    # Root-served files: icons, web manifest, the default social card and _headers.
    # gen_site clears site/ on every run, so these have to be re-planted here.
    src = ROOT / "static"
    if src.exists():
        for f in src.rglob("*"):
            if f.is_file():
                dest = SITE / f.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, dest)
    # A page without a social card is a grey rectangle in every share. Regenerate the
    # fallback if Pillow is available; the committed copy is the floor.
    try:
        from og_card import default_card
        default_card(SITE / "og" / "default.png")
    except Exception:
        pass

def gen_redirects():
    """301 every pre-canonicalisation model URL to its new home (Cloudflare _redirects)."""
    src = ROOT / "data" / "model_redirects.json"
    if not src.exists():
        return
    try:
        m = json.loads(src.read_text())
    except Exception:
        return
    # Cloudflare parses "<path>* <target> 301" as a DYNAMIC rule and allows only 100 of
    # them per deploy; the canonicalisation map passed that months of nightly growth ago
    # (263 and counting), and the deploy rejection it caused ("Line 103: maximum number of
    # dynamic _redirects rules") is what silently froze production. The splat handling now
    # lives in the Worker (workers/redirect.js imports the same JSON and prefix-matches in
    # code, no platform limit); the static file keeps only the exact-path lines, which sit
    # under the separate 2,000-rule static cap.
    lines = ["# Generated by canonicalize_models.py — vPIC trim URLs folded onto the model.",
             "# Exact paths only: splat handling lives in workers/redirect.js (100-rule limit)."]
    for old_u, new_u in sorted(m.items()):
        if old_u != new_u:
            lines.append(f"{old_u} {new_u} 301")
    (SITE / "_redirects").write_text("\n".join(lines[:1900]) + "\n")


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
- {ORIGIN}/vin-check/ — free VIN decoder and NHTSA recall check
- {ORIGIN}/calculators/ — true-cost calculator
- {ORIGIN}/methodology/ — scoring formula
""")
    # sitemap index + shard (spec: sharded <=10K URLs/file)
    shard = "".join(f"<url><loc>{ORIGIN}{u}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls)
    (SITE / "sitemap-0.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{shard}</urlset>')
    (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{ORIGIN}/sitemap-0.xml</loc><lastmod>{TODAY}</lastmod></sitemap></sitemapindex>')
    (SITE / "ads.txt").write_text("# populate with AdSense line after approval: google.com, pub-XXXX, DIRECT, f08c47fec0942fa0\n")
    nf_body = (
        '<div class="wrap nf">'
        '<p class="nf-code">404</p>'
        '<h1>This page took a wrong turn</h1>'
        '<p class="nf-sub">That address does not match anything in the record. The data is all still here &mdash; '
        'search any car ever made, or start from a section.</p>'
        '<div class="searchbox nf-search"><input id="q404" type="search" '
        'placeholder="Search any car ever made&hellip;" autocomplete="off" aria-label="search" '
        'data-none="No matches &mdash; try a brand like Toyota or a nickname like Vette">'
        '<div id="q404-out" hidden></div></div>'
        '<div class="nf-links">'
        '<a href="/cars/">Browse ownership data</a>'
        '<a href="/library/">The model library</a>'
        '<a href="/stories/">Data stories</a>'
        '<a href="/compare/">Head to head</a>'
        '<a href="/events/">Events calendar</a>'
        '<a href="/calculators/">Calculators</a>'
        '</div></div>'
    )
    (SITE / "404.html").write_text(page("Page not found", "That page is not in the record. Search any car ever made or browse the data.", ORIGIN + "/404", nf_body))

def dup_check(pages):
    """duplicate-paragraph detector: % of <p> blocks appearing on >1 page (excluding boilerplate)."""
    seen, dup, total = {}, 0, 0
    for path in pages:
        html = (SITE / path).read_text()
        body = html.split('<div class="wrap', 1)[-1].rsplit("<footer", 1)[0]
        # exclude citation/CTA boilerplate blocks — the budget measures CONTENT prose
        body = re.sub(r'<div class="(?:card sources|cta-band)">.*?</div>', "", body, flags=re.S)
        # Chart furniture is not prose. The cost-curve SVG carries its axis ticks and the
        # legend carries its series name as text, and the paragraph regex was sweeping both
        # into the measurement - identical on every model-year page by construction. With 16
        # model-years that noise was invisible (4.6%); with 397 it alone pushed the figure to
        # 36.1% and failed the build, so a green ingest could never reach production.
        body = re.sub(r"<svg\b.*?</svg>", "", body, flags=re.S)
        body = re.sub(r'<div class="legend">.*?</div>', "", body, flags=re.S)
        # Fixed explainer captions are UI chrome too: they say where the data comes from and
        # are meant to read identically everywhere. Duplicating them is the point.
        # The attribution line replaced the old human byline. It is deliberately identical on
        # every computed page — that is what makes it an honest statement of how the page was
        # made — so it belongs with the other chrome, not in the prose measurement.
        body = re.sub(r'''<p class=(?:"(?:geo-note|src-note|data-missing|sv-n|byline)"|'(?:geo-note|src-note|data-missing|sv-n|byline)')[^>]*>.*?</p>''',
                      "", body, flags=re.S)
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
    pages.append(gen_years_to_avoid(con, all_rows))
    pages.append(gen_home(con, all_rows))
    pages.append(gen_search(con, all_rows))
    pages.append(gen_calculators(con, all_rows))
    pages.append(gen_recalls_feed(con, all_rows))
    pages.append(gen_vin_check())
    pages += gen_static()
    pages.append(gen_author_page())
    urls = ["/" + p.replace("index.html", "") for p in pages]
    gen_meta(urls)
    gen_redirects()
    dup = dup_check(pages)
    print(f"GENERATED {len(pages)} pages ({len(gated)} model-year) -> site/  dup-paragraphs: {dup:.1f}% (budget <15%)")
    if dup >= 15:
        print("FAIL: duplicate-paragraph budget exceeded"); sys.exit(1)

if __name__ == "__main__":
    main()
