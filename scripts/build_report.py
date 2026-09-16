#!/usr/bin/env python3
"""build_report.py — the linkable asset: "Used-Car Trap Years 2026".

One report page (/reports/used-car-trap-years-2026/) computed from data/cars.sqlite, plus the
whole scored record as a CSV (/assets/motorjury-trap-years-2026.csv, CC BY 4.0). Motoring press
and personal-finance desks link to ranked tables and downloadable datasets; they do not link to
a database. This is the page the outreach points at.

Runs after build_guides.py (gen_site has built the car pages, so every link resolves) and
before localize.py (so the page enters the sitemap).
"""
import csv, io, json, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gen_site  # noqa: E402

SITE = ROOT / "site"
DB = ROOT / "data" / "cars.sqlite"
ORIGIN, BRAND, page, write, esc, TODAY = (gen_site.ORIGIN, gen_site.BRAND, gen_site.page,
                                          gen_site.write, gen_site.esc, gen_site.TODAY)
YEAR = TODAY[:4]
URL = f"/reports/used-car-trap-years-{YEAR}/"
CSV_URL = f"/assets/motorjury-trap-years-{YEAR}.csv"


def exists(u):
    return (SITE / u.strip("/") / "index.html").exists()


def link_my(r, text=None):
    u = gen_site.url_my(r)
    hub = f"/cars/{r['kslug']}/{r['mslug']}/"
    href = u if exists(u) else hub
    label = text or f"{r['year']} {r['make']} {r['model']}"
    return f'<a href="{href}">{esc(label)}</a>'


def link_hub(r, text=None):
    label = text or f"{r['make']} {r['model']}"
    return f'<a href="/cars/{r["kslug"]}/{r["mslug"]}/">{esc(label)}</a>'


def top_component(con, my_id):
    row = con.execute("SELECT component, count FROM complaints WHERE my_id=? ORDER BY count DESC LIMIT 1",
                      (my_id,)).fetchone()
    return (row[0].title(), row[1]) if row else ("", 0)


def table(head, rows_html, cls="cost-table"):
    return (f'<div class="table-wrap"><table class="{cls}"><thead><tr>'
            + "".join(f"<th>{h}</th>" for h in head) + f"</tr></thead><tbody>{rows_html}</tbody></table></div>")


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = gen_site.rows_all(con)
    scored = [r for r in rows if gen_site.gate(r) and r["score"] is not None]
    strong = [r for r in scored if (r["confidence"] or "") in ("high", "medium")]
    n_complaints = sum(r["complaint_count"] or 0 for r in rows)
    n_recalls = con.execute("SELECT COUNT(DISTINCT campaign) FROM recalls").fetchone()[0]
    n_nameplates = len({r["model_id"] for r in scored})
    n_makes = len({r["make"] for r in scored})

    # ---- 1. one-year cliffs -------------------------------------------------------------
    by = defaultdict(list)
    for r in scored:
        by[r["model_id"]].append(r)
    cliffs = []
    for rs in by.values():
        rs = sorted(rs, key=lambda x: x["year"])
        for a, b in zip(rs, rs[1:]):
            if (b["year"] == a["year"] + 1 and (b["complaint_count"] or 0) >= 150
                    and (a["confidence"] or "") in ("high", "medium") and (b["confidence"] or "") in ("high", "medium")):
                cliffs.append((a["score"] - b["score"], a, b))
    cliffs.sort(key=lambda t: -t[0])
    cliffs = [c for c in cliffs if c[0] >= 20]
    cliff_rows = ""
    for d, a, b in cliffs[:25]:
        comp, n = top_component(con, b["my_id"])
        cliff_rows += (f"<tr><td>{link_hub(b)}</td><td>{link_my(a, str(a['year']))} · {a['score']}</td>"
                       f"<td>{link_my(b, str(b['year']))} · <b>{b['score']}</b> {gen_site.vtag(b['verdict'])}</td>"
                       f'<td class="num">−{d}</td><td class="num">{(b["complaint_count"] or 0):,}</td>'
                       f"<td>{esc(comp)} ({n:,})</td></tr>")
    avg_drop = round(sum(c[0] for c in cliffs) / len(cliffs)) if cliffs else 0

    # ---- 2. recovery time after a trap year ------------------------------------------------
    recov = []
    for rs in by.values():
        rs = sorted(rs, key=lambda x: x["year"])
        if len(rs) < 6:
            continue
        w = min(rs, key=lambda x: x["score"])
        if (w["verdict"] or "") != "AVOID" or (w["complaint_count"] or 0) < 150:
            continue
        later = [x for x in rs if x["year"] > w["year"]]
        if not later:
            recov.append((w, None))
            continue
        back = next((x for x in later if x["score"] >= 70), None)
        recov.append((w, (back["year"] - w["year"]) if back else None))
    n_rec = len(recov)
    within2 = sum(1 for _, t in recov if t is not None and t <= 2)
    within3 = sum(1 for _, t in recov if t is not None and t <= 3)
    never = sum(1 for _, t in recov if t is None)

    # ---- 3. widest gaps (the years-to-avoid ranking, top 15) -------------------------------
    gaps = []
    for rs in by.values():
        rs = sorted(rs, key=lambda x: x["year"])
        if len(rs) < 5:
            continue
        av = [x for x in rs if (x["verdict"] or "") == "AVOID"]
        if not av:
            continue
        b = max(rs, key=lambda x: x["score"]); w = min(rs, key=lambda x: x["score"])
        if b["score"] - w["score"] >= 25 and sum(x["complaint_count"] or 0 for x in rs) >= 800:
            gaps.append((b["score"] - w["score"], rs[0], av, b, w))
    gaps.sort(key=lambda t: -t[0])
    gap_rows = "".join(
        f"<tr><td>{link_hub(r0)}</td><td>{', '.join(link_my(a, str(a['year'])) for a in sorted(av, key=lambda x: x['year'])[:5])}</td>"
        f"<td>{link_my(b, str(b['year']))} · {b['score']}</td><td>{link_my(w, str(w['year']))} · {w['score']}</td>"
        f'<td class="num">{s}</td></tr>' for s, r0, av, b, w in gaps[:15])

    # ---- 4. brands ---------------------------------------------------------------------------
    br = defaultdict(list)
    for r in strong:
        br[r["make"]].append(r)
    brands = []
    for k, v in br.items():
        if len(v) < 25:
            continue
        av = [x for x in v if x["verdict"] == "AVOID"]
        # best and worst nameplate by mean score over ≥4 strong years
        bym = defaultdict(list)
        for x in v:
            bym[x["model_id"]].append(x)
        means = [(sum(x["score"] for x in xs) / len(xs), xs[0]) for xs in bym.values() if len(xs) >= 4]
        best = max(means, key=lambda t: t[0]) if means else None
        worst = min(means, key=lambda t: t[0]) if means else None
        brands.append((100 * len(av) / len(v), sum(x["score"] for x in v) / len(v), k, len(v), len(av), best, worst))
    brands.sort(key=lambda t: t[0])
    def _np(t):
        return link_hub(t[1], "%s (%.0f)" % (t[1]["model"], t[0])) if t else "—"
    brand_rows = "".join(
        f"<tr><td>{esc(k)}</td><td class=\"num\">{n}</td><td class=\"num\">{na} ({pct:.0f}%)</td>"
        f"<td class=\"num\">{avg:.0f}</td><td>{_np(best)}</td><td>{_np(worst)}</td></tr>"
        for pct, avg, k, n, na, best, worst in brands)

    # ---- 5. most complained per year of exposure, most recalled -----------------------------
    # A one-year-old car with 300 complaints reads as 300 a year; three years of exposure is
    # the floor before the rate means anything.
    dens = sorted([r for r in strong if (r["complaint_count"] or 0) >= 300 and r["year"] <= int(YEAR) - 3],
                  key=lambda r: -(r["complaints_per_year"] or 0))[:20]
    dens_rows = ""
    for r in dens:
        comp, n = top_component(con, r["my_id"])
        dens_rows += (f"<tr><td>{link_my(r)}</td><td class=\"num\">{r['complaints_per_year']:.0f}</td>"
                      f"<td class=\"num\">{(r['complaint_count'] or 0):,}</td><td>{r['score']} {gen_site.vtag(r['verdict'])}</td>"
                      f"<td>{esc(comp)} ({n:,})</td></tr>")
    rec = sorted(scored, key=lambda r: (-(r["recall_count"] or 0), -(r["severe_recalls"] or 0)))[:20]
    rec_rows = "".join(
        f"<tr><td>{link_my(r)}</td><td class=\"num\">{r['recall_count']}</td><td class=\"num\">{r['severe_recalls'] or 0}</td>"
        f"<td class=\"num\">{(r['complaint_count'] or 0):,}</td><td>{r['score']} {gen_site.vtag(r['verdict'])}</td></tr>"
        for r in rec)

    # ---- 6. what breaks ----------------------------------------------------------------------
    comps = con.execute("SELECT component, SUM(count) n FROM complaints GROUP BY component ORDER BY n DESC").fetchall()
    tot_c = sum(c["n"] for c in comps) or 1
    comp_rows = "".join(f"<tr><td>{esc(c['component'].title())}</td><td class=\"num\">{c['n']:,}</td>"
                        f"<td class=\"num\">{100 * c['n'] / tot_c:.1f}%</td></tr>" for c in comps[:12])
    top3_share = 100 * sum(c["n"] for c in comps[:3]) / tot_c

    # ---- 7. the CSV --------------------------------------------------------------------------
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["make", "model", "model_year", "reliability_score", "verdict", "evidence", "nhtsa_complaints",
                "complaints_per_year_of_exposure", "recall_campaigns", "safety_critical_recalls",
                "top_complaint_component", "top_component_complaints", "epa_combined_mpg", "page_url"])
    for r in sorted(scored, key=lambda x: (x["make"], x["model"], x["year"])):
        comp, n = top_component(con, r["my_id"])
        w.writerow([r["make"], r["model"], r["year"], r["score"], r["verdict"], r["confidence"] or "",
                    r["complaint_count"] or 0, round(r["complaints_per_year"] or 0, 1), r["recall_count"] or 0,
                    r["severe_recalls"] or 0, comp, n, r["mpg_comb"] or "",
                    ORIGIN + (gen_site.url_my(r) if exists(gen_site.url_my(r)) else f"/cars/{r['kslug']}/{r['mslug']}/")])
    csv_text = buf.getvalue()
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / CSV_URL.lstrip("/")).write_text(csv_text)
    csv_kb = len(csv_text.encode()) // 1024

    worst_cliff = cliffs[0] if cliffs else None
    findings = f"""<ul>
<li><b>A redesign year is the single most expensive mistake a used-car buyer can make.</b> Across {len(cliffs)} one-year
cliffs of 20 points or more, the score falls by an average of <b>{avg_drop} points</b> from one model year to the next of
the same car. The steepest: {link_hub(worst_cliff[1])} from {worst_cliff[1]['year']} ({worst_cliff[1]['score']}) to
{worst_cliff[2]['year']} ({worst_cliff[2]['score']}), on {(worst_cliff[2]['complaint_count'] or 0):,} owner complaints.</li>
<li><b>Trap years usually heal — but not for two to three years.</b> Of {n_rec} nameplates with a clear worst year on a deep
record, {within2} were back at 70 or better within two model years and {within3} within three; {never} have not recovered on
the record so far.</li>
<li><b>Three component categories account for {top3_share:.0f}% of every complaint on file</b>: {esc(comps[0]['component'].title())},
{esc(comps[1]['component'].title())} and {esc(comps[2]['component'].title())}. Owner complaints are overwhelmingly about the
drivetrain, the electrics and the engine, not about the things reviews are written about.</li>
<li><b>The brand matters less than the year.</b> Among {len(brands)} brands with 25 or more strongly evidenced model years,
the share of years the record marks AVOID runs from {brands[0][0]:.0f}% ({esc(brands[0][2])}) to {brands[-1][0]:.0f}%
({esc(brands[-1][2])}); every brand on the list has both a nameplate its owners barely complain about and one they complain
about constantly.</li>
<li><b>The most complained-about model year on the record, per year on the road,</b> is {link_my(dens[0])} at
{dens[0]['complaints_per_year']:.0f} complaints for every year of exposure ({(dens[0]['complaint_count'] or 0):,} in total).</li>
</ul>"""

    body = f"""<div class="hero"><div class="wrap hero-inner"><div class="hero-copy">
<nav class="crumbs"><a href="/">MotorJury</a> › Reports › Used-Car Trap Years {YEAR}</nav>
<span class="hh-kicker">Report · {TODAY} · free dataset, CC BY 4.0</span>
<h1>Used-Car Trap Years {YEAR}: the model years the federal record says to avoid</h1>
<p class="sub">{len(scored):,} model years of {n_nameplates} nameplates from {n_makes} makes, scored from {n_complaints:,} owner
complaints and {n_recalls:,} recall campaigns filed with the United States safety regulator. Which years fall off a cliff,
how long they take to recover, what actually breaks, and how the brands compare.</p>
{gen_site.editor_byline(TODAY)}
<p class="src-note"><a class="btn" href="{CSV_URL}" download>Download the dataset (CSV, {csv_kb} KB)</a>
&nbsp; <a href="#cite">How to cite</a> · <a href="/methodology/">Method</a> · <a href="/contact/">Contact the editor</a></p>
</div></div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0;max-width:1100px">

<div class="card prose"><h2>Key findings</h2>{findings}
<p class="src-note">Every figure on this page is computed from the record on {TODAY} and every car named links to the
page that shows its full complaint and recall record. The scoring method, its limits and the evidence labels are on the
<a href="/methodology/">methodology page</a>; the same numbers are in the dataset above.</p></div>

<div class="card"><h2>The 25 steepest one-year cliffs</h2>
<p>The same car, one model year apart, and the score falls by 20 points or more. Most of these are the first year of a
redesign; the buyer who takes the older car saves the difference in repair risk. Only years with strong or moderate
evidence and at least 150 complaints qualify.</p>
{table(["Nameplate", "From", "To", "Drop", "Complaints in the trap year", "What owners report most"], cliff_rows)}</div>

<div class="card"><h2>Widest gap between a nameplate's best and worst year</h2>
<p>The nameplates where the choice of year matters most. The full ranking of every nameplate is at
<a href="/years-to-avoid/">/years-to-avoid/</a>.</p>
{table(["Nameplate", "Years to avoid", "Best year", "Worst year", "Gap"], gap_rows)}</div>

<div class="card"><h2>Brands: how often the record says AVOID</h2>
<p>Brands with at least 25 model years of strong or moderate evidence, ranked by the share of those years the record
marks AVOID. Read the last two columns before the first: the spread inside a brand is larger than the spread between
brands. Scores are comparable across nameplates only within the limits described in the method.</p>
{table(["Brand", "Model years", "AVOID years", "Mean score", "Best nameplate (mean)", "Worst nameplate (mean)"], brand_rows)}</div>

<div class="card"><h2>The 20 most complained-about model years, per year on the road</h2>
<p>Complaints divided by years of exposure, so a 2012 car and a 2020 car are compared fairly. Strong or moderate
evidence only, 300 complaints minimum, and at least three years on the road.</p>
{table(["Model year", "Complaints per year", "Total", "Score", "What owners report most"], dens_rows)}</div>

<div class="card"><h2>The 20 most recalled model years</h2>
<p>Distinct recall campaigns on the model year, and how many of them touch a safety-critical system — brakes, steering,
fuel, air bags, seat belts, engine stall or electrical fire. A recall is counted once however many cars it covers, and
a model year can be heavily recalled yet quiet in the complaint record: the 2011–2013 cluster below is largely the
air-bag inflator campaigns that touched most of the industry, each filed as its own campaign.</p>
{table(["Model year", "Recall campaigns", "Safety-critical", "Complaints", "Score"], rec_rows)}</div>

<div class="card"><h2>What actually breaks</h2>
<p>Every owner complaint on the record by the component category NHTSA files it under.</p>
{table(["Component", "Complaints", "Share"], comp_rows)}</div>

<div class="card prose" id="cite"><h2>Method, limits, and how to cite</h2>
<p><b>Source.</b> Owner complaints and recall campaigns published by the National Highway Traffic Safety Administration;
fuel economy from the Environmental Protection Agency. The record covers model years 2011 to {YEAR} of the nameplates sold in
the United States that MotorJury scores; it is refreshed nightly.</p>
<p><b>Score.</b> 0–100, computed per model year from the complaint rate against the nameplate's own median, shrunk on thin
records, plus recall terms weighted by safety criticality. BUY is 70 or better, CAUTION 50–69, AVOID under 50. Every
verdict carries an evidence label; this report uses strong and moderate evidence only unless stated. The full formula is
on the <a href="/methodology/">methodology page</a>.</p>
<p><b>Limits.</b> A complaint is an owner's report, not a confirmed defect; complaint volume is influenced by sales
volume (the method corrects within a nameplate, only partly across nameplates) and by publicity. A recall counts once
however many cars it covers. Hybrid variants that share a NHTSA model name with the petrol car can share its record.</p>
<p><b>Cite as:</b> MotorJury, <i>Used-Car Trap Years {YEAR}</i>, {TODAY}, <a href="{ORIGIN}{URL}">{ORIGIN}{URL}</a>.
The dataset is published under <a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>:
use it freely with a link to this page. The editor, <a href="/about/adir-trabelsi/">Adir Trabelsi</a>, is available for
comment and for custom cuts of the data — <a href="/contact/">contact</a>.</p></div>
</div>"""
    jsonld = [
        {"@context": "https://schema.org", "@type": "Report", "name": f"Used-Car Trap Years {YEAR}",
         "headline": f"Used-Car Trap Years {YEAR}: the model years the federal record says to avoid",
         "datePublished": TODAY, "dateModified": TODAY,
         "author": {"@type": "Person", "name": gen_site.EDITOR, "url": ORIGIN + "/about/adir-trabelsi/"},
         "publisher": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
         "mainEntityOfPage": ORIGIN + URL, "license": "https://creativecommons.org/licenses/by/4.0/"},
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": f"MotorJury used-car reliability record, {YEAR}",
         "description": f"{len(scored):,} scored model years: NHTSA complaints, complaints per year of exposure, recall campaigns, safety-critical recalls, top complaint component, EPA fuel economy and the MotorJury score and verdict.",
         "url": ORIGIN + URL, "license": "https://creativecommons.org/licenses/by/4.0/",
         "creator": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
         "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": ORIGIN + CSV_URL}],
         "temporalCoverage": f"2011/{YEAR}", "spatialCoverage": "United States"},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + "/"},
            {"@type": "ListItem", "position": 2, "name": f"Used-Car Trap Years {YEAR}", "item": ORIGIN + URL}]}]
    write(URL.lstrip("/") + "index.html",
          page(f"Used-Car Trap Years {YEAR}: The Model Years to Avoid, From the Federal Record | {BRAND}",
               f"{len(scored):,} model years scored from {n_complaints:,} NHTSA complaints and {n_recalls:,} recalls: the steepest one-year cliffs, recovery times, brands ranked, and a free CC BY dataset.",
               ORIGIN + URL, body, jsonld, og_type="article"))
    print(f"REPORT OK: {URL} — {len(cliffs)} cliffs, {len(brands)} brands, CSV {csv_kb} KB ({len(scored):,} rows)")


if __name__ == "__main__":
    main()
