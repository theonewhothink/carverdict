#!/usr/bin/env python3
"""verify_dataset.py — refuse to publish a dataset that lost rows or grew duplicates.

Publishing a shrunken database is worse than publishing nothing: the next deploy would
silently drop the pages it can no longer support, and Search Console would read that as
mass deletion. Exits non-zero on anything suspicious.
"""
import sqlite3, sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "cars.sqlite"
FLOOR = int(sys.argv[1]) if len(sys.argv) > 1 else 10


def main():
    con = sqlite3.connect(DB)
    con.execute("VACUUM")
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM model_years").fetchone()[0]
    dupes = con.execute("""SELECT COUNT(*) FROM (SELECT model_id, year FROM model_years
                           GROUP BY model_id, year HAVING COUNT(*) > 1)""").fetchone()[0]
    orphan_c = con.execute("""SELECT COUNT(*) FROM complaints
                              WHERE my_id NOT IN (SELECT id FROM model_years)""").fetchone()[0]
    orphan_r = con.execute("""SELECT COUNT(*) FROM recalls
                              WHERE my_id NOT IN (SELECT id FROM model_years)""").fetchone()[0]
    size = DB.stat().st_size / 1e6
    con.close()
    print(f"model_years={n} duplicate_keys={dupes} orphan_complaints={orphan_c} "
          f"orphan_recalls={orphan_r} size={size:.1f}MB")
    bad = []
    if n < FLOOR:
        bad.append(f"only {n} model-years, floor is {FLOOR}")
    if dupes:
        bad.append(f"{dupes} duplicate (model, year) keys")
    if orphan_c or orphan_r:
        bad.append(f"{orphan_c + orphan_r} orphaned child rows")
    if bad:
        print("DATASET REJECTED: " + "; ".join(bad))
        return 1
    print("dataset OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
