#!/usr/bin/env python3
"""fill_fuel.py — no model-year is published without a fuel or energy figure.

EPA's menu API lists "CR-V AWD" where the plan stored "CR-V", so 1,173 of 5,296 model-years
had no fuel row and every generator rendered "fuel unavailable" with a five-year total that
was silently short by six to twelve thousand dollars. The ingest is fixed (fetch_epa in
ingest_scale.py) and refreshes those rows first, but the fleet is refreshed at 150 a night;
this fills the gap deterministically at build time, in the database, so every generator
(model-year pages, cards, search index, calculators, library rollups) reads one number.

Precedence, recorded in fuel.fuel_type so pages can label it:
  1. EPA record for the exact model-year               fuel_type = EPA's own string
  2. nearest EPA-covered year of the same nameplate    fuel_type = "est-adjacent:<year>"
     (within six model years; economy drifts a few MPG between facelifts, not more)
  3. segment mean from this dataset's own EPA rows     fuel_type = "est-segment"
     (electric cars: mean EPA energy cost of the EVs on record)
Estimated rows are re-derived on every build and replaced the moment EPA data arrives.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cars.sqlite"

FALLBACK = {  # used only when the dataset has too few EPA rows in a segment to average
    "economy": 1500, "compact": 1650, "midsize": 1800, "fullsize": 2200,
    "compact_suv": 1900, "midsize_suv": 2250, "fullsize_suv": 2900, "pickup": 2800,
    "minivan": 2300, "sports": 2400, "sports_luxury": 2700, "luxury_compact": 2100,
    "luxury_midsize": 2300, "luxury_large": 2700, "exotic": 3300,
}
EV_FALLBACK = 650


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    have_pe = con.execute("SELECT 1 FROM sqlite_master WHERE name='price_estimates'").fetchone()
    # Drop last build's estimates so a fresh EPA row is never shadowed by a stale guess.
    con.execute("DELETE FROM fuel WHERE fuel_type LIKE 'est-%'")

    rows = con.execute(f"""
        SELECT my.id, my.model_id, my.year, my.is_ev,
               f.annual_fuel_cost, f.mpg_comb, f.mpg_city, f.mpg_hwy, f.fuel_type, f.ev_range, f.kwh_100mi
               {', pe.segment' if have_pe else ", NULL AS segment"}
        FROM model_years my
        LEFT JOIN fuel f ON f.my_id = my.id
        {'LEFT JOIN price_estimates pe ON pe.my_id = my.id' if have_pe else ''}
        ORDER BY my.model_id, my.year""").fetchall()

    # Segment means from real EPA rows.
    seg_sum, seg_n, ev_sum, ev_n = {}, {}, 0, 0
    for r in rows:
        if r["annual_fuel_cost"]:
            if r["is_ev"]:
                if (r["fuel_type"] or "") == "Electricity":   # battery-electric only, not plug-in hybrids
                    ev_sum += r["annual_fuel_cost"]; ev_n += 1
            elif r["segment"]:
                seg_sum[r["segment"]] = seg_sum.get(r["segment"], 0) + r["annual_fuel_cost"]
                seg_n[r["segment"]] = seg_n.get(r["segment"], 0) + 1
    seg_mean = {s: int(round(seg_sum[s] / seg_n[s], -1)) for s in seg_sum if seg_n[s] >= 10}
    ev_mean = int(round(ev_sum / ev_n, -1)) if ev_n >= 10 else EV_FALLBACK

    by_model = {}
    for r in rows:
        by_model.setdefault(r["model_id"], []).append(r)

    adjacent = segment = 0
    for group in by_model.values():
        real = [x for x in group if x["annual_fuel_cost"]]
        for r in group:
            if r["annual_fuel_cost"]:
                continue
            near = min(real, key=lambda x: abs(x["year"] - r["year"]), default=None)
            if near and abs(near["year"] - r["year"]) <= 6:
                con.execute("""INSERT OR REPLACE INTO fuel
                    (my_id, fuel_type, mpg_city, mpg_hwy, mpg_comb, annual_fuel_cost, ev_range, kwh_100mi)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (r["id"], f"est-adjacent:{near['year']}", near["mpg_city"], near["mpg_hwy"],
                     near["mpg_comb"], near["annual_fuel_cost"], near["ev_range"], near["kwh_100mi"]))
                adjacent += 1
            else:
                cost = ev_mean if r["is_ev"] else seg_mean.get(r["segment"]) or FALLBACK.get(r["segment"] or "", 1900)
                con.execute("""INSERT OR REPLACE INTO fuel
                    (my_id, fuel_type, mpg_city, mpg_hwy, mpg_comb, annual_fuel_cost, ev_range, kwh_100mi)
                    VALUES (?,?,NULL,NULL,NULL,?,NULL,NULL)""", (r["id"], "est-segment", cost))
                segment += 1
    con.commit()
    total = len(rows)
    real_n = sum(1 for r in rows if r["annual_fuel_cost"])
    print(f"FUEL OK: {total} model-years — EPA {real_n}, estimated from adjacent year {adjacent}, "
          f"from segment mean {segment}; segment means {seg_mean}, EV mean {ev_mean}")


if __name__ == "__main__":
    main()
