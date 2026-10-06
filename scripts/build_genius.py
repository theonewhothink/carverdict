#!/usr/bin/env python3
"""build_genius.py — the knowledge Car Genius answers from, and its /ask/ page.

Car Genius is the site's chat assistant (workers/genius.mjs). It never answers from memory:
every fact it states comes from a tool call over the files this script writes, and every
link it gives is one of the URLs these files carry. So the rule here is the site's own
rule — data or nothing — applied to the index: a URL enters only when its page exists in
site/, and every figure is the one the page itself prints.

  site/assets/genius-cars.json    one row per model-year: verdict, score, complaints, top
                                  failure areas, recalls, fuel, price estimates, page URL
  site/assets/genius-guides.json  the signed guides as plain text, with their URLs
  site/assets/genius-pages.json   title, description and URL of every other English page
                                  (comparisons, stories, problems, superlatives, hubs)
  site/ask/index.html             the full-page Car Genius

Runs after every generator that writes pages and before localize.py, so every page Car
Genius may link to is already on disk. /ask/ is noindex: it is an app screen, not content.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gen_site  # noqa: E402
import build_guides  # noqa: E402

SITE = ROOT / "site"
ASSETS = SITE / "assets"
DB = ROOT / "data" / "cars.sqlite"
LANGS = ("pt", "es", "fr", "de", "he")
SKIP_PREFIX = ("/assets/", "/studio/", "/account/", "/login/", "/garage/", "/notify/", "/og/", "/ask/")

RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
RE_DESC = re.compile(r'<meta name="description" content="(.*?)"', re.S)


def exists(url):
    return (SITE / url.strip("/") / "index.html").exists()


def unesc(s):
    import html
    return html.unescape(re.sub(r"\s+", " ", s or "")).strip()


def cars(con):
    con.row_factory = sqlite3.Row
    rows = gen_site.rows_all(con)
    top = {}
    for r in con.execute("SELECT my_id, component, count FROM complaints ORDER BY my_id, count DESC"):
        lst = top.setdefault(r["my_id"], [])
        if len(lst) < 3 and r["component"]:
            lst.append([r["component"].title(), r["count"]])
    rec = {}
    for r in con.execute("SELECT my_id, component, severe FROM recalls ORDER BY my_id, severe DESC"):
        lst = rec.setdefault(r["my_id"], [])
        comp = (r["component"] or "").split(":")[0].title()
        if comp and comp not in lst and len(lst) < 3:
            lst.append(comp)
    out = []
    checked = {(r["my_id"], r["service"]): r["status"] for r in con.execute("SELECT * FROM source_checks")}
    for r in rows:
        if any(checked.get((r["my_id"], kind)) not in ("matched", "empty") for kind in ("complaints", "recalls")):
            continue
        year_url = gen_site.url_my(r)
        model_url = f"/cars/{r['kslug']}/{r['mslug']}/"
        try:
            reasons = json.loads(r["reasons"] or "[]")[:2]
        except ValueError:
            reasons = []
        row = {
            "make": r["make"], "model": r["model"], "year": r["year"],
            "url": year_url if exists(year_url) else (model_url if exists(model_url) else None),
            "verdict": r["verdict"], "score": r["score"], "confidence": r.get("confidence"),
            "complaints": r["complaint_count"] or 0, "recalls": r["recall_count"] or 0,
            "top_complaints": top.get(r["my_id"], []), "recall_areas": rec.get(r["my_id"], []),
            "why": reasons,
        }
        if r.get("is_ev"):
            row["ev"] = True
            if r.get("ev_range"):
                row["ev_range_mi"] = r["ev_range"]
        if r.get("mpg_comb"):
            row["mpg"] = r["mpg_comb"]
            row["fuel_estimated"] = str(r.get("fuel_type") or "").startswith("est")
        if r.get("annual_fuel_cost"):
            row["fuel_cost_usd_year"] = r["annual_fuel_cost"]
        if r.get("segment"):
            row["segment"] = r["segment"]
        row['scope'] = 'US model-level; complaint counts are not failure rates; VIN applicability and remedy completion are not established.'
        out.append({k: v for k, v in row.items() if v not in (None, [], "")})
    return out


def guides():
    out = []
    for f in sorted((ROOT / "data" / "guides").glob("*.md")):
        meta, body = build_guides.parse(f.read_text())
        if not meta.get("source_review"):
            continue
        url = f"/guides/{meta['slug']}/"
        if not exists(url):
            continue
        text = re.sub(r"\{\{.*?\}\}", "", body)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\*\*?|^#+\s*", "", text, flags=re.M)
        out.append({"slug": meta["slug"], "title": meta.get("title", ""), "url": url,
                    "date": meta.get("date", ""), "description": meta.get("description", ""),
                    "models": meta["models"], "text": re.sub(r"\n{3,}", "\n\n", text).strip()})
    return out


def pages():
    out = []
    reviewed = set(json.loads((ROOT / 'data' / 'publication_policy.json').read_text()).get('index_pages', []))
    for p in sorted(SITE.rglob("index.html")):
        url = "/" + str(p.parent.relative_to(SITE)).replace("\\", "/").strip(".") + "/"
        url = url.replace("//", "/")
        first = url.strip("/").split("/")[0]
        if first in LANGS or url.startswith(SKIP_PREFIX):
            continue
        # model-year and library model pages are covered, with their data, by the cars
        # index; listing them twice only dilutes the search
        if re.match(r"^/cars/[^/]+/[^/]+/\d{4}/$", url) or re.match(r"^/library/[^/]+/[^/]+/$", url):
            continue
        if url not in reviewed:
            continue
        s = p.read_text(encoding="utf-8", errors="ignore")[:6000]
        t, d = RE_TITLE.search(s), RE_DESC.search(s)
        if not t:
            continue
        out.append({"url": url, "title": unesc(t.group(1)).replace(" | MotorJury", "").replace(" — MotorJury", ""),
                    "description": unesc(d.group(1)) if d else ""})
    return out


ASK_BODY = """<div class="wrap genius-page">
<nav class="crumbs"><a href="/">Home</a> › Car Genius</nav>
<h1>Car Genius</h1>
<p class="lede">Explore the checked public records and our first RAV4 buying brief. Coverage is limited.
Reliability scores, automatic buying verdicts and market-price estimates are suspended.</p>
<div data-genius-page></div>
<noscript><p>Car Genius needs JavaScript. The same data is on every <a href="/cars/">car page</a> and in the
<a href="/guides/">guides</a>.</p></noscript>
<p class="src-note">Car Genius is an AI assistant. It can be wrong — check the figures on the linked page before
you buy. Questions are sent to our AI provider to be answered and are not stored with your account.
<a href="/methodology/">How the evidence is checked</a>.</p>
</div>"""


def main():
    con = sqlite3.connect(DB)
    ASSETS.mkdir(parents=True, exist_ok=True)
    c, g, pg = cars(con), guides(), pages()
    dump = lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)
    (ASSETS / "genius-cars.json").write_text(dump(c), encoding="utf-8")
    (ASSETS / "genius-guides.json").write_text(dump(g), encoding="utf-8")
    (ASSETS / "genius-pages.json").write_text(dump(pg), encoding="utf-8")
    canon = gen_site.ORIGIN + "/ask/"
    html = gen_site.page("Car Genius — ask anything about a car | MotorJury",
                         "Ask Car Genius which years to avoid, what breaks and what a car costs to own. "
                         "Answers from federal complaint and recall data, with links to the source page.",
                         canon, ASK_BODY,
                         # an app screen, not an article: kept out of the index so a reviewer
                         # sampling pages never lands on an empty chat box
                         extra_head=gen_site.NOINDEX)
    gen_site.write("ask/index.html", html)
    linked = sum(1 for r in c if r.get("url"))
    print(f"GENIUS OK: {len(c)} model-years ({linked} linked), {len(g)} guides, {len(pg)} pages indexed; /ask/ written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
