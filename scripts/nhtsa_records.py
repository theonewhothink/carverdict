"""Match each NHTSA service independently; an unmatched lookup is never a zero.

Official model menus sometimes list RX 350 although the recall endpoint requires
RX350. Explicitly verified aliases are queried and their record IDs deduplicated.
No drivetrain, engine or trim is stripped to manufacture a match.
"""
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlencode

BASE = "https://api.nhtsa.gov"
ALIASES = {("LEXUS", "RX350", "complaints"): ["RX 350"],
           ("LEXUS", "RX350", "recalls"): ["RX350"]}


def identity(value):
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


@lru_cache(maxsize=2048)
def model_menu(url, getter):
    return getter(url)


def records(make, model, year, kind, getter):
    if kind not in ("complaints", "recalls"):
        raise ValueError("Unknown NHTSA service")
    checked = datetime.now(timezone.utc).isoformat()
    menu_url = BASE + "/products/vehicle/models?" + urlencode(
        {"make": make, "modelYear": year, "issueType": "r" if kind == "recalls" else "c"})
    menu = model_menu(menu_url, getter)
    source = {"status": "unavailable", "checked_at": checked,
              "menu_url": menu_url, "urls": [], "aliases": [], "results": [], "count": None}
    if not isinstance(menu, dict) or not isinstance(menu.get("results"), list):
        return source
    names = list(dict.fromkeys(str(r.get("model", "")) for r in menu["results"]
                             if identity(r.get("model")) == identity(model)))
    if not names:
        source["status"] = "unmatched"
        return source
    names = ALIASES.get((make.upper(), identity(model), kind), names)
    found = {}
    for name in names:
        url = BASE + f"/{kind}/{kind}ByVehicle?" + urlencode(
            {"make": make, "model": name, "modelYear": year})
        source["urls"].append(url)
        source["aliases"].append(name)
        response = getter(url)
        if not isinstance(response, dict) or not isinstance(response.get("results"), list):
            return source
        rows = response["results"]
        try:
            count = int(response.get("count", response.get("Count", len(rows))))
        except (TypeError, ValueError):
            return source
        if count != len(rows):
            source["status"] = "incomplete"
            return source
        for row in rows:
            key = row.get("NHTSACampaignNumber") if kind == "recalls" else row.get("odiNumber")
            if not key:
                source["status"] = "incomplete"
                return source
            found[str(key)] = row
    source.update(status="matched" if found else "empty", count=len(found), results=list(found.values()))
    return source


def record_check(con, my_id, kind, check):
    con.execute("""CREATE TABLE IF NOT EXISTS source_checks(
        my_id INTEGER, service TEXT, status TEXT, checked_at TEXT, urls TEXT,
        aliases TEXT, PRIMARY KEY(my_id,service))""")
    con.execute("INSERT OR REPLACE INTO source_checks VALUES(?,?,?,?,?,?)",
                (my_id, kind, check["status"], check["checked_at"],
                 json.dumps(check["urls"]), json.dumps(check["aliases"])))
