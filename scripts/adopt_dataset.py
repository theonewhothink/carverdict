#!/usr/bin/env python3
"""adopt_dataset.py — replace data/cars.sqlite with a candidate, but only if it is bigger.

Used by the nightly ingest workflow (adopt the published dataset before extending it) and
available to any build step that wants the same guard. A candidate that is missing,
unreadable or smaller than what is already committed is ignored: coverage must never go
backwards, because the site sheds pages when it does.
"""
import shutil, sqlite3, sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "data" / "cars.sqlite"


def rows(p):
    try:
        con = sqlite3.connect(p)
        n = con.execute("SELECT COUNT(*) FROM model_years").fetchone()[0]
        con.close()
        return n
    except Exception:
        return -1


def main(candidate):
    cand = Path(candidate)
    if not cand.exists():
        print(f"adopt: no candidate at {cand}; keeping {rows(TARGET)} model-years")
        return 0
    new, cur = rows(cand), rows(TARGET)
    if new > cur:
        shutil.copy2(cand, TARGET)
        print(f"adopt: using candidate - {new} model-years (was {cur})")
    else:
        print(f"adopt: keeping current - {cur} model-years (candidate had {new})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/cars.sqlite"))
