#!/usr/bin/env python3
"""score_model_years.py — recompute reliability scores, verdicts and cost curves.

WHY THIS EXISTS
---------------
The first scoring pass used raw NHTSA complaint counts divided by years of exposure.
Complaint counts scale with how many cars were sold, not with how good the car is, so a
nameplate selling 350,000 units a year was punished for its own popularity: the 2018
Toyota Camry scored 5/100 (AVOID) while low-volume luxury models scored BUY. A verdict
engine that inverts the real ranking is worse than no verdict engine.

There is no free, complete dataset of US sales or registrations per model-year, so the fix
is not "divide by volume" — it is to score on quantities that do not depend on volume:

  1. WITHIN-MODEL RATE (the main term, volume-free by construction).
     A model's sales volume is roughly constant across its years, so comparing a
     model-year's complaint rate against the median rate of *that same nameplate* cancels
     volume out almost entirely. This is also exactly the question the site promises to
     answer: which years of this car are the traps?

  2. EMPIRICAL-BAYES SHRINKAGE.
     A year with 6 complaints is not evidence of a great car; it is an absence of evidence.
     The within-model ratio is shrunk toward 1.0 (neutral) with weight n/(n+K), so thin
     years land near the model's own norm instead of at a perfect score.

  3. CROSS-MODEL RATE (damped).
     A small term keeps a genuinely complaint-heavy nameplate from scoring well just
     because all of its years are equally bad. It is computed on a log scale and capped at
     12 points precisely because it is the one term volume still leaks into.

  4. RECALLS (volume-free).
     A recall campaign is issued per defect, not per car sold, so recall counts are
     directly comparable across models. Severe campaigns — fire, crash, injury, stall,
     brake or steering loss — carry more weight than the rest.

Every term is bounded, so the floor is 20/100: no car is ever branded with a number that
implies a total failure the data cannot support.

Run standalone (idempotent):  python scripts/score_model_years.py [path/to/cars.sqlite]
"""
import bisect
import collections
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cars.sqlite"
CURRENT_YEAR = 2026

# --- tunables (published on /methodology/) ---------------------------------
W_WITHIN = 42.0     # max penalty from the within-model complaint rate
W_CROSS = 12.0      # max penalty from the cross-model complaint rate (damped: volume leaks here)
W_SEVERE = 3.0      # penalty per safety-critical recall campaign
CAP_SEVERE = 18.0
W_RECALL = 1.0      # penalty per other recall campaign
CAP_RECALL = 8.0
SHRINK_K = 40.0     # complaints needed before a year is judged mostly on its own evidence
REL_FLOOR = 0.75    # ratio at or below which the complaint penalty is zero
REL_SPAN = 1.55     # ratio span from floor to full penalty

BUY, CAUTION = 70, 50           # verdict thresholds
CONF_HIGH, CONF_MED = 150, 50   # complaint counts backing a HIGH / MEDIUM confidence label


def _percentile_fn(values):
    pool = sorted(values)
    n = len(pool)
    if not n:
        return lambda x: 0.0
    return lambda x: bisect.bisect_left(pool, x) / n


def compute(con):
    """Recompute computed_scores for every model_year row. Returns a summary dict."""
    rows = [
        dict(id=r[0], model_id=r[1], year=r[2], cc=r[3] or 0, rc=r[4] or 0, sev=r[5] or 0)
        for r in con.execute(
            "SELECT id, model_id, year, complaint_count, recall_count, severe_recalls "
            "FROM model_years")
    ]
    for r in rows:
        r["age"] = max(1, CURRENT_YEAR - (r["year"] or CURRENT_YEAR))
        r["cpy"] = r["cc"] / r["age"]

    # 1. the model's own normal complaint rate, from its years that actually have data
    by_model = collections.defaultdict(list)
    for r in rows:
        if r["cc"] > 0:
            by_model[r["model_id"]].append(r["cpy"])
    model_median = {k: statistics.median(v) for k, v in by_model.items()}

    # 3. the cross-model distribution, on a log scale so volume differences compress
    pct = _percentile_fn(math.log10(1 + r["cpy"]) for r in rows if r["cc"] > 0)

    out = []
    for r in rows:
        base = model_median.get(r["model_id"]) or r["cpy"] or 1.0
        rel = (r["cpy"] / base) if base > 0 else 1.0
        weight = r["cc"] / (r["cc"] + SHRINK_K)              # 2. shrinkage
        rel_shrunk = 1.0 + (rel - 1.0) * weight

        p_within = W_WITHIN * max(0.0, min(1.0, (rel_shrunk - REL_FLOOR) / REL_SPAN))
        p_cross = W_CROSS * pct(math.log10(1 + r["cpy"]))
        p_severe = min(CAP_SEVERE, r["sev"] * W_SEVERE)
        p_recall = min(CAP_RECALL, max(0, r["rc"] - r["sev"]) * W_RECALL)

        score = int(max(1, min(100, round(100 - p_within - p_cross - p_severe - p_recall))))
        verdict = "BUY" if score >= BUY else ("CAUTION" if score >= CAUTION else "AVOID")
        confidence = ("high" if r["cc"] >= CONF_HIGH else
                      "medium" if r["cc"] >= CONF_MED else "low")

        # No complaints AND no recalls is an empty record, not a clean one. Publishing 93/100
        # BUY for a car nobody has reported on yet is the single most misleading thing this
        # table could do, so it says so instead.
        if r["cc"] == 0 and r["rc"] == 0:
            score, verdict, confidence = None, "DATA PENDING", "none"

        peer = "in line with" if 0.85 <= rel <= 1.2 else ("worse than" if rel > 1.2 else "better than")
        if verdict == "DATA PENDING":
            out.append((r["id"], None, verdict,
                        json.dumps(["No NHTSA complaints or recall campaigns on record for this "
                                    "model year yet — no verdict is computed from an empty record"]),
                        json.dumps([{"age": a, "total_low": 260 + a * 95, "total_high": 520 + a * 185}
                                    for a in range(0, 16)]),
                        0.0, confidence))
            continue
        reasons = [
            f"{r['cc']} NHTSA complaints on record ({r['cpy']:.1f}/yr of exposure) — "
            f"{peer} a typical year of this model ({base:.1f}/yr)",
            f"{r['rc']} recall campaigns, {r['sev']} touching safety-critical systems",
        ]
        if confidence == "low":
            reasons.append("Thin complaint record — this score is held close to the model's "
                           "own average rather than read as evidence of quality")

        # running-cost curve: fuel/energy is added by the page generator from EPA data;
        # this is the maintenance-and-repair band by age, in USD, before geo re-pricing.
        curve = [{"age": a,
                  "total_low": 260 + a * 95 + int(r["cpy"] * 12),
                  "total_high": 520 + a * 185 + int(r["cpy"] * 26)} for a in range(0, 16)]

        out.append((r["id"], score, verdict, json.dumps(reasons), json.dumps(curve),
                    round(r["cpy"], 2), confidence))

    con.execute("""CREATE TABLE IF NOT EXISTS computed_scores(my_id INT PRIMARY KEY,
        reliability_score INT, verdict TEXT, reasons TEXT, cost_curve TEXT,
        complaints_per_year REAL)""")
    cols = {c[1] for c in con.execute("PRAGMA table_info(computed_scores)")}
    if "confidence" not in cols:
        con.execute("ALTER TABLE computed_scores ADD COLUMN confidence TEXT")
    con.executemany(
        "INSERT OR REPLACE INTO computed_scores"
        "(my_id,reliability_score,verdict,reasons,cost_curve,complaints_per_year,confidence)"
        " VALUES(?,?,?,?,?,?,?)", out)
    con.commit()

    dist = collections.Counter(o[2] for o in out)
    return {"scored": len(out), "BUY": dist["BUY"], "CAUTION": dist["CAUTION"],
            "AVOID": dist["AVOID"]}


def main(path=None):
    import sqlite3
    db = Path(path) if path else DB
    con = sqlite3.connect(db)
    s = compute(con)
    con.close()
    print(f"SCORES OK: {s['scored']} model-years — "
          f"BUY {s['BUY']} · CAUTION {s['CAUTION']} · AVOID {s['AVOID']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
