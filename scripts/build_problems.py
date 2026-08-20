#!/usr/bin/env python3
"""build_problems.py — the highest-intent page family in car search: "<year> <car> problems".

Every model-year that carries complaint data earns /problems/<make>/<model>/<year>/ with the
top failing components, real owner narratives from the federal record, the recall list and a
verdict. A model index /problems/<make>/<model>/ names the worst year outright, and
/problems/ is a hall of shame ranked by complaints per year on the road — built to be
screenshotted and argued about.

Runs after gen_site (which wipes site/) and build_stories. Never fails the build.
"""
import html, json, os, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DB = ROOT / "data" / "cars.sqlite"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")
BRAND = "MotorJury"
MIN_COMPLAINTS = 25          # below this the page is thin; the model index still lists the year


def esc(s):
    return html.escape(str(s), quote=True)


def shell(title, desc, canon, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/site.css"></head><body>
<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="/">Car<em>Verdict</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="Search any car" autocomplete="off" aria-label="search"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/cars/">Browse</a><a href="/problems/">Problems</a><a href="/compare/">Compare</a><a href="/stories/">Stories</a><a href="/library/">Library</a></nav>
</div></header>
{body}
<footer><div class="wrap"><p>Every number on this page is computed from NHTSA public records.
· <a href="/methodology/">Methodology</a></p></div></footer>
<script src="/assets/site.js" defer></script></body></html>"""


def share_row(url, text):
    """Plain intent links - no scripts, no trackers, works everywhere."""
    import urllib.parse as up
    q = up.quote(text + " " + url)
    return (f'<div class="share-row"><a class="sbtn" href="https://twitter.com/intent/tweet?text={q}" rel="noopener">Share on X</a>'
            f'<a class="sbtn" href="https://wa.me/?text={q}" rel="noopener">WhatsApp</a>'
            f'<a class="sbtn" href="https://www.reddit.com/submit?url={up.quote(url)}&title={up.quote(text)}" rel="noopener">Reddit</a></div>')


def load():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT my.id my_id, mk.name make, mo.name model, mo.slug mslug,
        mk.slug kslug, my.year, my.complaint_count cc, my.recall_count rc,
        my.severe_recalls sev, cs.reliability_score score, cs.verdict,
        cs.complaints_per_year cpy
        FROM model_years my
        JOIN models mo ON mo.id = my.model_id
        JOIN makes mk ON mk.id = mo.make_id
        LEFT JOIN computed_scores cs ON cs.my_id = my.id""").fetchall()
    comp, quotes, recalls = {}, {}, {}
    for r in con.execute("SELECT my_id, component, count, sample FROM complaints"):
        if r["component"] == "__quote__":
            quotes.setdefault(r["my_id"], []).append(r["sample"])
        elif r["component"]:
            comp.setdefault(r["my_id"], []).append((r["component"], r["count"] or 0))
    for r in con.execute("SELECT my_id, campaign, date, component, summary, severe FROM recalls"):
        recalls.setdefault(r["my_id"], []).append(dict(r))
    con.close()
    return rows, comp, quotes, recalls


def year_page(r, comps, qs, recs):
    name = f"{r['year']} {r['make']} {r['model']}"
    url = f"/problems/{r['kslug']}/{r['mslug']}/{r['year']}/"
    top = comps[0][0].title() if comps else "unknown"
    total_c = sum(n for _, n in comps) or 1
    bars = "".join(
        f'<div class="pb-row"><span>{esc(c.title())}</span>'
        f'<i style="width:{max(4, round(100 * n / max(x[1] for x in comps)))}%"></i><b>{n}</b></div>'
        for c, n in comps[:8])
    quote_html = "".join(f'<blockquote class="owner-q">&ldquo;{esc(q)}&rdquo;'
                         f'<small>NHTSA complaint, {r["year"]} {esc(r["make"])} {esc(r["model"])} owner</small></blockquote>'
                         for q in qs[:3] if q)
    SAFETY_TAG = ' <span class="tag v-AVOID">SAFETY</span>'
    rec_html = "".join(
        f'<tr><td>{esc(x["date"] or "")}</td><td>{esc((x["component"] or "").title())}'
        f'{SAFETY_TAG if x["severe"] else ""}</td>'
        f'<td>{esc((x["summary"] or "")[:220])}</td></tr>' for x in recs[:10])
    verdict = r["verdict"] or "DATA"
    data_link = (
        f'<a href="/cars/{r["kslug"]}/{r["mslug"]}/{r["year"]}/">Full {r["year"]} data page'
        f'<small>costs, verdict, every number</small></a>'
        if (SITE / "cars" / r["kslug"] / r["mslug"] / str(r["year"]) / "index.html").exists() else "")
    faq = [
        (f"Is the {name} reliable?",
         f"On the federal record it scores {r['score'] or '?'}/100: {r['cc'] or 0:,} owner complaints "
         f"({r['cpy'] or 0:g} per year on the road) and {r['rc'] or 0} recall campaigns, "
         f"{r['sev'] or 0} touching safety-critical systems."),
        (f"What is the most common problem with the {name}?",
         f"The most-reported component in NHTSA complaints is {top}, with {comps[0][1] if comps else 0} "
         f"of {total_c} categorised reports."),
    ]
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    body = f"""<div class="hero"><div class="wrap hero-inner">
<nav class="crumbs"><a href="/problems/">Problems</a> › <a href="/problems/{r['kslug']}/{r['mslug']}/">{esc(r['make'])} {esc(r['model'])}</a> › {r['year']}</nav>
<h1>{esc(name)} Problems</h1>
<p class="sub">{r['cc'] or 0:,} owner complaints filed with the United States safety regulator ·
top issue: <b>{esc(top)}</b> · verdict <span class="tag v-{verdict if verdict in ('BUY','CAUTION','AVOID') else 'DATA'}">{esc(verdict)}</span> {r['score'] or '?'}/100</p>
<div class="triad"><b>Source</b> NHTSA public complaint and recall record · <a href="/methodology/">methodology</a></div>
</div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0;max-width:860px">
<div class="card"><h2>What breaks, by owner reports</h2><div class="pb">{bars or '<p>No categorised component data.</p>'}</div></div>
{f'<div class="card"><h2>In the owners&rsquo; words</h2>{quote_html}</div>' if quote_html else ''}
{f'<div class="card"><h2>Recall campaigns</h2><table><thead><tr><th>Reported</th><th>Component</th><th>Summary</th></tr></thead><tbody>{rec_html}</tbody></table></div>' if rec_html else ''}
<div class="card"><h2>Questions owners ask</h2>{faq_html}</div>
<div class="card"><h2>Share this verdict</h2>
<p>The {esc(name)} scored {r['score'] or '?'}/100 on the federal record.</p>
{share_row(ORIGIN + url, f"The {name} scored {r['score'] or '?'}/100 - {r['cc'] or 0:,} owner complaints, top issue: {top}.")}</div>
<div class="rel-grid">{data_link}<a href="/problems/{r['kslug']}/{r['mslug']}/">All {esc(r['model'])} years<small>which year to avoid</small></a>
<a href="/stories/most-complained/">Most complained-about cars<small>the national ranking</small></a></div>
</div>
<script type="application/ld+json">{json.dumps(faq_ld)}</script>"""
    d = SITE / "problems" / r["kslug"] / r["mslug"] / str(r["year"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(shell(
        f"{name} Problems: Top Issues, Complaints & Recalls | {BRAND}",
        f"{name} problems from {r['cc'] or 0:,} NHTSA owner complaints: top issue {top}, "
        f"{r['rc'] or 0} recalls. Verdict: {verdict} {r['score'] or '?'}/100.", ORIGIN + url, body))
    return url


def model_page(key, years):
    make, model, kslug, mslug = key
    years = sorted(years, key=lambda r: -r["year"])
    worst = min(years, key=lambda r: (r["score"] if r["score"] is not None else 101))
    best = max(years, key=lambda r: (r["score"] if r["score"] is not None else -1))
    rows = "".join(
        f'<tr><td><a href="/problems/{kslug}/{mslug}/{r["year"]}/">{r["year"]}</a></td>'
        f'<td>{r["score"] if r["score"] is not None else "—"}</td>'
        f'<td><span class="tag v-{r["verdict"] if r["verdict"] in ("BUY","CAUTION","AVOID") else "DATA"}">{esc(r["verdict"] or "DATA")}</span></td>'
        f'<td>{r["cc"] or 0:,}</td><td>{r["rc"] or 0}</td></tr>'
        for r in years if r["page"])
    url = f"/problems/{kslug}/{mslug}/"
    hub_link = (
        f'<a href="/cars/{kslug}/{mslug}/">{esc(make)} {esc(model)} data hub<small>costs and verdicts</small></a>'
        if (SITE / "cars" / kslug / mslug / "index.html").exists() else "")
    title = f"{make} {model} Problems by Year: Worst & Best Years"
    body = f"""<div class="hero"><div class="wrap hero-inner">
<nav class="crumbs"><a href="/problems/">Problems</a> › {esc(make)} {esc(model)}</nav>
<h1>{esc(make)} {esc(model)}: Worst &amp; Best Years</h1>
<p class="sub">Avoid the <b>{worst['year']}</b> ({worst['score']}/100, {worst['cc'] or 0:,} complaints).
The cleanest record is the <b>{best['year']}</b> ({best['score']}/100). Judged on federal complaint
and recall data only.</p></div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0;max-width:860px">
<div class="card"><h2>Every year on record</h2>
<table><thead><tr><th>Year</th><th>Score</th><th>Verdict</th><th>Complaints</th><th>Recalls</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="card"><h2>Share it</h2>{share_row(ORIGIN + url, f"Worst {make} {model} year: {worst['year']} ({worst['score']}/100, {worst['cc'] or 0:,} federal complaints). Best: {best['year']}.")}</div>
<div class="rel-grid">{hub_link}<a href="/problems/">All problem rankings<small>the hall of shame</small></a></div></div>"""
    d = SITE / "problems" / kslug / mslug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(shell(
        title + f" | {BRAND}",
        f"Which {make} {model} year to avoid: {worst['year']} scored {worst['score']}/100 with "
        f"{worst['cc'] or 0:,} NHTSA complaints. Best year: {best['year']}.", ORIGIN + url, body))


def hall_of_shame(rows):
    ranked = sorted([r for r in rows if r["score"] is not None and (r["cc"] or 0) >= 100],
                    key=lambda r: -(r["cpy"] or 0))[:25]
    items = "".join(
        f'<li><a href="/problems/{r["kslug"]}/{r["mslug"]}/{r["year"]}/">{r["year"]} {esc(r["make"])} {esc(r["model"])}'
        f'<small>{r["cpy"]:g} complaints per year on the road · score {r["score"]}/100</small></a></li>'
        for r in ranked)
    url = "/problems/"
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>Car Problems, Ranked</h1>
<p class="sub">The 25 model years American owners complain about most, normalised per year on
the road. Computed from the federal record on every build - nobody edits this list.</p></div></div>
<div class="wrap" style="padding:8px 16px 40px;max-width:860px">
<ol class="story-list">{items}</ol>
<div class="card" style="margin-top:20px"><h2>Share the list</h2>
{share_row(ORIGIN + url, "The 25 most complained-about cars in America, straight from the federal record:")}</div></div>"""
    (SITE / "problems").mkdir(parents=True, exist_ok=True)
    (SITE / "problems" / "index.html").write_text(shell(
        f"Car Problems Ranked: The Most Complained-About Cars | {BRAND}",
        "The most complained-about model years in America, ranked from NHTSA owner "
        "complaints. Updated on every build.", ORIGIN + url, body))


CSS_EXTRA = """
/* problems pages: complaint bars */
.pb-row{display:grid;grid-template-columns:170px 1fr 46px;gap:10px;align-items:center;
  padding:6px 0;font-size:14px}
.pb-row span{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pb-row i{display:block;height:10px;border-radius:3px;background:var(--brand);opacity:.85}
.pb-row b{text-align:right;font-variant-numeric:tabular-nums}
@media(max-width:600px){.pb-row{grid-template-columns:110px 1fr 40px;font-size:12.5px}}
"""


def main():
    if not DB.exists() or not (SITE / "index.html").exists():
        print("PROBLEMS SKIPPED: no database or site yet")
        return 0
    css = SITE / "assets" / "site.css"
    if css.exists() and ".pb-row" not in css.read_text():
        css.write_text(css.read_text() + CSS_EXTRA)
    rows, comp, quotes, recalls = load()
    by_model, made = {}, 0
    for r in rows:
        rr = dict(r)
        rr["page"] = (r["cc"] or 0) >= MIN_COMPLAINTS
        if rr["page"]:
            year_page(r, sorted(comp.get(r["my_id"], []), key=lambda x: -x[1]),
                      quotes.get(r["my_id"], []), recalls.get(r["my_id"], []))
            made += 1
        by_model.setdefault((r["make"], r["model"], r["kslug"], r["mslug"]), []).append(rr)
    n_models = 0
    for key, years in by_model.items():
        if any(y["page"] for y in years):
            model_page(key, years)
            n_models += 1
    hall_of_shame(rows)
    # surface on the home Explore grid
    home = SITE / "index.html"
    h = home.read_text()
    hook = '<div class="rel-grid"><a href="/stories/">'
    if hook in h and 'href="/problems/"' not in h:
        h = h.replace(hook, '<div class="rel-grid">'
                      '<a href="/problems/">Problems, ranked<small>what actually breaks, by owner reports</small></a>'
                      '<a href="/stories/">', 1)
        home.write_text(h)
    print(f"PROBLEMS OK: {made} year pages, {n_models} model pages, 1 ranking")
    return 0


if __name__ == "__main__":
    sys.exit(main())
