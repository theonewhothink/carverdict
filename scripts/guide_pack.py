#!/usr/bin/env python3
"""guide_pack.py — the fact sheet a guide is written from.

Usage: python3 scripts/guide_pack.py make/model [make/model ...] > pack.md

Prints, for each nameplate, everything in data/cars.sqlite a writer may cite: every model
year with its score, verdict, evidence label, complaint total, complaints per year of
exposure, recall campaigns (with the safety-critical count), the top complaint components
per year, every recall campaign on record with its summary, and the EPA fuel line. Nothing
outside this sheet is a fact the guide may state as one.
"""
import json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cars.sqlite"
from datetime import date
THIS_YEAR = date.today().year


def pack(con, key):
    kslug, mslug = key.split("/")
    rows = con.execute("""SELECT my.id, mk.name, mo.name, my.year, my.complaint_count, my.recall_count,
        my.severe_recalls, my.is_ev, s.reliability_score, s.verdict, s.confidence, s.complaints_per_year,
        f.fuel_type, f.mpg_comb, f.annual_fuel_cost, f.ev_range
        FROM model_years my JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
        LEFT JOIN computed_scores s ON s.my_id=my.id LEFT JOIN fuel f ON f.my_id=my.id
        WHERE mk.slug=? AND mo.slug=? ORDER BY my.year""", (kslug, mslug)).fetchall()
    if not rows:
        return f"## {key}: NOT IN DATABASE\n"
    make, model = rows[0][1], rows[0][2]
    out = [f"## {make} {model}  (page: /cars/{kslug}/{mslug}/)"]
    tot_c = sum(r[4] or 0 for r in rows)
    tot_r = sum(r[5] or 0 for r in rows)
    scored = [r for r in rows if r[8] is not None]
    out.append(f"Years on record: {rows[0][3]}–{rows[-1][3]} ({len(rows)} model years, {len(scored)} scored). "
               f"Total NHTSA complaints: {tot_c:,}. Total recall campaigns: {tot_r}.")
    if scored:
        best = max(scored, key=lambda r: r[8]); worst = min(scored, key=lambda r: r[8])
        out.append(f"Best year: {best[3]} ({best[8]}/100 {best[9]}). Worst year: {worst[3]} ({worst[8]}/100 {worst[9]}).")
    out.append("")
    out.append("| Year | Score | Verdict | Evidence | Complaints | Complaints/yr on road | Recalls | Safety-critical recalls | Fuel |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        fuel = ""
        if r[12]:
            fuel = f"{r[12]}"
            if r[13]:
                fuel += f" {r[13]:.0f} mpg comb"
            if r[15]:
                fuel += f", {r[15]:.0f} mi range"
        out.append(f"| {r[3]} | {r[8] if r[8] is not None else '—'} | {r[9] or '—'} | {r[10] or '—'} | "
                   f"{r[4] or 0:,} | {r[11] or 0:.1f} | {r[5] or 0} | {r[6] or 0} | {fuel} |")
    out.append("")
    out.append("Top complaint components by year (NHTSA component category: count):")
    for r in rows:
        comps = con.execute("SELECT component, count FROM complaints WHERE my_id=? ORDER BY count DESC LIMIT 5",
                            (r[0],)).fetchall()
        if comps and (r[4] or 0) >= 20:
            out.append(f"- {r[3]}: " + "; ".join(f"{c.title()}: {n}" for c, n in comps))
    out.append("")
    recs = con.execute("""SELECT my.year, rc.campaign, rc.date, rc.component, rc.summary, rc.severe
        FROM recalls rc JOIN model_years my ON my.id=rc.my_id JOIN models mo ON mo.id=my.model_id
        JOIN makes mk ON mk.id=mo.make_id WHERE mk.slug=? AND mo.slug=? ORDER BY my.year, rc.date""",
                       (kslug, mslug)).fetchall()
    seen = set(); lines = []
    for y, camp, d, comp, summ, sev in recs:
        if camp in seen:
            continue
        seen.add(camp)
        yrs = sorted({yy for yy, cc, *_ in recs if cc == camp})
        span = f"{yrs[0]}" if len(yrs) == 1 else f"{yrs[0]}–{yrs[-1]}"
        lines.append(f"- {camp} ({d}, model years {span}) {comp.title()}{' [safety-critical]' if sev else ''}: "
                     f"{(summ or '').strip()[:260]}")
    out.append(f"Recall campaigns on record ({len(seen)} distinct):")
    out.extend(lines[:40])
    if len(lines) > 40:
        out.append(f"- … and {len(lines) - 40} more campaigns")
    out.append("")
    return "\n".join(out)


def main():
    con = sqlite3.connect(DB)
    print(f"# Fact sheet — generated {date.today().isoformat()} from data/cars.sqlite (NHTSA complaints and recalls, EPA fuel economy)\n")
    for key in sys.argv[1:]:
        print(pack(con, key))


if __name__ == "__main__":
    main()
