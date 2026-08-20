#!/usr/bin/env python3
"""extract_library.py — pull the embedded catalogue out of the nightly dataset.

The deep harvest runs nightly with hours of budget and embeds its merged
car_library.json into cars.sqlite (site_kv / car_library_json). This build-time
step extracts it, and adopts it only when it is BIGGER than the committed
catalogue — coverage never goes backwards. Missing table or key is normal on
older datasets and is not an error.
"""
import json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "data" / "car_library.json"
DB = ROOT / "data" / "cars.sqlite"


def main():
    try:
        con = sqlite3.connect(DB)
        row = con.execute("SELECT v FROM site_kv WHERE k='car_library_json'").fetchone()
        con.close()
    except Exception:
        print("extract: dataset carries no embedded catalogue yet")
        return 0
    if not row:
        print("extract: dataset carries no embedded catalogue yet")
        return 0
    try:
        embedded = json.loads(row[0])
    except Exception as e:
        print(f"extract: embedded catalogue unreadable ({e}); keeping committed")
        return 0
    committed = json.loads(LIB.read_text()) if LIB.exists() else []
    if len(embedded) > len(committed):
        LIB.write_text(json.dumps(embedded, separators=(",", ":"), ensure_ascii=False))
        print(f"extract: adopted embedded catalogue - {len(embedded)} models (was {len(committed)})")
    else:
        print(f"extract: keeping committed catalogue - {len(committed)} models (embedded had {len(embedded)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
