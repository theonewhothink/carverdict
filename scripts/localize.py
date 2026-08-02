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
from i18n import LANGS, RTL, P, t

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = "https://carverdict.example"

LOCALIZE_DIRS = ["cars", "calculators", "recalls"]


def rel_urls(page_rel):
    """page_rel like 'cars/toyota/camry/2007/index.html' -> per-lang URLs"""
    u = "/" + page_rel.replace("index.html", "")
    return {l: (u if l == "en" else f"/{l}{u}") for l in LANGS}


def hreflang_block(urls):
    tags = "".join(f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}{u}">' for l, u in urls.items())
    return tags + f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}{urls["en"]}">'


def localize_html(html, lang, urls):
    # lang + rtl
    html = html.replace('<html lang="en">', f'<html lang="{lang}"{" dir=rtl" if lang in RTL else ""}>')
    # canonical -> localized
    html = re.sub(r'(<link rel="canonical" href=")([^"]+)(")',
                  lambda m: m.group(1) + ORIGIN + urls[lang] + m.group(3), html)
    # hreflang
    html = html.replace("</head>", hreflang_block(urls) + "</head>")
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
    html = re.sub(r'href="/(cars|calculators|recalls)/', f'href="/{lang}/\\1/', html)
    html = html.replace('href="/library/"', f'href="/{lang}/library/"')
    return html


def main():
    pages = [p for d in LOCALIZE_DIRS for p in (SITE / d).rglob("index.html")]
    pages.append(SITE / "index.html")
    made = 0
    for p in pages:
        rel = p.relative_to(SITE).as_posix()
        urls = rel_urls(rel)
        src = p.read_text()
        # add hreflang to the EN source too
        if "hreflang" not in src:
            p.write_text(src.replace("</head>", hreflang_block(urls) + "</head>"))
            src = p.read_text()
        for lang in LANGS:
            if lang == "en":
                continue
            out = SITE / lang / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(localize_html(src, lang, urls))
            made += 1
    # rebuild sitemap from the final tree
    urls = []
    for p in sorted(SITE.rglob("index.html")):
        u = "/" + p.relative_to(SITE).as_posix().replace("index.html", "")
        if u == "/404.html":
            continue
        urls.append(ORIGIN + u)
    shard = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    (SITE / "sitemap-0.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + shard + "</urlset>")
    print(f"LOCALIZED: {made} pages across {len(LANGS) - 1} languages; sitemap {len(urls)} URLs")


if __name__ == "__main__":
    main()
