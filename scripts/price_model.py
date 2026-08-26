#!/usr/bin/env python3
"""price_model.py — the ownership-price layer.

WHY THIS EXISTS
---------------
The site answered "what will this car cost to run" and refused to answer the question every
buyer actually asks first: "what does it cost, and what will I lose on it?" Fuel and a
maintenance band are the small money. Purchase price and depreciation are the large money —
on a five-year hold, depreciation is normally the single biggest line, larger than fuel,
maintenance and insurance combined. A cost site without them is not a cost site.

WHAT IT CAN AND CANNOT KNOW
---------------------------
There is no free, complete, per-model-year price dataset. NHTSA carries safety, EPA carries
economy; neither carries money. So this layer does not pretend to know one car's price. It
computes a CLASS-LEVEL band from published series, in four steps, all of them published on
/methodology/ and all of them labeled as estimates on the page:

  1. ORIGINAL PRICE. The US average new-vehicle transaction price for that model year
     (Cox Automotive / Kelley Blue Book annual means) multiplied by the model's segment
     multiplier, its brand tier and — for a battery-electric car — that year's EV premium.
     Where Wikipedia's infobox carries an explicit MSRP for the nameplate, that real figure
     anchors the estimate instead, and the page says so.

  2. VALUE TODAY. Original price times the retained-value curve at the car's age, with a
     steeper curve for used EVs (battery-warranty runout, fast model turnover) and a floor,
     because a running car is never worth nothing.

  3. VALUE IN FIVE YEARS, and therefore the depreciation the next owner actually pays.

  4. INSURANCE. National average full-coverage premium for the segment, relieved by age
     because full coverage tracks the value at risk, then re-priced per country by the
     ins_idx column already in data/geo_prices.json.

Everything lands in a `price_estimates` table and is recomputed on every build, so a change
to the model reaches production with the next deploy.

Run standalone (idempotent):  python scripts/price_model.py [path/to/cars.sqlite]
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cars.sqlite"
CONST = json.loads((ROOT / "data" / "price_model.json").read_text())
CURRENT_YEAR = 2026
BAND = 0.18  # +/- around the central estimate; roughly the IQR of real listings

ATP = {int(k): v for k, v in CONST["atp_by_year"].items()}
RETAIN = {int(k): v for k, v in CONST["retained_value"].items()}
EV_PEN = {int(k): v for k, v in CONST["ev_retention_penalty"].items() if k.isdigit()}
INS_RELIEF = {int(k): v for k, v in CONST["insurance_age_relief"].items() if k.isdigit()}
EV_PREM = {int(k): v for k, v in CONST["ev_price_premium"].items() if k.isdigit()}
SEG_MULT = CONST["segment_multiplier"]
SEG_RET = {k: v for k, v in CONST["segment_retention"].items() if not k.startswith("_")}
RET_CEIL = CONST["retained_value_ceiling"]
SEG_KW = CONST["segment_keywords"]
KEYWORDS = sorted(((w, s) for s, ws in SEG_KW.items() for w in ws),
                  key=lambda x: -len(x[0]))
LUX_MAP = CONST["luxury_map"]
INS = CONST["insurance_annual_usd"]
MPG_FALLBACK = sorted(((int(k), v) for k, v in CONST["segment_fallback_by_mpg"].items()
                       if k.isdigit()), reverse=True)
TIER = {b: tier for tier, brands in CONST["brand_tier"].items() for b in brands}


def interp(table, x):
    """Linear interpolation over a sparse integer-keyed table, flat outside its range."""
    keys = sorted(table)
    if x <= keys[0]:
        return table[keys[0]]
    if x >= keys[-1]:
        return table[keys[-1]]
    for a, b in zip(keys, keys[1:]):
        if a <= x <= b:
            f = (x - a) / (b - a)
            return table[a] + f * (table[b] - table[a])
    return table[keys[-1]]


def brand_tier(make):
    return TIER.get((make or "").strip().lower(), "mainstream")


def segment(make, model, mpg_comb, is_ev):
    """Placement rule, published on /methodology/: an explicit nameplate keyword wins;
    otherwise EPA combined economy is the size proxy; then the brand tier re-reads the
    segment upward for a luxury or exotic marque."""
    name = f"{make} {model}".lower()
    mlow = (model or "").lower()
    seg = None
    # Longest keyword first: "outlander sport" must beat "outlander", or every compact
    # SUV whose name contains a mid-size nameplate is priced as the bigger car.
    for w, s in KEYWORDS:
        pat = r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])"
        if re.search(pat, mlow) or re.search(pat, name):
            seg = s
            break
    if not seg:
        if is_ev:
            # EPA economy is in MPGe for an EV and is not a size proxy there.
            seg = "compact_suv"
        elif not mpg_comb:
            # No EPA record. The MPG ladder's bottom rung is "full-size SUV", so a missing
            # figure used to read as a Suburban and priced a 2013 Outlander Sport at
            # $22,000. An absent measurement is not a large car; it is no information, so
            # the fleet middle is the only honest default.
            seg = "midsize"
        else:
            m = mpg_comb
            seg = "midsize"
            for thr, s in MPG_FALLBACK:
                if m >= thr:
                    seg = s
                    break
    tier = brand_tier(make)
    if tier in ("luxury", "exotic"):
        seg = LUX_MAP.get(seg, seg)
        if tier == "exotic":
            seg = "exotic"
    return seg, tier


_WIKI = None


def wiki_msrp(make, model):
    """Real MSRP where Wikipedia's infobox carries one. Optional: the harvest writes
    data/wiki_specs.json during the build and the file simply may not exist."""
    global _WIKI
    if _WIKI is None:
        f = ROOT / "data" / "wiki_specs.json"
        try:
            raw = json.loads(f.read_text())
        except Exception:
            raw = {}
        _WIKI = {}
        for k, v in (raw.items() if isinstance(raw, dict) else []):
            if isinstance(v, dict) and v.get("msrp"):
                _WIKI[str(k).strip().lower()] = v["msrp"]
    for key in (f"{make} {model}".strip().lower(), (model or "").strip().lower()):
        val = _WIKI.get(key)
        if not val:
            continue
        nums = [int(x.replace(",", "")) for x in re.findall(r"\$\s?([\d,]{4,9})", str(val))]
        nums = [n for n in nums if 3000 <= n <= 3000000]
        if nums:
            return sum(nums) / len(nums)
    return None


def equivalent_new_today(seg, tier, is_ev, year):
    """What this car's segment costs NEW today, in today's money. Everything else is
    derived from this number, because a used market prices in today's dollars — pricing a
    2015 car off a 2015 dollar figure is what makes model-based valuations read low."""
    p = interp(ATP, CURRENT_YEAR) * SEG_MULT.get(seg, 1.0)
    if tier == "mainstream_plus":
        p *= 1.08
    if is_ev:
        p *= interp(EV_PREM, year)
    return p


def price_new(make, model, year, seg, tier, is_ev):
    """Transaction price when the car was new, in the nominal dollars of that model year:
    today's equivalent walked back with the ATP series. A published MSRP wins where one
    exists."""
    real = wiki_msrp(make, model)
    if real:
        return real, "wikipedia"
    today = equivalent_new_today(seg, tier, is_ev, year)
    return today * interp(ATP, year) / interp(ATP, CURRENT_YEAR), "segment"


def retained(age, is_ev, seg):
    r = interp(RETAIN, max(0, age)) * SEG_RET.get(seg, 1.0)
    if is_ev and age >= 3:
        r *= interp(EV_PEN, age)
    return min(RET_CEIL, r)


USED_IDX = CONST.get("used_market_index", 1.0)


def value_at(new_today, age, is_ev, seg):
    return max(CONST["retained_value_floor_usd"],
               new_today * retained(age, is_ev, seg) * USED_IDX)


def band(x):
    return int(round(x * (1 - BAND), -2)), int(round(x * (1 + BAND), -2))


def compute(con):
    rows = con.execute("""
        SELECT my.id, my.year, my.is_ev, mo.name model, mk.name make, f.mpg_comb
        FROM model_years my
        JOIN models mo ON mo.id = my.model_id
        JOIN makes mk ON mk.id = mo.make_id
        LEFT JOIN fuel f ON f.my_id = my.id
    """).fetchall()

    out = []
    for my_id, year, is_ev, model, make, mpg in rows:
        year = int(year or CURRENT_YEAR)
        is_ev = bool(is_ev)
        age = max(0, CURRENT_YEAR - year)
        seg, tier = segment(make, model, mpg, is_ev)
        p0, anchor = price_new(make, model, year, seg, tier, is_ev)
        # The value walk runs off the equivalent-new-today price, not off p0, so a
        # 2015 car is measured against the 2026 market it is actually sold in.
        new_today = equivalent_new_today(seg, tier, is_ev, year)
        if anchor == "wikipedia":
            # A published MSRP is in its own year's dollars; bring it forward before it
            # anchors a present-day valuation.
            new_today = p0 * interp(ATP, CURRENT_YEAR) / interp(ATP, year)
        now = value_at(new_today, age, is_ev, seg)
        in5 = value_at(new_today, age + 5, is_ev, seg)
        dep5 = max(0.0, now - in5)

        ins_lo, ins_hi = INS.get(seg, INS["midsize"])
        relief = interp(INS_RELIEF, age)
        ins_lo, ins_hi = ins_lo * relief, ins_hi * relief

        nl, nh = band(p0)
        tl, th = band(now)
        fl, fh = band(in5)
        out.append((
            my_id, seg, tier, anchor,
            int(round(p0, -2)), nl, nh,
            int(round(now, -2)), tl, th,
            int(round(in5, -2)), fl, fh,
            int(round(dep5, -2)), int(round(dep5 / 5, -1)),
            int(round(ins_lo, -1)), int(round(ins_hi, -1)),
        ))

    con.execute("""CREATE TABLE IF NOT EXISTS price_estimates(
        my_id INT PRIMARY KEY, segment TEXT, brand_tier TEXT, anchor TEXT,
        price_new INT, price_new_low INT, price_new_high INT,
        price_today INT, price_today_low INT, price_today_high INT,
        price_in5 INT, price_in5_low INT, price_in5_high INT,
        depreciation_5y INT, depreciation_per_year INT,
        insurance_low INT, insurance_high INT)""")
    con.executemany("INSERT OR REPLACE INTO price_estimates VALUES(" + ",".join("?" * 17) + ")", out)
    con.commit()
    return out


def main(path=None):
    con = sqlite3.connect(Path(path) if path else DB)
    out = compute(con)
    segs = {}
    anchors = {}
    for r in out:
        segs[r[1]] = segs.get(r[1], 0) + 1
        anchors[r[3]] = anchors.get(r[3], 0) + 1
    con.close()
    top = ", ".join(f"{k} {v}" for k, v in sorted(segs.items(), key=lambda x: -x[1])[:6])
    print(f"PRICES OK: {len(out)} model-years priced — {top}"
          f" · anchored on a published MSRP: {anchors.get('wikipedia', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
