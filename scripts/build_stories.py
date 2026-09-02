#!/usr/bin/env python3
"""build_stories.py — data stories and head-to-head comparisons, straight from the database.

Two page families the ownership data has earned:

  /stories/<slug>/          rankings computed from the NHTSA/EPA dataset on every deploy -
                            most complained-about, most recalled, safest bets, EV reality.
                            The format journalists cite and forums argue about.
  /compare/<a>-vs-<b>/      head-to-head verdict pages for natural rivals, built for the
                            highest-intent search query family in cars: "X vs Y".

Both run after gen_site (which wipes site/) and only link to pages that exist in this
build, so the dead-link gate stays meaningful.
"""
import html, json, os, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DB = ROOT / "data" / "cars.sqlite"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")
BRAND = "MotorJury"

RIVALS = [
    ("Toyota", "Camry", "Honda", "Accord"),
    ("Toyota", "Corolla", "Honda", "Civic"),
    ("Toyota", "RAV4", "Honda", "CR-V"),
    ("Ford", "F-150", "Chevrolet", "Silverado"),
    ("Toyota", "Highlander", "Honda", "Pilot"),
    ("Tesla", "Model 3", "Toyota", "Camry"),
    ("Tesla", "Model Y", "Toyota", "RAV4"),
    ("Nissan", "Altima", "Toyota", "Camry"),
    ("Nissan", "Rogue", "Toyota", "RAV4"),
    ("Subaru", "Outback", "Toyota", "RAV4"),
    ("Hyundai", "Elantra", "Toyota", "Corolla"),
    ("Kia", "Telluride", "Toyota", "Highlander"),
    ("Jeep", "Grand Cherokee", "Toyota", "4Runner"),
    ("Ford", "Mustang", "Chevrolet", "Camaro"),
    ("Ford", "Escape", "Toyota", "RAV4"),
    ("Chevrolet", "Equinox", "Honda", "CR-V"),
    ("Hyundai", "Tucson", "Kia", "Sportage"),
    ("Tesla", "Model 3", "Nissan", "Leaf"),
    ("Ram", "1500", "Ford", "F-150"),
    ("Subaru", "Forester", "Honda", "CR-V"),
]


def esc(s):
    return html.escape(str(s), quote=True)


def slug(s):
    import re
    s = re.sub(r"[^\w\s-]", "", str(s).lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:60] or "x"


def _hubs():
    try:
        return json.load(open(ROOT / "data" / "editorial" / "hubs.json"))
    except Exception:
        return {}
HUB_NOTES = _hubs()
NOINDEX = '<meta name="robots" content="noindex,follow">'
BYLINE = ''


def shell(title, desc, canon, body, robots=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{robots}
<meta name="theme-color" content="#0B0D10"><title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/site.css"></head><body>
<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="/">Motor<em>Jury</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="Search any car ever made…" autocomplete="off" aria-label="search"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/guides/">Guides</a><a href="/cars/">Browse</a><a href="/library/">Library</a><a href="/events/">Events</a><a href="/play/">Play</a><a href="/calculators/">Calculators</a></nav>
</div></header>
{body}
<footer><div class="wrap"><p>Every number on this page is computed from NHTSA and EPA public
records on the day this site was last built. · <a href="/methodology/">Methodology</a> · <a href="/editorial-policy/">Editorial policy</a> · <a href="/about/">About</a> · <a href="/contact/">Contact</a> · <a href="/privacy/">Privacy</a></p></div></footer>
<script src="/assets/site.js" defer></script></body></html>"""


def load():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT mk.name make, mo.name model, mo.slug mslug, mk.slug kslug,
        my.year, my.complaint_count, my.recall_count, my.severe_recalls, my.is_ev,
        cs.reliability_score score, cs.verdict, cs.complaints_per_year cpy,
        f.mpg_comb, f.fuel_type
        FROM model_years my
        LEFT JOIN fuel f ON f.my_id = my.id
        JOIN models mo ON mo.id = my.model_id
        JOIN makes mk ON mk.id = mo.make_id
        LEFT JOIN computed_scores cs ON cs.my_id = my.id""").fetchall()
    con.close()
    return rows


def url(r):
    return f"/cars/{r['kslug']}/{r['mslug']}/{r['year']}/"


def exists(u):
    return (SITE / u.strip("/") / "index.html").exists()


def row_link(r, extra=""):
    return (f'<a href="{url(r)}">{r["year"]} {esc(r["make"])} {esc(r["model"])}'
            f'<small>{extra}</small></a>')


def story(slug_, title, desc, intro, ranked, value_of):
    items = "".join(
        f'<li>{row_link(r, value_of(r))}</li>' for r in ranked if exists(url(r)))
    if not items:
        return None
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>{esc(title)}</h1><p class="sub">{esc(intro)}</p></div></div>
<div class="wrap" style="padding:8px 16px 40px">
<ol class="story-list">{items}</ol>
<p class="lib-note">Computed from the federal complaint and recall record at build time -
this list updates itself as new data lands. Sources: NHTSA, EPA.</p>{BYLINE}
<h2 class="sec">Keep going</h2>
<div class="rel-grid"><a href="/stories/">All data stories<small>rankings from the record</small></a>
<a href="/compare/">Head to head<small>the classic rivalries, settled by data</small></a>
<a href="/cars/">Browse by brand<small>every marque A-Z</small></a></div></div>"""
    (SITE / "stories" / slug_).mkdir(parents=True, exist_ok=True)
    (SITE / "stories" / slug_ / "index.html").write_text(
        shell(f"{title} | {BRAND}", desc, f"{ORIGIN}/stories/{slug_}/", body))
    return (slug_, title, desc)


def build_stories(rows):
    scored = [r for r in rows if r["score"] is not None and (r["complaint_count"] or 0) > 0]
    made = []

    made.append(story("most-complained", "The Most Complained-About Cars in America",
        "The model years with the most owner complaints per year on the road, from the federal record.",
        "Complaints filed with the United States safety regulator, normalised per year on the road. "
        "Nobody files paperwork about a car that behaves.",
        sorted(scored, key=lambda r: -(r["cpy"] or 0))[:15],
        lambda r: f'{r["cpy"]:g} complaints per year on the road · score {r["score"]}/100'))

    made.append(story("most-recalled", "The Most Recalled Cars on the Road",
        "Model years ranked by recall campaigns, with safety-critical recalls flagged.",
        "Recall campaigns are the manufacturer admitting something in writing. "
        "These model years collected the most.",
        sorted(rows, key=lambda r: -(r["recall_count"] or 0))[:15],
        lambda r: f'{r["recall_count"]} campaigns, {r["severe_recalls"] or 0} touching fire, crash or stall risk'))

    made.append(story("safest-bets", "The Safest Bets: Highest-Scoring Used Cars",
        "The model years our data likes best - fewest complaints per year, cleanest recall records.",
        "The quiet ones. High scores here mean owners had little to report and manufacturers "
        "had little to admit.",
        sorted(scored, key=lambda r: -(r["score"] or 0))[:15],
        lambda r: f'score {r["score"]}/100 · {r["complaint_count"]:,} complaints total'))

    ev = [r for r in scored if r["is_ev"]]
    if ev:
        made.append(story("ev-reality-check", "The EV Reality Check",
            "Electric cars ranked by what owners actually reported - not by the brochure.",
            "Electric ownership through the complaint record: which EVs owners live with quietly, "
            "and which generate paperwork.",
            sorted(ev, key=lambda r: -(r["score"] or 0)),
            lambda r: f'score {r["score"]}/100 · {r["complaint_count"]:,} complaints on record'))

    made = [m for m in made if m]
    cards = "".join(f'<a href="/stories/{s}/">{esc(t)}<small>{esc(d[:90])}</small></a>'
                    for s, t, d in made)
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>Data stories</h1><p class="sub">Rankings nobody edits: computed from the federal complaint
and recall record every time this site is built.</p></div></div>
<div class="wrap" style="padding:8px 16px 40px"><div class="card prose editorial">{HUB_NOTES.get("stories", "")}</div><div class="rel-grid">{cards}</div></div>"""
    (SITE / "stories").mkdir(parents=True, exist_ok=True)
    (SITE / "stories" / "index.html").write_text(
        shell(f"Data Stories - Rankings from the Federal Record | {BRAND}",
              "Most complained-about, most recalled, safest bets and the EV reality check - "
              "computed from NHTSA and EPA records.", f"{ORIGIN}/stories/", body))
    return len(made)


def best_year(rows, make, model):
    cand = [r for r in rows if r["make"].lower() == make.lower()
            and r["model"].lower() == model.lower() and r["score"] is not None
            and exists(url(r))]
    return max(cand, key=lambda r: r["score"]) if cand else None


def side(r):
    return f"""<div class="cmp-side">
<h2><a href="{url(r)}">{r['year']} {esc(r['make'])} {esc(r['model'])}</a></h2>
<div class="cmp-score">{r['score']}<small>/100</small></div>
<span class="tag v-{r['verdict'] if r['verdict'] in ('BUY','CAUTION','AVOID') else 'DATA'}">{esc(r['verdict'])}</span>
<ul>
<li>{(r['complaint_count'] or 0):,} owner complaints on record</li>
<li>{r['cpy'] or 0:g} complaints per year on the road</li>
<li>{r['recall_count'] or 0} recall campaigns, {r['severe_recalls'] or 0} severe</li>
</ul></div>"""


MAX_COMPARES = int(os.environ.get("MAX_COMPARES", "600"))
MIN_COMPLAINTS = 60        # a nameplate nobody complains about is a nameplate nobody owns


def auto_rivals(rows):
    """Pair nameplates the way a buyer would shop them, from data we actually hold.

    "X vs Y" is the highest-intent query family in car search and the one Car and Driver
    built a franchise on. Twenty hand-written pairs cannot cover it; the pairing has to come
    out of the database. There is no segment column, so the proxy is combined fuel economy
    plus powertrain: a truck and a compact saloon are never within 15% of each other on MPG,
    while a Camry, an Accord and an Altima are within a point or two. Popularity is proxied
    by complaint volume - the federal record is thin for cars nobody bought.

    Hand-written RIVALS still run first and are never displaced; this only fills the rest of
    the page budget.
    """
    best = {}
    for r in rows:
        if r["score"] is None or not exists(url(r)):
            continue
        k = (r["make"], r["model"])
        if k not in best or (r["score"] or 0) > (best[k]["score"] or 0):
            best[k] = r
    pool = [r for r in best.values()
            if (r["complaint_count"] or 0) >= MIN_COMPLAINTS and (r["mpg_comb"] or 0) > 0]
    pool.sort(key=lambda r: -(r["complaint_count"] or 0))
    pairs = []
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if a["make"] == b["make"] and a["model"] == b["model"]:
                continue
            if bool(a["is_ev"]) != bool(b["is_ev"]):
                continue
            lo, hi = sorted((a["mpg_comb"], b["mpg_comb"]))
            if hi > lo * 1.15:                      # different kind of car; not a shopping pair
                continue
            pairs.append((a["make"], a["model"], b["make"], b["model"]))
    return pairs


def build_compares(rows):
    made = []
    seen_pairs = {tuple(sorted((f"{a} {b}".lower(), f"{c} {d}".lower())))
                  for a, b, c, d in RIVALS}
    auto = [q for q in auto_rivals(rows)
            if tuple(sorted((f"{q[0]} {q[1]}".lower(), f"{q[2]} {q[3]}".lower()))) not in seen_pairs]
    budget = max(0, MAX_COMPARES - len(RIVALS))
    if len(auto) > budget:
        print(f"COMPARES: {len(auto)} data-matched pairs available, publishing {budget} "
              f"(MAX_COMPARES={MAX_COMPARES}); {len(auto) - budget} held back")
        auto = auto[:budget]
    for mk1, mo1, mk2, mo2 in list(RIVALS) + auto:
        a, b = best_year(rows, mk1, mo1), best_year(rows, mk2, mo2)
        if not a or not b:
            continue
        win = a if (a["score"] or 0) >= (b["score"] or 0) else b
        s = f"{slug(mk1 + '-' + mo1)}-vs-{slug(mk2 + '-' + mo2)}"
        title = f"{mk1} {mo1} vs {mk2} {mo2}: What the Data Says"
        verdict_line = (f"On the federal record, the {win['year']} {win['make']} {win['model']} "
                        f"takes it: {win['score']}/100 against "
                        f"{(a if win is b else b)['score']}/100.")
        body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>{esc(mk1)} {esc(mo1)} <em>vs</em> {esc(mk2)} {esc(mo2)}</h1>
<p class="sub">{esc(verdict_line)} Best-scoring model year of each, judged only on complaints
and recalls filed with the United States safety regulator.</p></div></div>
<div class="wrap" style="padding:8px 16px 40px">
<div class="cmp-grid">{side(a)}{side(b)}</div>
<p class="lib-note">Scores compare the best data-year of each nameplate. Click through for
every model year, owner narratives and running costs.</p>
<h2 class="sec">More head-to-heads</h2><div class="rel-grid" id="more-cmp"></div></div>"""
        (SITE / "compare" / s).mkdir(parents=True, exist_ok=True)
        (SITE / "compare" / s / "index.html").write_text(
            shell(robots=NOINDEX, title=title + f" | {BRAND}", desc=
                  f"{mk1} {mo1} or {mk2} {mo2}? Complaint and recall records compared, "
                  f"with a data verdict.", canon=f"{ORIGIN}/compare/{s}/", body=body))
        made.append((s, f"{mk1} {mo1} vs {mk2} {mo2}",
                     f"{win['make']} {win['model']} wins on data, {win['score']}/100"))

    # Cross-link the head-to-heads, but bounded. Pasting every comparison into every
    # comparison was fine at twenty pages and is a footer-link farm at six hundred: it
    # bloats each page and spreads internal PageRank evenly over pages that should not
    # rank evenly. Each page links the twelve that follow it, wrapping around, so the
    # lattice stays fully connected at twelve links a page instead of N.
    def anchor(x):
        sl, ti, wi = x
        return f'<a href="/compare/{sl}/">{esc(ti)}<small>{esc(wi)}</small></a>'

    NEIGHBOURS = 12
    for i, (sl, _, _) in enumerate(made):
        near = [made[(i + k) % len(made)] for k in range(1, min(NEIGHBOURS, len(made)))]
        f = SITE / "compare" / sl / "index.html"
        f.write_text(f.read_text().replace(
            '<div class="rel-grid" id="more-cmp"></div>',
            '<div class="rel-grid">' + "".join(anchor(x) for x in near) + '</div>'))
    links = "".join(anchor(x) for x in made)
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>Head to head</h1><p class="sub">The classic rivalries, settled by the federal complaint
record instead of a comments section.</p></div></div>
<div class="wrap" style="padding:8px 16px 40px"><div class="card prose editorial">{HUB_NOTES.get("compare", "")}</div><div class="rel-grid">{links}</div></div>"""
    (SITE / "compare").mkdir(parents=True, exist_ok=True)
    (SITE / "compare" / "index.html").write_text(
        shell(f"Car Comparisons - Rivalries Settled by Data | {BRAND}",
              "Camry vs Accord, F-150 vs Silverado and more - complaint and recall records "
              "compared head to head.", f"{ORIGIN}/compare/", body))
    return len(made)


def main():
    if not DB.exists() or not (SITE / "index.html").exists():
        print("STORIES SKIPPED: no database or site yet")
        return 0
    rows = load()
    ns = build_stories(rows)
    nc = build_compares(rows)

    # surface both on the home page Explore grid
    home = SITE / "index.html"
    h = home.read_text()
    hook = '<div class="rel-grid"><a href="/events/">'
    if hook in h and "/stories/" not in h:
        h = h.replace(hook,
            '<div class="rel-grid">'
            '<a href="/stories/">Data stories<small>most complained · most recalled · safest bets</small></a>'
            '<a href="/compare/">Head to head<small>Camry vs Accord, settled by data</small></a>'
            '<a href="/events/">', 1)
        home.write_text(h)
    print(f"STORIES OK: {ns} stories, {nc} comparisons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
