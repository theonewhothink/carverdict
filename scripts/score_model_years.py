#!/usr/bin/env python3
"""Keep legacy schema compatible without publishing unvalidated reliability ratings.

Complaint totals have no comparable sales/usage denominator. Campaign counts do
not establish failure probability. No BUY/AVOID label or numeric reliability score
is therefore computed. The maintenance curve is an explicitly generic planning
assumption; the buying brief uses inputs supplied by the reader instead.
"""
import json
import sqlite3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cars.sqlite"
CURRENT_YEAR = 2026


def compute(con):
    con.execute("""CREATE TABLE IF NOT EXISTS computed_scores(my_id INT PRIMARY KEY,
        reliability_score INT, verdict TEXT, reasons TEXT, cost_curve TEXT,
        complaints_per_year REAL)""")
    if "confidence" not in {r[1] for r in con.execute("PRAGMA table_info(computed_scores)")}:
        con.execute("ALTER TABLE computed_scores ADD COLUMN confidence TEXT")
    curve = json.dumps([{"age": a, "total_low": 260 + a * 95,
                         "total_high": 520 + a * 185} for a in range(16)])
    reason = json.dumps(["Public safety records are not a reliability prediction or a buying verdict.",
                         "Check the individual VIN and arrange an independent inspection."])
    rows = [(r[0], None, "RECORD ONLY", reason, curve, None, None)
            for r in con.execute("SELECT id FROM model_years")]
    con.executemany("""INSERT OR REPLACE INTO computed_scores
        (my_id,reliability_score,verdict,reasons,cost_curve,complaints_per_year,confidence)
        VALUES(?,?,?,?,?,?,?)""", rows)
    con.commit()
    return {"scored": len(rows), "BUY": 0, "CAUTION": 0, "AVOID": 0}


def main(path=None):
    con = sqlite3.connect(Path(path) if path else DB)
    result = compute(con)
    con.close()
    print(f"RECORDS: {result['scored']} model-years; predictive ratings suspended")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
