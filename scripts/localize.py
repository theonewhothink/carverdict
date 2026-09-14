#!/usr/bin/env python3
"""localize.py — deterministic i18n post-pass.
Copies generated EN pages (home, /cars/**, /calculators/, /recalls/) into /{lang}/... with:
  - <html lang> + dir=rtl for Hebrew
  - translated template strings (pattern tables in i18n.py — all prose is templated, so
    replacement is complete for covered patterns; uncovered long-tail stays EN and is logged)
  - hreflang alternates on every localized + source page
  - localized nav/search placeholder
Then rebuilds the sitemap from the final site/ tree (all languages + library).
"""
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import LANGS, RTL, P, t, meta

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
import os
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")

LOCALIZE_DIRS = ["cars", "calculators", "recalls"]


def rel_urls(page_rel):
    """page_rel like 'cars/toyota/camry/2007/index.html' -> per-lang URLs"""
    u = "/" + page_rel.replace("index.html", "")
    return {l: (u if l == "en" else f"/{l}{u}") for l in LANGS}


RE_HREFLANG = re.compile(r'<link rel="alternate" hreflang="[^"]+" href="[^"]+">')


def hreflang_block(urls):
    tags = "".join(f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}{u}">' for l, u in urls.items())
    return tags + f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}{urls["en"]}">'


def set_hreflang(html, urls):
    """Replace, never append. The EN source already carries the block by the time the
    localized copies are made, so appending emitted every alternate twice — a validity
    error that can void the whole language cluster."""
    html = RE_HREFLANG.sub("", html)
    html = re.sub(r'<link rel="alternate" hreflang="x-default" href="[^"]+">', "", html)
    return html.replace("</head>", hreflang_block(urls) + "</head>", 1)


def page_kind(rel):
    """Which localized template this page is, for its title and description."""
    if rel == "index.html":
        return "home", ""
    parts = rel.split("/")
    if parts[0] == "cars":
        return ("cars", "") if len(parts) == 2 else ("brand", parts[1])
    if parts[0] in ("calculators", "recalls"):
        return parts[0], ""
    return None, ""


RE_TITLE = re.compile(r"<title>.*?</title>", re.S)
RE_DESC = re.compile(r'<meta name="description" content="[^"]*">')


def set_meta(html, rel, lang):
    kind, brand = page_kind(rel)
    if not kind:
        return html
    if brand:
        m = re.search(r"<h1>([^<]+?)\s+ownership", html) or re.search(r"<h1>([^<]+)</h1>", html)
        brand = (m.group(1).strip() if m else brand.replace("-", " ").title())
    e = meta(kind, lang, brand)
    if not e:
        return html
    title, desc = e
    html = RE_TITLE.sub(f"<title>{title}</title>", html, count=1)
    html = RE_DESC.sub(f'<meta name="description" content="{desc}">', html, count=1)
    html = re.sub(r'<meta property="og:title" content="[^"]*">',
                  f'<meta property="og:title" content="{title}">', html, count=1)
    html = re.sub(r'<meta property="og:description" content="[^"]*">',
                  f'<meta property="og:description" content="{desc}">', html, count=1)
    return html


def localize_html(html, lang, urls, rel=""):
    # lang + rtl
    html = html.replace('<html lang="en">', f'<html lang="{lang}"{" dir=rtl" if lang in RTL else ""}>')
    # canonical -> localized
    html = re.sub(r'(<link rel="canonical" href=")([^"]+)(")',
                  lambda m: m.group(1) + ORIGIN + urls[lang] + m.group(3), html)
    # Localised copies are pattern-substituted English, and the long tail stays English.
    # A half-translated page is exactly what Google's "automatically generated content"
    # rule describes, so these copies serve readers who pick a language but stay
    # noindex,follow and carry no hreflang cluster. The English page is the only indexed one.
    html = RE_HREFLANG.sub("", html)
    html = re.sub(r'<link rel="alternate" hreflang="x-default" href="[^"]+">', "", html)
    if 'name="robots"' not in html:
        html = html.replace("</head>", '<meta name="robots" content="noindex,follow"></head>', 1)
    # translated title + description
    html = set_meta(html, rel, lang)
    # nav + search chrome
    html = html.replace('placeholder="Search any car ever made…"', f'placeholder="{t(lang, "search_ph")}"')
    html = html.replace('data-none="No matches"', f'data-none="{t(lang, "search_none")}"')
    html = (html.replace(">Browse</a>", f'>{t(lang, "nav_browse")}</a>')
                .replace(">Library</a>", f'>{t(lang, "nav_library")}</a>')
                .replace(">Calculators</a>", f'>{t(lang, "nav_calculators")}</a>')
                .replace(">Recalls</a>", f'>{t(lang, "nav_recalls")}</a>')
                .replace(">Methodology</a>", f'>{t(lang, "nav_methodology")}</a>'))
    html = html.replace("<summary>EN</summary>", f"<summary>{lang.upper()}</summary>")
    html = html.replace('<a class="cur" href="/">EN</a>', '<a href="/">EN</a>')
    html = html.replace(f'<a href="/{lang}/">{lang.upper()}</a>',
                        f'<a class="cur" href="/{lang}/">{lang.upper()}</a>')
    # content patterns
    for pat, rep in P[lang]:
        html = re.sub(pat, rep, html)
    # keep language when navigating localized sections
    html = re.sub(r'href="/(calculators|recalls)/', f'href="/{lang}/\\1/', html)
    # /cars/ localizes only the section index and brand hubs; deeper model-year
    # pages exist in English alone, so only hub links keep the language prefix.
    html = re.sub(r'href="/cars/(?=")', f'href="/{lang}/cars/', html)
    html = re.sub(r'href="/cars/([a-z0-9-]+)/(?=")', f'href="/{lang}/cars/\\1/', html)
    html = html.replace('href="/library/"', f'href="/{lang}/library/"')
    return html


def main():
    pages = []
    for d in LOCALIZE_DIRS:
        for p in (SITE / d).rglob("index.html"):
            rel = p.relative_to(SITE / d).parts
            # /cars/ localizes only the section index and brand hubs. Model and
            # model-year pages are English data records; duplicating thousands of
            # them per language would blow the 20,000 static-asset budget as the
            # nightly dataset compounds.
            if d == "cars" and len(rel) > 2:
                continue
            pages.append(p)
    pages.append(SITE / "index.html")
    made = 0
    for p in pages:
        rel = p.relative_to(SITE).as_posix()
        urls = rel_urls(rel)
        src = p.read_text()
        # The EN source carries no hreflang: the localised copies are noindex (see
        # localize_html), and an alternate cluster pointing at noindexed pages is invalid.
        src = RE_HREFLANG.sub("", src)
        src = re.sub(r'<link rel="alternate" hreflang="x-default" href="[^"]+">', "", src)
        p.write_text(src)
        for lang in LANGS:
            if lang == "en":
                continue
            out = SITE / lang / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(localize_html(src, lang, urls, rel))
            made += 1
    # rebuild sitemap from the final tree
    import datetime, hashlib, json as _json, os, pathlib, re as _re, urllib.request
    today = datetime.date.today().isoformat()

    # ---- lastmod that means something ---------------------------------------------------
    # Every URL used to carry the build date, and the whole site is rebuilt nightly, so the
    # sitemap told Google that all 4,000 pages changed every single day. Google states
    # plainly that it ignores lastmod when the value is not trustworthy, and "everything
    # changed today, again" is the textbook untrustworthy value — so the one signal that
    # could pull the rewritten pages to the front of the recrawl queue was being thrown away.
    #
    # A page's date now advances only when its own content actually changes. The hash
    # ignores the parts that differ on every build by construction — the printed build date,
    # the asset cache-busting query strings, the ad markup and the nonce-ish bits — so a page
    # whose words and numbers are identical keeps the date it already had.
    VOLATILE = [
        (_re.compile(r'<script\b[^>]*>.*?</script>', _re.S), ""),
        (_re.compile(r'\?v=[0-9a-f]{6,}'), ""),
        (_re.compile(r'Last updated:\s*\d{4}-\d{2}-\d{2}'), ""),
        (_re.compile(r'updated \d{4}-\d{2}-\d{2}'), ""),
        (_re.compile(r'<ins\b[^>]*></ins>'), ""),
        (_re.compile(r'\d{4}-\d{2}-\d{2}'), ""),
    ]

    def content_hash(html):
        body = html.split("<body", 1)[-1].rsplit("</body>", 1)[0]
        for rx, rep in VOLATILE:
            body = rx.sub(rep, body)
        body = _re.sub(r"\s+", " ", body)
        return hashlib.sha1(body.encode("utf-8", "ignore")).hexdigest()[:16]

    def previous_manifest():
        """Last build's hashes, published with the site itself. Advisory: on any failure
        every page simply gets today's date, which is where this started."""
        local = os.environ.get("LASTMOD_MANIFEST")
        if local and pathlib.Path(local).exists():
            try:
                return _json.loads(pathlib.Path(local).read_text())
            except Exception:
                return {}
        try:
            req = urllib.request.Request(ORIGIN + "/assets/lastmod.json",
                                         headers={"User-Agent": "motorjury-build"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return _json.loads(r.read().decode())
        except Exception as exc:
            print(f"  lastmod: no published manifest ({exc.__class__.__name__}); "
                  f"every page dated today")
            return {}

    prev = previous_manifest()
    manifest, urls, carried = {}, [], 0
    for p in sorted(SITE.rglob("index.html")):
        u = "/" + p.relative_to(SITE).as_posix().replace("index.html", "")
        if u == "/404.html":
            continue
        try:
            html = p.read_text()
        except Exception:
            continue
        # A page we ask search engines not to index has no business in the sitemap.
        if 'name="robots" content="noindex' in html:
            continue
        h = content_hash(html)
        was = prev.get(u)
        if was and was[0] == h:
            when = was[1]
            carried += 1
        else:
            when = today
        manifest[u] = [h, when]
        urls.append((ORIGIN + u, when))

    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "lastmod.json").write_text(
        _json.dumps(manifest, separators=(",", ":")))
    shard = "".join(f"<url><loc>{u}</loc><lastmod>{w}</lastmod></url>" for u, w in urls)
    (SITE / "sitemap-0.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + shard + "</urlset>")
    print(f"LOCALIZED: {made} pages across {len(LANGS) - 1} languages; sitemap {len(urls)} URLs "
          f"({carried} keeping an earlier lastmod, {len(urls) - carried} dated today)")


if __name__ == "__main__":
    main()
