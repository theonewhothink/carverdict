#!/usr/bin/env python3
"""canonicalize_models.py — turn raw vPIC model strings into the names people search for.

THE PROBLEM
-----------
NHTSA's vPIC catalogue lists a model per drivetrain, body and trim combination. Ingested
verbatim, "BMW 3 Series" arrives as six separate nameplates:

    bmw/330i          bmw/330i-sedan            bmw/330i-xdrive
    bmw/330i-xdrive-sedan   bmw/330i-xdrive-gran-turismo   bmw/330i-xdrive-sports-wagon

and Audi's Q5 as seven. Each one becomes its own URL, its own thin page and its own tiny
share of authority, and none of them is the phrase anyone types. Slug normalisation also
drifted, so bmw/x3-sdrive-28i and bmw/x3-sdrive28i both exist.

WHAT THIS DOES
--------------
Strips drivetrain, body-style and engine-code tokens, folds BMW/Mercedes engine-code
nameplates onto their series, merges the resulting duplicates (model years included) and
writes the old -> new URL map to data/model_redirects.json so the Worker can 301 them.

WHAT IT DELIBERATELY KEEPS
--------------------------
Powertrain is never merged. A Sorento Hybrid does not cost what a Sorento costs, and
telling a reader otherwise is the kind of error this whole site exists to avoid. Hybrid,
plug-in, EV and diesel variants stay separate nameplates.

Run:  python scripts/canonicalize_models.py [--dry-run]
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cars.sqlite"
MAP_OUT = ROOT / "data" / "model_redirects.json"

# Tokens that describe how a car is driven or bodied, not which car it is.
DRIVETRAIN = r"(?:xdrive|sdrive|quattro|4matic|4motion|awd|fwd|rwd|4wd|2wd|4x4|4x2)"
BODY = (r"(?:sedan|saloon|coupe|convertible|cabriolet|roadster|wagon|sports?[- ]wagon|estate|"
        r"gran[- ]turismo|gran[- ]coupe|sportback|avant|allroad|hatchback|liftback|"
        r"fastback|touring|crew[- ]cab|extended[- ]cab|regular[- ]cab|double[- ]cab|"
        r"king[- ]cab|quad[- ]cab|mega[- ]cab|access[- ]cab|super[- ]cab|supercrew|"
        r"long[- ]bed|short[- ]bed|passenger|cargo)"
        )
ENGINE = r"(?:tfsi|tsi|tdi|fsi|ecoboost|vvt|turbo|biturbo|twin[- ]turbo|v6|v8|v12|i4|i6)"
# "sport" is NOT in this list on purpose: Range Rover Sport, Outlander Sport and Discovery
# Sport are their own cars, and folding them into the base nameplate would merge two
# different vehicles' ownership costs into one page.
TRIM = r"(?:s[- ]line|m[- ]sport|amg[- ]line|premium|luxury|limited)"

# Powertrain words are protected: they change the ownership economics, so they stay.
PROTECT = re.compile(r"(hybrid|plug[- ]?in|phev|electric|\bev\b|diesel|e-?tron|prime|hev|bev)", re.I)

STRIP = re.compile(r"[-\s](?:%s|%s|%s|%s)(?=[-\s]|$)" % (DRIVETRAIN, BODY, ENGINE, TRIM), re.I)

# Engine-code nameplates that are really one series.
BMW_SERIES = re.compile(r"^([1-8])\d{2}[a-z]*$", re.I)
BMW_X = re.compile(r"^(x[1-7]|z[34]|i[3-8x])\b", re.I)
MB_CLASS = re.compile(r"^([a-z]{1,3})\s?(\d{2,3})[a-z]*$", re.I)
MB_LETTERS = {"a": "a-class", "b": "b-class", "c": "c-class", "e": "e-class", "s": "s-class",
              "cla": "cla", "cls": "cls", "gla": "gla", "glb": "glb", "glc": "glc",
              "gle": "gle", "gls": "gls", "slk": "slk", "slc": "slc", "sl": "sl"}


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", str(s).lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:60] or "x"


def canonical(make, name):
    """Return (canonical_name, canonical_slug) for a raw vPIC model string."""
    raw = re.sub(r"\s+", " ", str(name or "")).strip()
    raw = re.sub(r"[()\[\]]", " ", raw)            # "E350 (wagon)" is still an E-Class
    raw = re.sub(r"\s+", " ", raw).strip()
    protected = PROTECT.search(raw)
    work = PROTECT.sub("", raw).strip(" -")

    prev = None
    while prev != work:                      # tokens can chain: "xDrive28i Sports Wagon"
        prev = work
        work = STRIP.sub("", work).strip(" -")
    work = re.sub(r"\s{2,}", " ", work).strip(" -")

    mk = (make or "").lower()
    head = work.lower()
    if mk == "bmw":
        m = BMW_SERIES.match(head)
        if m:
            work = f"{m.group(1)} Series"
        else:
            m = BMW_X.match(head)
            if m:
                tail = head[m.end():].strip(" -")
                # the M cars are separate vehicles; M Performance trims (m40i, m50i) are not
                work = m.group(1).upper()
                if re.match(r"^m(\s+competition)?$", tail):
                    work += " M"
    elif mk in ("mercedes-benz", "mercedes"):
        m = MB_CLASS.match(head)
        if m and m.group(1).lower() in MB_LETTERS:
            work = MB_LETTERS[m.group(1).lower()].upper().replace("-CLASS", "-Class")

    if not work:
        work = raw
    if protected:
        word = protected.group(1).title().replace("Plug-In", "Plug-in").replace("Ev", "EV")
        if word.lower() not in work.lower():
            work = f"{work} {word}".strip()
    work = re.sub(r"\s+", " ", work).strip()
    return work, slugify(work)


def merge_year(con, keep_id, drop_id):
    """Fold one model-year record into another: complaints add, recalls de-duplicate."""
    seen = {r[0] for r in con.execute(
        "SELECT campaign FROM recalls WHERE my_id=?", (keep_id,))}
    for r in con.execute("SELECT id, campaign FROM recalls WHERE my_id=?", (drop_id,)).fetchall():
        if r[1] in seen:
            con.execute("DELETE FROM recalls WHERE id=?", (r[0],))
        else:
            seen.add(r[1])
            con.execute("UPDATE recalls SET my_id=? WHERE id=?", (keep_id, r[0]))
    # component counts add; verbatim quotes are kept up to a sensible ceiling
    for comp, n in con.execute(
            "SELECT component, SUM(count) FROM complaints WHERE my_id=? AND component!='__quote__'"
            " GROUP BY component", (drop_id,)).fetchall():
        row = con.execute("SELECT id, count FROM complaints WHERE my_id=? AND component=?",
                          (keep_id, comp)).fetchone()
        if row:
            con.execute("UPDATE complaints SET count=? WHERE id=?", ((row[1] or 0) + (n or 0), row[0]))
        else:
            con.execute("INSERT INTO complaints(my_id,component,count,sample) VALUES(?,?,?,NULL)",
                        (keep_id, comp, n or 0))
    kept_q = con.execute("SELECT COUNT(*) FROM complaints WHERE my_id=? AND component='__quote__'",
                         (keep_id,)).fetchone()[0]
    for qid, in con.execute("SELECT id FROM complaints WHERE my_id=? AND component='__quote__'",
                            (drop_id,)).fetchall():
        if kept_q < 6:
            con.execute("UPDATE complaints SET my_id=? WHERE id=?", (keep_id, qid))
            kept_q += 1
        else:
            con.execute("DELETE FROM complaints WHERE id=?", (qid,))
    a = con.execute("SELECT complaint_count, complaint_sample, is_ev FROM model_years WHERE id=?",
                    (keep_id,)).fetchone()
    b = con.execute("SELECT complaint_count, complaint_sample, is_ev FROM model_years WHERE id=?",
                    (drop_id,)).fetchone()
    con.execute("UPDATE model_years SET complaint_count=?, complaint_sample=?, is_ev=? WHERE id=?",
                ((a[0] or 0) + (b[0] or 0), (a[1] or 0) + (b[1] or 0),
                 1 if (a[2] or b[2]) else 0, keep_id))
    for t in ("fuel", "ev_extras"):
        if not con.execute(f"SELECT 1 FROM {t} WHERE my_id=?", (keep_id,)).fetchone():
            con.execute(f"UPDATE {t} SET my_id=? WHERE my_id=?", (keep_id, drop_id))
        else:
            con.execute(f"DELETE FROM {t} WHERE my_id=?", (drop_id,))
    con.execute("DELETE FROM computed_scores WHERE my_id=?", (drop_id,))
    con.execute("DELETE FROM complaints WHERE my_id=?", (drop_id,))
    con.execute("DELETE FROM recalls WHERE my_id=?", (drop_id,))
    con.execute("DELETE FROM model_years WHERE id=?", (drop_id,))
    n = con.execute("SELECT COUNT(*) FROM recalls WHERE my_id=?", (keep_id,)).fetchone()[0]
    sev = con.execute("SELECT COALESCE(SUM(severe),0) FROM recalls WHERE my_id=?",
                      (keep_id,)).fetchone()[0]
    con.execute("UPDATE model_years SET recall_count=?, severe_recalls=? WHERE id=?",
                (n, sev, keep_id))


def run(dry=False):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    models = [dict(r) for r in con.execute(
        "SELECT mo.id, mo.make_id, mo.name, mo.slug, mk.name make, mk.slug kslug "
        "FROM models mo JOIN makes mk ON mk.id=mo.make_id")]

    groups, redirects, changed = {}, {}, 0
    for m in models:
        cname, cslug = canonical(m["make"], m["name"])
        groups.setdefault((m["make_id"], cslug), []).append((m, cname))
        if cslug != m["slug"]:
            changed += 1
            redirects[f"/cars/{m['kslug']}/{m['slug']}/"] = f"/cars/{m['kslug']}/{cslug}/"

    merges = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"models={len(models)} renamed={changed} groups_merged={len(merges)} "
          f"models_after={len(groups)}")
    for (mkid, cslug), members in list(merges.items())[:12]:
        print("  ", cslug, "<-", ", ".join(sorted(x[0]["slug"] for x in members)))
    if dry:
        con.close()
        return 0

    for (mkid, cslug), members in groups.items():
        # keep the row with the most model-years, fold the rest into it
        def depth(x):
            return con.execute("SELECT COUNT(*) FROM model_years WHERE model_id=?",
                               (x[0]["id"],)).fetchone()[0]
        members = sorted(members, key=depth, reverse=True)
        keep, kname = members[0]
        # Fold the duplicates away FIRST: one of them may still be holding the canonical
        # slug, and (make_id, slug) is unique.
        for other, _ in members[1:]:
            for my in con.execute("SELECT id, year FROM model_years WHERE model_id=?",
                                  (other["id"],)).fetchall():
                clash = con.execute("SELECT id FROM model_years WHERE model_id=? AND year=?",
                                    (keep["id"], my["year"])).fetchone()
                if clash is None:
                    con.execute("UPDATE model_years SET model_id=? WHERE id=?", (keep["id"], my["id"]))
                    continue
                # Same car, two vPIC spellings: NHTSA answered each query separately, so the
                # records are additive, not duplicates. Sum them rather than throwing one away.
                merge_year(con, keep_id=clash["id"], drop_id=my["id"])
            con.execute("DELETE FROM models WHERE id=?", (other["id"],))
        con.execute("UPDATE models SET name=?, slug=? WHERE id=?", (kname, cslug, keep["id"]))
    con.commit()

    left = con.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    my_left = con.execute("SELECT COUNT(*) FROM model_years").fetchone()[0]
    con.close()

    # A renamed URL must keep its links and its search entries — forever, not just on the
    # build that renamed it. The map accumulates: once a URL has moved it stays redirected
    # even after the old vPIC spelling disappears from the dataset.
    redirects = {k: v for k, v in redirects.items() if k != v}
    try:
        prior = json.loads(MAP_OUT.read_text())
    except Exception:
        prior = {}
    prior.update(redirects)
    # follow chains, so an old URL never points at another redirect
    for k in list(prior):
        seen = set()
        v = prior[k]
        while v in prior and v not in seen:
            seen.add(v)
            v = prior[v]
        prior[k] = v
    prior = {k: v for k, v in prior.items() if k != v}
    MAP_OUT.write_text(json.dumps(prior, indent=0, sort_keys=True))
    redirects = prior
    print(f"CANONICAL OK: {left} models, {my_left} model-years, {len(redirects)} redirects written")
    return 0


if __name__ == "__main__":
    sys.exit(run("--dry-run" in sys.argv))
