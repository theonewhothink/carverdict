#!/usr/bin/env python3
"""build_library.py — The Car Library: every automobile model ever catalogued (Wikidata/Commons).
Generates:
  site/library/index.html                EN flagship page (brand grid + A-Z)
  site/library/{brand}/index.html        1 page per brand, photo cards, licensed hotlinks
  site/{lang}/library/index.html         localized interactive library (renders from shared JSON)
  site/assets/library-data.json          shared dataset (also powers header search)
Photo policy: hotlink Wikimedia Commons via Special:FilePath (redirects to upload.wikimedia.org),
credit + link to the Commons file page on every card. No files copied -> no licensing risk.
"""
import json, os, re, sys, html
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import LANGS, RTL, t, S, LANG_NAMES

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://carsite.adir-073.workers.dev").rstrip("/")
DATA = json.load(open(ROOT / "data" / "car_library.json"))


def _load_logos():
    p = ROOT / "data" / "brand_logos.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


LOGOS = _load_logos()

BRAND_ALIAS = {
    "Mercedes-Benz Group": "Mercedes-Benz", "Daimler AG": "Mercedes-Benz",
    "Ford Motor Company": "Ford", "General Motors": "GM (General Motors)",
    "Bayerische Motoren Werke AG": "BMW", "Volkswagen Group": "Volkswagen",
    "Fiat Chrysler Automobiles": "Fiat", "PSA Group": "Peugeot",
}


def slug(s):
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:60] or "x"


def esc(s):
    return html.escape(str(s), quote=True)


def commons_thumb(fname, w=480):
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{fname.replace(' ', '_')}?width={w}"


def commons_page(fname):
    return "https://commons.wikimedia.org/wiki/File:" + fname.replace(" ", "_")


def is_qid(s):
    """True for a bare Wikidata identifier like 'Q796364'. The label service returns the
    Q-id itself when an item has no English label, so these leak in as 'brand names'."""
    s = (s or "").strip()
    return bool(re.fullmatch(r"Q\d+", s))


def resolve_qid_brands(rows, known):
    """Wikidata's label service echoes the bare Q-id when a manufacturer item has no
    English label, so 48 Bugattis were catalogued under a marque literally called
    "Q2308012". Recover the real marque from the models themselves: inside one Q-id
    group every name starts with the same word ("Bugatti Veyron", "Bugatti Type 57"),
    so that word is the brand. Requires a group of at least two models and 60% agreement;
    anything weaker is left blank for the existing name-inference and catch-all to handle.
    Mutates rows in place and returns how many were relabelled."""
    groups = defaultdict(list)
    for x in rows:
        if is_qid(x.get("m")):
            groups[x["m"].strip()].append(x)
    fixed = 0
    for qid, members in groups.items():
        firsts = Counter(x["n"].split()[0] for x in members if x.get("n", "").split())
        if not firsts:
            continue
        word, hits = firsts.most_common(1)[0]
        if len(members) < 2 or hits / len(members) < 0.6:
            continue
        if len(word) < 2 or word.isdigit() or is_qid(word):
            continue
        brand = known.get(word.lower(), word)   # canonical casing when we already know it
        for x in members:
            x["m"] = brand
        fixed += len(members)
    return fixed


# Values Wikidata's "powered by" (P516) returns that describe every car ever built.
# A Camry whose Engine fact reads "diesel engine" is worse than a Camry with no
# Engine fact: it is wrong, and it is wrong in a way a reader can see.
GENERIC_ENGINE = {
    "engine", "motor", "automobile engine", "car engine", "piston engine",
    "internal combustion engine", "combustion engine", "reciprocating engine",
    "four-stroke engine", "two-stroke engine", "spark-ignition engine",
    "compression-ignition engine", "diesel engine", "petrol engine",
    "gasoline engine", "gas engine", "electric motor", "electric engine",
    "hybrid", "hybrid vehicle", "hybrid electric vehicle",
}


def real_engine(v):
    """Drop engine values that name a category rather than an engine.

    Wikidata P516 mixes real answers ("2.85 L PRV ZMJ-159 V6") with taxonomy
    ("diesel engine"), and the taxonomy rows sort first often enough to win. A
    multi-valued string keeps whichever parts actually say something."""
    if not v:
        return None
    parts = [p.strip() for p in str(v).split(" / ") if p.strip()]
    keep = [p for p in parts if p.lower() not in GENERIC_ENGINE]
    return " / ".join(keep) or None


def brand_of(name, manufacturer, known):
    """The marque a reader expects, which is not always the manufacturer.

    Wikidata's P176 names the company that built the car, so the Daihatsu Altis,
    the Chevrolet Cavalier and the Lexus ES were all filed under "Toyota" - right
    for a factory, wrong under a heading that reads "More from Toyota". When the
    model's own name opens with a marque the catalogue already knows, that marque
    wins; otherwise the manufacturer stands."""
    low = (name or "").lower().split()
    for n_words in (3, 2, 1):
        cand = " ".join(low[:n_words])
        if cand in known:
            return known[cand]
    return norm_brand(manufacturer)


def norm_brand(m):
    m = (m or "").strip()
    # An unlabelled manufacturer item comes back as its own Q-id. That is not a marque:
    # treat it as missing so the model-name inference below can find the real brand
    # (and, failing that, the honest catch-all bucket is used instead of "Q796364").
    if is_qid(m):
        m = ""
    m = BRAND_ALIAS.get(m, m)
    return m if m else "Independent & coachbuilders"


def build_dataset():
    # pass 1: brands that Wikidata states explicitly
    known = {}
    for x in DATA:
        m = (x.get("m") or "").strip()
        if m and not is_qid(m):
            k = BRAND_ALIAS.get(m, m)
            known[k.lower()] = k
    n_fixed = resolve_qid_brands(DATA, known)
    if n_fixed:
        print(f"  brand labels recovered from unlabelled Wikidata ids: {n_fixed} models")
    brands = defaultdict(list)
    for x in DATA:
        name = x["n"].strip()
        if name.startswith("Q") and name[1:].isdigit():
            continue  # unlabeled junk
        b = brand_of(name, x["m"], known)
        brands[b].append({"n": name, "p": x["p"], "y": x["y"], "q": x["q"]})
    for b in brands:
        brands[b].sort(key=lambda r: (r["y"] or "9999", r["n"]))
    return dict(sorted(brands.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def header(lang="en", origin_prefix=""):
    pre = "" if lang == "en" else f"/{lang}"
    langsw = "".join(
        f'<a href="{"" if l == "en" else "/" + l}/{"library/" if True else ""}" '
        f'{"class=cur" if l == lang else ""}>{l.upper()}</a>' for l in LANGS)
    return f"""<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="{pre or "/"}">Car<em>Verdict</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="{esc(t(lang, "search_ph"))}" autocomplete="off"
 aria-label="search"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/cars/">{t(lang, "nav_browse")}</a><a href="{pre}/library/" class="cur">{t(lang, "nav_library")}</a><a href="/events/">Events</a><a href="/calculators/">{t(lang, "nav_calculators")}</a><a href="/recalls/">{t(lang, "nav_recalls")}</a></nav>
<details class="langs"><summary>{lang.upper()}</summary><div>{langsw}</div></details>
</div></header>"""


def shell(lang, title, desc, canon, body, extra_head=""):
    d = ' dir="rtl"' if lang in RTL else ""
    hreflang = "".join(
        f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}{"" if l == "en" else "/" + l}/library/">'
        for l in LANGS) + f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/library/">'
    return f"""<!doctype html><html lang="{lang}"{d}><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">
<link rel="stylesheet" href="/assets/site.css">{hreflang}{extra_head}</head><body>
{header(lang)}{body}
<footer><div class="wrap"><p>{t(lang, "footer_data")} · <a href="/methodology/">{t(lang, "nav_methodology")}</a> · {t(lang, "lib_photo_credit")} (<a href="https://commons.wikimedia.org" rel="noopener">CC</a>)</p></div></footer>
<script src="/assets/site.js" defer></script>
<script src="/assets/lightbox.js" defer></script></body></html>"""


MODEL_INDEX = {}
def load_model_index():
    global MODEL_INDEX
    f = ROOT / "data" / "model_index.json"
    if f.exists():
        MODEL_INDEX = json.loads(f.read_text())

def card(m, lang="en", lazy=True, brand_slug=""):
    """The WHOLE card links to the model page — a photo click opens the car, never an image file."""
    y = f'<small>{t(lang, "lib_since")} {m["y"]}</small>' if m["y"] else ""
    has_page = m["n"] in MODEL_INDEX.get(brand_slug, {})
    url = f'/library/{brand_slug}/{slug(m["n"])}/' if has_page else f'/library/{brand_slug}/'
    if m["p"]:
        img = (f'<span class="ph"><img src="{commons_thumb(m["p"])}" alt="{esc(m["n"])}"'
               f'{" loading=lazy" if lazy else ""} '
               f'onerror="this.closest(\'.ph\').classList.add(\'noimg\')"></span>')
    else:
        img = ('<span class="ph noimg"><svg viewBox="0 0 64 28"><path d="M6 22c2-6 8-9 14-9h20c6 0 12 3 14 9" '
               'fill="none" stroke="currentColor" stroke-width="2"/><circle cx="18" cy="22" r="4" fill="currentColor"/>'
               '<circle cx="46" cy="22" r="4" fill="currentColor"/></svg></span>')
    return f'<a class="lib-card" href="{url}">{img}<b>{esc(m["n"])}</b>{y}</a>'


REST_DATA = {}

def main():
    load_model_index()
    brands = build_dataset()
    n_models = sum(len(v) for v in brands.values())
    n_photos = sum(1 for v in brands.values() for m in v if m["p"])

    # shared data (search + localized dynamic library)
    data_out = {b: {"s": slug(b), "m": [[m["n"], m["p"] and 1 or 0, m["y"]] for m in v]} for b, v in brands.items()}
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "library-data.json").write_text(json.dumps(data_out, separators=(",", ":"), ensure_ascii=False))

    # photo pool for Car of the Day / Guess the Car (needs real filenames; kept separate
    # so the search index stays small on mobile). Big brands only = recognisable cars.
    BIG = {b for b, v in list(brands.items())[:120]}
    pool = []
    for b, v in brands.items():
        if b not in BIG:
            continue
        for m in v:
            if m["p"] and len(m["n"]) < 40 and m["n"] in MODEL_INDEX.get(slug(b), {}):
                pool.append([m["n"], b, slug(b), m["y"], m["p"]])
    pool.sort(key=lambda r: r[0])
    (SITE / "assets" / "daily-pool.json").write_text(json.dumps(pool, separators=(",", ":"), ensure_ascii=False))

    # brand pages (EN, static — SEO spearhead market)
    for b, models in brands.items():
        bs = slug(b)
        FIRST = 48
        cards = "".join(card(m, brand_slug=bs) for m in models[:FIRST])
        rest = [[m["n"], m["p"], m["y"], (MODEL_INDEX.get(bs, {}) or {}).get(m["n"], "")]
                for m in models[FIRST:]]
        if rest:
            REST_DATA[bs] = rest
        more = (f'<button class="btn ghost more-btn" data-brand="{bs}">'
                f'Show all {len(models)} {esc(b)} models</button>') if rest else ""
        with_photos = sum(1 for m in models if m["p"])
        body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<nav class="crumbs"><a href="/library/">{t("en", "nav_library")}</a> › {esc(b)}</nav>
<h1>{esc(b)}: every model ever made</h1>
<p class="sub">{len(models)} {t("en", "lib_models")} · {with_photos} {t("en", "lib_photos")}</p></div></div>
<div class="wrap"><div class="lib-grid" id="lib-grid">{cards}</div>
<div style="padding:6px 0 22px">{more}</div>
<p class="lib-note">Photos: <a href="https://commons.wikimedia.org" rel="noopener">Wikimedia Commons</a>, hotlinked with per-file credit links. Catalog: <a href="https://www.wikidata.org" rel="noopener">Wikidata</a> (CC0).</p></div>"""
        out = SITE / "library" / bs / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(shell("en", f"{b} — Complete Model Library | CarVerdict",
                             f"All {len(models)} {b} models ever catalogued, with photos.",
                             f"{ORIGIN}/library/{bs}/", body))

    # library index (EN static)
    # Brand tiles carry the marque's logo on white. The old tiles put the name over a
    # 16%-opacity photograph, which read as a washed-out smudge.
    top = list(brands.items())[:24]

    def tile(b, v):
        logo = LOGOS.get(b)
        mark = (f'<span class="bt-logo"><img src="{esc(logo)}" alt="{esc(b)} logo" loading="lazy"></span>'
                if logo else f'<span class="bt-logo bt-initial">{esc(b[0].upper())}</span>')
        return (f'<a class="brand-tile" href="/library/{slug(b)}/">{mark}'
                f'<b>{esc(b)}</b><small>{len(v)} {t("en", "lib_models")}</small></a>')

    top_html = "".join(tile(b, v) for b, v in top)
    az = defaultdict(list)
    for b, v in brands.items():
        az[b[0].upper() if b[0].isalpha() else "#"].append((b, len(v)))
    az_nav = "".join(f'<a href="#az-{k if k.isalpha() else "num"}">{k}</a>' for k in sorted(az))
    az_html = "".join(
        f'<div class="az-group" id="az-{k if k.isalpha() else "num"}"><h3>{k}</h3>' + "".join(
            f'<a href="/library/{slug(b)}/">{esc(b)} <span>{n}</span></a>' for b, n in sorted(v)) + "</div>"
        for k, v in sorted(az.items()))
    az_html = f'<nav class="az-jump">{az_nav}</nav>' + az_html
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>{t("en", "lib_title")}</h1>
<p class="sub"><b>{n_models:,}</b> {t("en", "lib_sub")} <b>{len(brands):,}</b> {t("en", "lib_brands")} — <b>{n_photos:,}</b> {t("en", "lib_photos")}.</p>
</div></div>
<div class="wrap">
<h2 class="sec">{t("en", "lib_top_brands")}</h2><div class="brand-grid">{top_html}</div>
<h2 class="sec">{t("en", "lib_all_brands")}</h2><div class="az">{az_html}</div>
</div>"""
    (SITE / "library").mkdir(parents=True, exist_ok=True)
    (SITE / "library" / "index.html").write_text(
        shell("en", "The Car Library — Every Car Model Ever Made | CarVerdict",
              f"{n_models:,} car models from {len(brands):,} brands, with photography. The complete automotive catalog.",
              f"{ORIGIN}/library/", body))

    # localized dynamic library (renders client-side from shared JSON)
    for lang in LANGS:
        if lang == "en":
            continue
        body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>{t(lang, "lib_title")}</h1>
<p class="sub"><b>{n_models:,}</b> {t(lang, "lib_sub")} <b>{len(brands):,}</b> {t(lang, "lib_brands")} — <b>{n_photos:,}</b> {t(lang, "lib_photos")}.</p>
</div></div>
<div class="wrap"><div id="lib-app" data-lang="{lang}"
 data-i18n='{json.dumps({k: t(lang, k) for k in ["lib_models", "lib_since", "lib_photo_credit", "search_none", "lib_all_brands", "lib_top_brands"]}, ensure_ascii=False)}'>
<noscript>JavaScript required for the localized library. <a href="/library/">English static version</a>.</noscript>
</div></div><script src="/assets/library-app.js" defer></script>"""
        out = SITE / lang / "library" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(shell(lang, t(lang, "lib_title") + " | CarVerdict",
                             f"{n_models:,} — {len(brands):,}.",
                             f"{ORIGIN}/{lang}/library/", body))

    (SITE / "assets" / "brand-rest.json").write_text(
        json.dumps(REST_DATA, separators=(",", ":"), ensure_ascii=False))
    print(f"LIBRARY OK: {n_models} models, {len(brands)} brands, {n_photos} photos, "
          f"{1 + len(brands) + len(LANGS) - 1} pages, pool {len(pool)}")


if __name__ == "__main__":
    main()
