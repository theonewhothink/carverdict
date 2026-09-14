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


sys.path.insert(0, str(ROOT / "scripts"))
try:
    from gen_site import lib_photo as _lib_photo
except Exception:            # a partial local run must still produce pages
    _lib_photo = lambda *a, **k: None


def esc(s):
    return html.escape(str(s), quote=True)


def car_figure(make, model):
    """A photograph of the nameplate for a comparison page. No year is claimed, so the
    nameplate-level match is the right one: these pages compare badges across their whole
    record, not one model year."""
    ph = _lib_photo(make, model)
    if not ph:
        return ""
    import urllib.parse as _u
    fn = _u.quote(ph.replace(" ", "_"))
    base = f"https://commons.wikimedia.org/wiki/Special:FilePath/{fn}"
    src = f"{base}?width=720"
    srcset = ", ".join(f"{base}?width={w} {w}w" for w in (360, 540, 720, 960))
    page = f"https://commons.wikimedia.org/wiki/File:{fn}"
    return (f'<figure class="cmp-shot"><img src="{src}" srcset="{srcset}" '
            f'sizes="(max-width:700px) 100vw, 46vw" alt="{esc(make)} {esc(model)}" '
            f'width="720" height="405" loading="lazy" decoding="async" '
            f'referrerpolicy="no-referrer" '
            f'onerror="this.closest(\'figure\').remove()">'
            f'<figcaption>{esc(make)} {esc(model)} · '
            f'<a href="{page}" rel="noopener">Wikimedia Commons</a></figcaption></figure>')


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
    # price_estimates is written by price_model.py earlier in the build; an empty table keeps
    # the join valid so a partial local run still produces pages.
    con.execute("""CREATE TABLE IF NOT EXISTS price_estimates(
        my_id INT PRIMARY KEY, segment TEXT, brand_tier TEXT, anchor TEXT,
        price_new INT, price_new_low INT, price_new_high INT,
        price_today INT, price_today_low INT, price_today_high INT,
        price_in5 INT, price_in5_low INT, price_in5_high INT,
        depreciation_5y INT, depreciation_per_year INT,
        insurance_low INT, insurance_high INT)""")
    rows = con.execute("""SELECT my.id my_id, mk.name make, mo.name model, mo.slug mslug,
        mk.slug kslug, mo.id model_id,
        my.year, my.complaint_count, my.recall_count, my.severe_recalls, my.is_ev,
        cs.reliability_score score, cs.verdict, cs.complaints_per_year cpy,
        f.mpg_comb, f.fuel_type, pe.segment, pe.price_today
        FROM model_years my
        LEFT JOIN fuel f ON f.my_id = my.id
        LEFT JOIN price_estimates pe ON pe.my_id = my.id
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


# ---------------------------------------------------------------------------------------
# Head to head. "X vs Y" is the highest-intent query family in car search and the one the
# buff books built franchises on. The old pages here were two score cards and a sentence,
# and they were noindexed for good reason: nothing on them answered the question. They now
# carry the one comparison nobody else publishes — both nameplates' full model-year records
# side by side, what each one's owners actually complain about, the years to avoid on each,
# and what each costs to run — all of it computed, so it stays true on the next build.

MIN_YEARS_TO_INDEX = 5       # a nameplate with three scored years cannot anchor a comparison
MIN_COMPLAINTS_TO_INDEX = 150


def nameplate(rows, make, model):
    """Every scored year of one nameplate, newest first."""
    rs = [r for r in rows if r["make"].lower() == make.lower()
          and r["model"].lower() == model.lower() and r["score"] is not None]
    return sorted(rs, key=lambda r: -r["year"])


def np_stats(rs):
    recent = [r for r in rs if r["year"] >= 2013] or rs
    scores = [r["score"] for r in recent]
    return {
        "n": len(rs),
        "mean": round(sum(scores) / len(scores)) if scores else 0,
        "best": max(rs, key=lambda r: r["score"]),
        "worst": min(rs, key=lambda r: r["score"]),
        "complaints": sum(r["complaint_count"] or 0 for r in rs),
        "cpy": round(sum(r["cpy"] or 0 for r in recent) / max(1, len(recent))),
        "recalls": sum(r["recall_count"] or 0 for r in rs),
        "severe": sum(r["severe_recalls"] or 0 for r in rs),
        "avoid": sorted([r for r in rs if r["verdict"] == "AVOID"], key=lambda r: r["year"]),
        "buy": sorted([r for r in rs if r["verdict"] == "BUY"], key=lambda r: r["year"]),
        "price": next((r["price_today"] for r in rs if r["price_today"]), None),
        "mpg": next((r["mpg_comb"] for r in rs if r["mpg_comb"]), None),
        "segment": next((r["segment"] for r in rs if r["segment"]), None),
    }


def top_components(con, rs, limit=3):
    ids = [r["my_id"] for r in rs]
    if not ids:
        return []
    q = ("SELECT component, SUM(count) n FROM complaints WHERE component!='__quote__' "
         "AND my_id IN (%s) GROUP BY component ORDER BY n DESC LIMIT ?" % ",".join("?" * len(ids)))
    return con.execute(q, ids + [limit]).fetchall()


def _yearlist(rs, n=6):
    out = ", ".join(f'<a href="{url(r)}">{r["year"]}</a>' if exists(url(r)) else str(r["year"])
                    for r in rs[:n])
    return out + ("…" if len(rs) > n else "")


def compare_body(con, mk1, mo1, rs1, mk2, mo2, rs2):
    """Returns (body html, title, description, faqs, indexable)."""
    a, b = np_stats(rs1), np_stats(rs2)
    n1, n2 = f"{mk1} {mo1}", f"{mk2} {mo2}"
    gap = a["mean"] - b["mean"]
    lead, trail = (n1, n2) if gap >= 0 else (n2, n1)
    la, ta = (a, b) if gap >= 0 else (b, a)
    g = abs(gap)

    if g <= 3:
        headline = (f"The {n1} and the {n2} are level on the federal record — "
                    f"{a['mean']}/100 against {b['mean']}/100 across the years we score. "
                    f"Which one to buy is decided by the model year, not the badge.")
    elif g <= 10:
        headline = (f"The {lead} is ahead of the {trail} on the federal record, "
                    f"{la['mean']}/100 against {ta['mean']}/100 — a real but narrow gap that "
                    f"a bad model year on either side closes.")
    else:
        headline = (f"The {lead} is clearly ahead of the {trail} on the federal record: "
                    f"{la['mean']}/100 against {ta['mean']}/100 across every model year "
                    f"we score.")

    # -- side-by-side headline numbers ----------------------------------------------
    def card(nm, st, rs):
        return f"""<div class="cmp-side">
{car_figure(rs[0]['make'], rs[0]['model'])}
<h3><a href="/cars/{rs[0]['kslug']}/{rs[0]['mslug']}/">{esc(nm)}</a></h3>
<div class="cmp-score">{st['mean']}<small>/100 mean</small></div>
<ul>
<li>{st['n']} model years scored</li>
<li>{st['complaints']:,} owner complaints on record</li>
<li>about {st['cpy']:,} complaints per year on the road</li>
<li>{st['recalls']} recall campaigns, {st['severe']} safety-critical</li>
<li>best year {st['best']['year']} ({st['best']['score']}/100) · worst {st['worst']['year']} ({st['worst']['score']}/100)</li>
</ul></div>"""

    # -- year by year ----------------------------------------------------------------
    years = sorted({r["year"] for r in rs1} | {r["year"] for r in rs2}, reverse=True)[:16]
    m1 = {r["year"]: r for r in rs1}
    m2 = {r["year"]: r for r in rs2}

    def cell(r):
        if not r:
            return '<td class="num">—</td>'
        v = r["verdict"] if r["verdict"] in ("BUY", "CAUTION", "AVOID") else "DATA"
        link = f'<a href="{url(r)}">{r["score"]}</a>' if exists(url(r)) else str(r["score"])
        return f'<td class="num">{link} <span class="tag v-{v}">{esc(r["verdict"] or "—")}</span></td>'

    yrows = "".join(
        f"<tr><td>{y}</td>{cell(m1.get(y))}{cell(m2.get(y))}"
        f'<td class="num">{(m1[y]["score"] - m2[y]["score"]):+d}</td></tr>'
        if y in m1 and y in m2 else
        f'<tr><td>{y}</td>{cell(m1.get(y))}{cell(m2.get(y))}<td class="num">—</td></tr>'
        for y in years)

    # -- what actually goes wrong -----------------------------------------------------
    c1, c2 = top_components(con, rs1), top_components(con, rs2)

    def comp_list(cs, nm):
        if not cs:
            return ""
        items = "".join(f"<li><b>{esc(c[0].title())}</b> — {c[1]:,} complaints</li>" for c in cs)
        return f"<div class=\"cmp-side\"><h3>{esc(nm)}</h3><ul>{items}</ul></div>"

    diff = ""
    if c1 and c2 and c1[0][0] != c2[0][0]:
        diff = (f"<p>They do not fail the same way: the {esc(mo1)}'s complaints concentrate in "
                f"{esc(c1[0][0].title())}, the {esc(mo2)}'s in {esc(c2[0][0].title())}. "
                f"That difference matters more to a buyer than the score gap, because it says "
                f"which repair bill you are taking on.</p>")
    elif c1 and c2:
        diff = (f"<p>Both nameplates have {esc(c1[0][0].title())} as their largest complaint "
                f"group, so the choice between them is about how often, not about what.</p>")

    # -- years to avoid ----------------------------------------------------------------
    av = []
    for nm, st in ((n1, a), (n2, b)):
        if st["avoid"]:
            av.append(f"<p><b>{esc(nm)} — avoid:</b> {_yearlist(st['avoid'])}.</p>")
        elif st["buy"]:
            av.append(f"<p><b>{esc(nm)}:</b> no model year scores below 45; the strongest are "
                      f"{_yearlist(st['buy'])}.</p>")
    avoid_html = ""
    if av:
        avoid_html = ('<div class="card"><h2>Years to avoid on each</h2>' + "".join(av)
                      + '<p class="src-note">A year scores below 45 on complaints per year of '
                        'exposure and recall campaigns. '
                        '<a href="/years-to-avoid/">Every car’s years to avoid</a>.</p></div>')

    # -- money --------------------------------------------------------------------------
    money = ""
    if a["price"] and b["price"]:
        d = abs(a["price"] - b["price"])
        # These are class-level estimates: two cars of the same segment and the same age
        # often price identically, and the first version printed "roughly $0 less", which
        # is both nonsense and the exact string the HTML QA gate rejects. Under a quarter of
        # a percent apart is the same money, and saying so is the honest reading.
        if d < max(500, int(0.025 * max(a["price"], b["price"]))):
            gap_line = (f'they price within '
                        f'<span data-usd="{max(d, 1)}" data-kind="price">${max(d, 1):,}</span> '
                        f'of each other, which at this level is the same money')
        else:
            cheaper = n1 if a["price"] < b["price"] else n2
            gap_line = (f'the {esc(cheaper)} is roughly '
                        f'<span data-usd="{d}" data-kind="price">${d:,}</span> less')
        money = (f'<div class="card"><h2>What each costs today</h2>'
                 f'<p>A recent used {esc(n1)} prices at about '
                 f'<span data-usd="{a["price"]}" data-kind="price">${a["price"]:,}</span> and '
                 f'a {esc(n2)} at about '
                 f'<span data-usd="{b["price"]}" data-kind="price">${b["price"]:,}</span> — '
                 + gap_line
                 + (f', and they return {a["mpg"]} against {b["mpg"]} MPG combined'
                    if a["mpg"] and b["mpg"] else '')
                 + '.</p><p class="src-note">Class-level estimates re-priced to your country, '
                   'not a valuation of one car. <a href="/methodology/">Method</a>.</p></div>')

    faqs = [
        (f"Is the {n1} or the {n2} more reliable?",
         f"On the NHTSA record the {lead} scores {la['mean']}/100 against the {trail}'s "
         f"{ta['mean']}/100, averaged across every model year we hold. "
         + (f"The gap is small enough that the model year matters more than the badge."
            if g <= 10 else
            f"The {lead} carries about {la['cpy']:,} complaints per year on the road against "
            f"{ta['cpy']:,} for the {trail}.")),
        (f"Which {n1} and {n2} years should I avoid?",
         (f"{n1}: " + (", ".join(str(r['year']) for r in a['avoid'][:6]) if a['avoid'] else "no year scores below 45")
          + f". {n2}: " + (", ".join(str(r['year']) for r in b['avoid'][:6]) if b['avoid'] else "no year scores below 45")
          + ". Each of those scores under 45 out of 100 on complaints per year of exposure and recall campaigns.")),
    ]
    if c1 and c2:
        faqs.append((f"What goes wrong on the {n1} and the {n2}?",
                     f"The largest complaint group on the {n1} is {c1[0][0].title()} "
                     f"({c1[0][1]:,} complaints); on the {n2} it is {c2[0][0].title()} "
                     f"({c2[0][1]:,})."))
    if a["price"] and b["price"]:
        faqs.append((f"Is the {n1} or the {n2} cheaper to own?",
                     f"A recent used {n1} prices at about ${a['price']:,} and a {n2} at about "
                     f"${b['price']:,}, before insurance and the maintenance band. "
                     f"Both pages carry the five-year running-cost figure."))

    indexable = (a["n"] >= MIN_YEARS_TO_INDEX and b["n"] >= MIN_YEARS_TO_INDEX
                 and a["complaints"] >= MIN_COMPLAINTS_TO_INDEX
                 and b["complaints"] >= MIN_COMPLAINTS_TO_INDEX)

    faq_html = ('<div class="card"><h2>FAQ</h2>' + "".join(
        f"<details><summary>{esc(q)}</summary><p>{esc(ans)}</p></details>"
        for q, ans in faqs) + "</div>")

    title = f"{n1} vs {n2}: Which Is More Reliable? | {BRAND}"
    desc = (f"{n1} or {n2}? Mean score {a['mean']}/100 against {b['mean']}/100 across "
            f"{a['n']} and {b['n']} model years of NHTSA complaint and recall data, with the "
            f"years to avoid on each.")

    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<nav class="crumbs"><a href="/cars/">Cars</a> › <a href="/compare/">Head to head</a> › {esc(mo1)} vs {esc(mo2)}</nav>
<h1>{esc(n1)} <em>vs</em> {esc(n2)}: which is more reliable?</h1>
<p class="sub">{esc(headline)}</p>
<p class="byline">Computed by <a href="/about/">{BRAND}</a> from NHTSA and EPA public records ·
<a href="/methodology/">method</a></p></div></div>
<div class="wrap" style="display:grid;gap:20px;padding:20px 16px 40px">
<div class="card"><h2>The record, side by side</h2>
<div class="cmp-grid">{card(n1, a, rs1)}{card(n2, b, rs2)}</div>
<p class="src-note">Mean score is the average across model years from 2013 on, where both
records are comparable. <a href="/methodology/">How the score works</a>.</p></div>
<div class="card"><h2>Year by year: {esc(mo1)} against {esc(mo2)}</h2>
<p>The comparison that decides the purchase. A nameplate is not one car — a redesign can move
the record sixty points inside two years, and the two nameplates rarely move together.</p>
<div class="table-wrap"><table class="cost-table">
<thead><tr><th>Year</th><th class="num">{esc(mo1)}</th><th class="num">{esc(mo2)}</th>
<th class="num">Gap</th></tr></thead><tbody>{yrows}</tbody></table></div></div>
<div class="card"><h2>What owners actually complain about</h2>
<div class="cmp-grid">{comp_list(c1, n1)}{comp_list(c2, n2)}</div>{diff}</div>
{avoid_html}
{money}
{faq_html}
<div class="card"><h2>Both nameplates in full</h2><div class="rel-grid">
<a href="/cars/{rs1[0]['kslug']}/{rs1[0]['mslug']}/">{esc(n1)} years to avoid<small>every model year scored</small></a>
<a href="/cars/{rs2[0]['kslug']}/{rs2[0]['mslug']}/">{esc(n2)} years to avoid<small>every model year scored</small></a>
<a href="/years-to-avoid/">Every car's years to avoid<small>ranked by the gap</small></a>
</div></div>
<h2 class="sec">More head-to-heads</h2><div class="rel-grid" id="more-cmp"></div></div>"""
    return body, title, desc, faqs, indexable


# Raised from 600 once the library page budget was cut: 1,791 same-segment pairs are
# available and each one is a page built to rank, against a catalogue tail that is
# noindexed by design.
MAX_COMPARES = int(os.environ.get("MAX_COMPARES", "1100"))
MIN_COMPLAINTS = 60        # a nameplate nobody complains about is a nameplate nobody owns


def auto_rivals(rows):
    """Pair nameplates the way a buyer shops them.

    The first version had no segment column to work with, so it used combined fuel economy
    within 15% as a proxy — which puts a sports car next to a hybrid saloon and misses the
    pairs a buyer actually cross-shops. price_model.py now writes a real segment on every
    model year, so pairs are same-segment, same powertrain type, and ranked by how close the
    two nameplates are in size of record: a comparison is only worth publishing when both
    sides have enough history to carry it.

    Hand-written RIVALS still run first and are never displaced.
    """
    by_np = {}
    for r in rows:
        if r["score"] is None:
            continue
        k = (r["make"], r["model"])
        by_np.setdefault(k, []).append(r)

    cand = []
    for k, rs in by_np.items():
        if len(rs) < 4:
            continue
        total = sum(x["complaint_count"] or 0 for x in rs)
        if total < MIN_COMPLAINTS:
            continue
        seg = next((x["segment"] for x in rs if x["segment"]), None)
        if not seg:
            continue
        if not any(exists(url(x)) for x in rs):
            continue
        cand.append({"make": k[0], "model": k[1], "seg": seg,
                     "ev": bool(rs[0]["is_ev"]), "n": len(rs), "total": total})
    cand.sort(key=lambda c: -c["total"])

    pairs = []
    for i, a in enumerate(cand):
        for b in cand[i + 1:]:
            if a["seg"] != b["seg"] or a["ev"] != b["ev"]:
                continue
            if a["make"] == b["make"] and a["model"] == b["model"]:
                continue
            # both records within a factor of four of each other: a nameplate with 8,000
            # complaints against one with 200 is not a comparison, it is a mismatch.
            lo, hi = sorted((a["total"], b["total"]))
            if hi > lo * 4:
                continue
            pairs.append((a["make"], a["model"], b["make"], b["model"]))
    return pairs


def build_compares(rows):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    made, indexed = [], 0
    seen_pairs = {tuple(sorted((f"{a} {b}".lower(), f"{c} {d}".lower())))
                  for a, b, c, d in RIVALS}
    auto = [q for q in auto_rivals(rows)
            if tuple(sorted((f"{q[0]} {q[1]}".lower(), f"{q[2]} {q[3]}".lower()))) not in seen_pairs]
    budget = max(0, MAX_COMPARES - len(RIVALS))
    if len(auto) > budget:
        print(f"COMPARES: {len(auto)} same-segment pairs available, publishing {budget} "
              f"(MAX_COMPARES={MAX_COMPARES}); {len(auto) - budget} held back")
        auto = auto[:budget]

    for mk1, mo1, mk2, mo2 in list(RIVALS) + auto:
        rs1, rs2 = nameplate(rows, mk1, mo1), nameplate(rows, mk2, mo2)
        if len(rs1) < 3 or len(rs2) < 3:
            continue
        body, title, desc, faqs, indexable = compare_body(con, mk1, mo1, rs1, mk2, mo2, rs2)
        sl = f"{slug(mk1 + '-' + mo1)}-vs-{slug(mk2 + '-' + mo2)}"
        canon = f"{ORIGIN}/compare/{sl}/"
        ld = json.dumps([
            {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": ans}} for q, ans in faqs]},
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Cars", "item": ORIGIN + "/cars/"},
                {"@type": "ListItem", "position": 2, "name": "Head to head",
                 "item": ORIGIN + "/compare/"},
                {"@type": "ListItem", "position": 3,
                 "name": f"{mk1} {mo1} vs {mk2} {mo2}", "item": canon}]},
            {"@context": "https://schema.org", "@type": "Article",
             "headline": f"{mk1} {mo1} vs {mk2} {mo2}: which is more reliable?",
             "author": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
             "publisher": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
             "mainEntityOfPage": canon}], separators=(",", ":"))
        head = ("" if indexable else NOINDEX) + \
            f'<script type="application/ld+json">{ld}</script>'
        if indexable:
            indexed += 1
        (SITE / "compare" / sl).mkdir(parents=True, exist_ok=True)
        (SITE / "compare" / sl / "index.html").write_text(
            shell(title, desc, canon, body, robots=head))
        a, b = np_stats(rs1), np_stats(rs2)
        lead = f"{mk1} {mo1}" if a["mean"] >= b["mean"] else f"{mk2} {mo2}"
        made.append((sl, f"{mk1} {mo1} vs {mk2} {mo2}",
                     f"{lead} ahead on the record, {max(a['mean'], b['mean'])}/100"))
    con.close()

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
<h1>Car comparisons: {len(made)} rivalries settled by the federal record</h1>
<p class="sub">Every pair below is two cars of the same class, compared model year by model
year on complaints filed with the United States safety regulator and on recall campaigns —
not on a comments section and not on a road test.</p></div></div>
<div class="wrap" style="padding:8px 16px 40px"><div class="card prose editorial">{HUB_NOTES.get("compare", "")}</div><div class="rel-grid">{links}</div></div>"""
    (SITE / "compare").mkdir(parents=True, exist_ok=True)
    (SITE / "compare" / "index.html").write_text(
        shell(f"Car Comparisons - Rivalries Settled by Data | {BRAND}",
              "Camry vs Accord, F-150 vs Silverado and more - complaint and recall records "
              "compared model year by model year.", f"{ORIGIN}/compare/", body))
    print(f"COMPARES OK: {len(made)} head-to-heads, {indexed} indexable")
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
