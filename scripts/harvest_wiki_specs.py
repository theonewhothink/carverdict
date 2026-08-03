#!/usr/bin/env python3
"""harvest_wiki_specs.py — real technical specifications, from Wikipedia infoboxes.

Correcting an earlier mistake: I checked Wikidata, found power output on 58 of ~13,700
models, and concluded horsepower "is not available as free data". That was one source, not
the web. Wikipedia's {{Infobox automobile}} carries engine, power, production years, kerb
weight, transmission, layout, body style and assembly plant for a large share of models —
free, CC BY-SA, and far richer than Wikidata's structured claims.

    Porsche 911 GT3 -> engine "3.6L (3,596cc) Porsche M96.79 N/A Flat-6"
                       power  "{{cvt|360-380|PS|kW hp}}"  -> "360-380 PS (kW hp)"
                       production "1999-present", weight "3,043 lb", layout, transmission

Efficiency: titles resolve 50 per request via Wikidata sitelinks, then wikitext is fetched
50 pages per request. ~17,400 models cost roughly 700 requests, not 17,400.

Other free sources verified and wired in elsewhere / queued:
  NHTSA vPIC    vpic.nhtsa.dot.gov  free, no key, returns EngineHP + displacement +
                cylinders + drive + body class per VIN (520 hp for a 2019 911, confirmed)
  EPA           fueleconomy.gov     public domain, MPG city/highway/combined, annual fuel
                cost, CO2, per trim
"""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "data" / "car_library.json"
OUT = ROOT / "data" / "wiki_specs.json"
WD = "https://www.wikidata.org/w/api.php"
WP = "https://en.wikipedia.org/w/api.php"
UA = "CarVerdict/1.0 (https://carsite.adir-073.workers.dev) python-urllib"
BATCH = 50

# infobox key -> our field. Wikipedia uses several spellings for the same thing.
FIELDS = {
    "engine": ["engine"],
    "power": ["powerout", "power"],
    "production": ["production"],
    "model_years": ["model_years"],
    "weight": ["weight"],
    "transmission": ["transmission"],
    "layout": ["layout"],
    "body": ["body_style"],
    "assembly": ["assembly"],
    "designer": ["designer"],
    "wheelbase": ["wheelbase"],
    "predecessor": ["predecessor"],
    "successor": ["successor"],
}


def _get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def clean(v):
    """Infobox values are wiki markup. Unwrap the common templates rather than dumping
    braces on the page: {{cvt|3,043|lb}} -> '3,043 lb'."""
    if not v:
        return None
    v = re.sub(r"<ref[^>]*>.*?</ref>", "", v, flags=re.S)
    v = re.sub(r"<ref[^>]*/>", "", v)
    v = re.sub(r"<br\s*/?>", " / ", v, flags=re.I)
    v = re.sub(r"<[^>]+>", "", v)

    def cvt(m):
        parts = [p.strip() for p in m.group(1).split("|") if p.strip()]
        parts = [p for p in parts if "=" not in p]
        if not parts:
            return ""
        num = parts[0]
        unit = parts[1] if len(parts) > 1 else ""
        return f"{num} {unit}".strip()

    v = re.sub(r"\{\{\s*(?:cvt|convert)\s*\|([^{}]*)\}\}", cvt, v, flags=re.I)
    v = re.sub(r"\{\{\s*(?:nowrap|nobr)\s*\|([^{}]*)\}\}", r"\1", v, flags=re.I)
    v = re.sub(r"\{\{[^{}]*\}\}", " ", v)                 # drop remaining templates
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)   # [[A|B]] -> B
    v = v.replace("[[", "").replace("]]", "").replace("'''", "").replace("''", "")
    v = re.sub(r"\s*\*\s*", " / ", v)
    v = re.sub(r"\s{2,}", " ", v).strip(" /,;|")
    return v[:180] or None


def parse_infobox(text):
    if not text:
        return {}
    # narrow to the infobox so a "production" line in prose cannot be mistaken for a field
    i = text.lower().find("{{infobox")
    box = text[i:i + 9000] if i >= 0 else text[:6000]
    out = {}
    for field, keys in FIELDS.items():
        for k in keys:
            m = re.search(r"\|\s*" + k + r"\s*=\s*(.+?)(?=\n\s*\||\n\}\})", box, re.S | re.I)
            if m:
                c = clean(m.group(1))
                if c:
                    out[field] = c
                    break
    return out


def titles_for(qids):
    """Wikidata id -> English Wikipedia title, 50 at a time."""
    out = {}
    for i in range(0, len(qids), BATCH):
        chunk = qids[i:i + BATCH]
        url = (f"{WD}?action=wbgetentities&format=json&props=sitelinks"
               f"&sitefilter=enwiki&ids={'|'.join(chunk)}")
        for attempt in range(3):
            try:
                j = _get(url)
                break
            except Exception:
                if attempt == 2:
                    j = {}
                time.sleep(2 * (attempt + 1))
        for qid, ent in (j.get("entities") or {}).items():
            t = ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title")
            if t:
                out[qid] = t
        time.sleep(0.2)
    return out


def wikitext_for(titles):
    """Title -> wikitext, 50 pages per request."""
    out = {}
    items = list(titles)
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        url = (f"{WP}?action=query&format=json&prop=revisions&rvprop=content&rvslots=main"
               f"&titles={urllib.parse.quote('|'.join(chunk))}")
        try:
            j = _get(url)
        except Exception:
            time.sleep(2)
            continue
        pages = ((j.get("query") or {}).get("pages") or {})
        for p in pages.values():
            t = p.get("title")
            try:
                out[t] = p["revisions"][0]["slots"]["main"]["*"]
            except Exception:
                continue
        time.sleep(0.2)
    return out


def main():
    lib = json.loads(LIB.read_text())
    qids = [x["q"] for x in lib if x.get("q", "").startswith("Q")]
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        qids = qids[:limit]
    print(f"resolving {len(qids)} models to Wikipedia titles…")

    titles = titles_for(qids)
    print(f"  {len(titles)} have an English article")

    by_title = {t: q for q, t in titles.items()}
    texts = wikitext_for(list(by_title))
    print(f"  fetched wikitext for {len(texts)}")

    specs, filled = {}, 0
    for title, text in texts.items():
        qid = by_title.get(title)
        if not qid:
            continue
        got = parse_infobox(text)
        if got:
            got["wp"] = title
            specs[qid] = got
            filled += 1

    # The prose intro — what makes a model page worth reading rather than a table.
    # exlimit caps at 20 titles per request even though wikitext allows 50.
    print("fetching article intros…")
    intros, wanted = 0, list(by_title)
    for i in range(0, len(wanted), 20):
        chunk = wanted[i:i + 20]
        url = (f"{WP}?action=query&format=json&prop=extracts&exintro=1&explaintext=1"
               f"&exlimit=20&redirects=1&titles={urllib.parse.quote('|'.join(chunk))}")
        try:
            j = _get(url)
        except Exception:
            time.sleep(2)
            continue
        for p in ((j.get("query") or {}).get("pages") or {}).values():
            qid = by_title.get(p.get("title"))
            ex = (p.get("extract") or "").strip()
            if qid and len(ex) > 120:
                specs.setdefault(qid, {})["about"] = ex[:1600]
                specs[qid].setdefault("wp", p.get("title"))
                intros += 1
        time.sleep(0.2)
    print(f"  {intros} models have an article intro")

    if not specs:
        print("WIKI SPECS SKIPPED: nothing parsed; leaving existing file untouched")
        return 0

    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
        except Exception:
            prev = {}
    if len(specs) < len(prev) * 0.6:          # never let a bad run gut the file
        print(f"WIKI SPECS: only {len(specs)} vs cached {len(prev)}; keeping cache")
        return 0
    prev.update(specs)
    OUT.write_text(json.dumps(prev, ensure_ascii=False, separators=(",", ":")))

    have = lambda k: sum(1 for v in prev.values() if v.get(k))
    print(f"WIKI SPECS OK: {len(prev)} models — engine {have('engine')}, power {have('power')}, "
          f"production {have('production')}, weight {have('weight')}, "
          f"transmission {have('transmission')}, assembly {have('assembly')}, "
          f"about {have('about')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
