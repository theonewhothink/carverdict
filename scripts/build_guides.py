#!/usr/bin/env python3
"""build_guides.py — the written layer: signed, dated buyer's guides.

Source: data/guides/*.md. Each file opens with a header block, then `---`, then the body:

    title: Used Honda CR-V: the years to buy and the years to avoid
    slug: honda-cr-v-years-to-avoid
    date: 2026-09-01
    description: one sentence for search results and the index card
    models: honda/cr-v, honda/cr-v-hybrid       (optional; renders live year tables + links)
    ---
    Markdown body. Supports #/##/### headings, paragraphs, **bold**, *italic*,
    [links](/cars/), bullet lists, and {{years:honda/cr-v}} which expands to that
    nameplate's live year-by-year table from data/cars.sqlite.

Output: site/guides/<slug>/index.html and site/guides/index.html. Runs after gen_site.py
(which wipes site/) and before localize.py (so the pages enter the sitemap).

Why this exists: every other page on the site is computed. AdSense rejected the site as
"low value content" because a reviewer sampling pages finds one template everywhere. The
guides are the pages a reviewer must land on — human-written, attributed, dated, and
checkable against the model pages they link to.
"""
import html, json, re, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gen_site  # noqa: E402  (shell, write, ORIGIN, BRAND, TODAY, esc)

SITE = ROOT / "site"
SRC = ROOT / "data" / "guides"
DB = ROOT / "data" / "cars.sqlite"
ORIGIN, BRAND, page, write, esc = gen_site.ORIGIN, gen_site.BRAND, gen_site.page, gen_site.write, gen_site.esc
EDITOR = gen_site.EDITOR
HUB_NOTES = gen_site.HUB_NOTES


def parse(text):
    head, body = text.split("\n---", 1)
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", head, re.M))
    meta["models"] = [m.strip() for m in meta.get("models", "").split(",") if m.strip()]
    return meta, body.strip()


def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    return s


def md(body, tables):
    out, para, ul = [], [], False

    def flush():
        nonlocal para
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []

    for line in body.split("\n"):
        t = line.rstrip()
        if not t:
            flush()
            if ul:
                out.append("</ul>"); ul = False
            continue
        m = re.match(r"\{\{years:([\w/-]+)\}\}", t)
        if m:
            flush()
            out.append(tables(m.group(1)))
            continue
        if t.startswith("### "):
            flush(); out.append(f"<h3>{inline(t[4:])}</h3>"); continue
        if t.startswith("## "):
            flush(); out.append(f"<h2>{inline(t[3:])}</h2>"); continue
        if t.startswith("# "):
            flush(); out.append(f"<h2>{inline(t[2:])}</h2>"); continue
        if t.startswith("- "):
            flush()
            if not ul:
                out.append("<ul>"); ul = True
            out.append(f"<li>{inline(t[2:])}</li>")
            continue
        para.append(t)
    flush()
    if ul:
        out.append("</ul>")
    return "".join(out)


def year_table_factory(con):
    def exists(u):
        return (SITE / u.strip("/") / "index.html").exists()

    def table(key):
        try:
            kslug, mslug = key.split("/")
        except ValueError:
            return ""
        rows = con.execute("""SELECT mk.name make, mo.name model, my.year, my.complaint_count cc,
            my.recall_count rc, s.reliability_score score, s.verdict
            FROM model_years my JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
            LEFT JOIN computed_scores s ON s.my_id=my.id
            WHERE mk.slug=? AND mo.slug=? ORDER BY my.year DESC""", (kslug, mslug)).fetchall()
        if not rows:
            return ""
        make, model = rows[0][0], rows[0][1]
        trs = []
        for _, _, y, cc, rc, score, verdict in rows:
            u = f"/cars/{kslug}/{mslug}/{y}/"
            cell = f'<a href="{u}">{y}</a>' if exists(u) else str(y)
            trs.append(f"<tr><td>{cell}</td><td class=\"num\">{score if score is not None else '—'}</td>"
                       f"<td>{gen_site.vtag(verdict)}</td><td class=\"num\">{(cc or 0):,}</td>"
                       f"<td class=\"num\">{rc if rc is not None else '—'}</td></tr>")
        return (f'<div class="card"><h3>{esc(make)} {esc(model)}: the record, year by year</h3>'
                f'<div class="table-wrap"><table class="cost-table"><thead><tr><th>Year</th><th>Score</th>'
                f'<th>Verdict</th><th>NHTSA complaints</th><th>Recalls</th></tr></thead><tbody>{"".join(trs)}'
                f'</tbody></table></div><p class="src-note">Live from the federal record as of {gen_site.TODAY}; '
                f'linked years have their own page. Full table and repair costs on the '
                f'<a href="/cars/{kslug}/{mslug}/">{esc(make)} {esc(model)} model page</a>.</p></div>')
    return table


def model_links(con, keys):
    out = []
    for key in keys:
        try:
            kslug, mslug = key.split("/")
        except ValueError:
            continue
        r = con.execute("""SELECT mk.name, mo.name, COUNT(*), SUM(my.complaint_count) FROM model_years my
            JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
            WHERE mk.slug=? AND mo.slug=?""", (kslug, mslug)).fetchone()
        if r and r[0] and (SITE / "cars" / kslug / mslug / "index.html").exists():
            out.append(f'<a href="/cars/{kslug}/{mslug}/">{esc(r[0])} {esc(r[1])}'
                       f'<small>{r[2]} model years · {(r[3] or 0):,} complaints on record</small></a>')
    return f'<div class="card"><h2>Model pages behind this guide</h2><div class="rel-grid">{"".join(out)}</div></div>' if out else ""


def main():
    con = sqlite3.connect(DB)
    tables = year_table_factory(con)
    guides = []
    for f in sorted(SRC.glob("*.md")):
        meta, body = parse(f.read_text())
        slug = meta["slug"]
        url = f"/guides/{slug}/"
        canon = ORIGIN + url
        words = len(re.sub(r"\{\{.*?\}\}", "", body).split())
        article = md(body, tables)
        others = ""  # filled after all guides are parsed
        guides.append((meta, body, url, canon, words, article))

    for meta, body, url, canon, words, article in guides:
        related = [g for g in guides if g[2] != url][:0]
        # cross-links: guides that share a model, else the newest six
        mine = set(meta["models"])
        rel = [g for g in guides if g[2] != url and mine & set(g[0]["models"])]
        if len(rel) < 4:
            rel += [g for g in guides if g[2] != url and g not in rel][:4 - len(rel)]
        rel_html = ('<div class="card"><h2>More guides</h2><div class="rel-grid">' + "".join(
            f'<a href="{g[2]}">{esc(g[0]["title"])}<small>{esc(g[0].get("date", ""))}</small></a>'
            for g in rel[:6]) + "</div></div>")
        byline = (f'<div class="triad"><b>By</b> <a href="/about/">{EDITOR}</a>, editor · '
                  f'<b>Published</b> {esc(meta.get("date", gen_site.TODAY))} · '
                  f'<b>Sources</b> <a href="/methodology/">NHTSA, EPA</a> · '
                  f'<a href="/editorial-policy/">editorial policy</a> · {words:,} words</div>')
        body_html = f"""<div class="hero"><div class="wrap hero-inner"><div class="hero-copy">
<nav class="crumbs"><a href="/guides/">Guides</a> › {esc(meta["title"])}</nav>
<h1>{esc(meta["title"])}</h1>
<p class="sub">{esc(meta.get("description", ""))}</p>
{byline}
</div></div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0;max-width:860px">
<article class="card prose guide">{article}
<p class="src-note">Written by {EDITOR}. Complaint and recall figures are from NHTSA and are re-checked on
every nightly build; the year tables above are live. If a figure here disagrees with a model page, the model
page is newer — write to corrections@motorjury.com and the guide is revised.</p></article>
{model_links(con, meta["models"])}
{rel_html}
</div>"""
        jsonld = [{"@context": "https://schema.org", "@type": "Article", "headline": meta["title"],
                   "description": meta.get("description", ""), "datePublished": meta.get("date", gen_site.TODAY),
                   "dateModified": meta.get("updated", meta.get("date", gen_site.TODAY)),
                   "author": {"@type": "Person", "name": EDITOR, "url": ORIGIN + "/about/"},
                   "publisher": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
                   "mainEntityOfPage": canon, "wordCount": words},
                  {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                      {"@type": "ListItem", "position": 1, "name": "Guides", "item": ORIGIN + "/guides/"},
                      {"@type": "ListItem", "position": 2, "name": meta["title"], "item": canon}]}]
        write(url.lstrip("/") + "index.html",
              page(f"{meta['title']} | {BRAND}", meta.get("description", meta["title"]), canon, body_html,
                   jsonld, og_type="article"))

    guides.sort(key=lambda g: g[0].get("date", ""), reverse=True)
    cards = "".join(
        f'<a href="{g[2]}">{esc(g[0]["title"])}<small>{esc(g[0].get("description", ""))[:120]} · {esc(g[0].get("date", ""))}</small></a>'
        for g in guides)
    body_html = f"""<div class="hero"><div class="wrap hero-inner"><h1>Buyer's guides</h1>
<p class="sub">Which years to buy and which to walk past — written and signed by the editor, checked against the federal record.</p></div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0">
<div class="card prose editorial">{HUB_NOTES.get("guides", "")}<p class="src-note">Editor: <a href="/about/">{EDITOR}</a> · <a href="/editorial-policy/">editorial policy</a></p></div>
<div class="card"><div class="rel-grid">{cards}</div></div>
</div>"""
    write("guides/index.html", page(f"Used Car Buyer's Guides: Years to Avoid | {BRAND}",
                                    "Signed, dated buyer's guides for the most-searched nameplates: which model years to buy and which to avoid, from the federal complaint and recall record.",
                                    ORIGIN + "/guides/", body_html))
    total = sum(g[4] for g in guides)
    print(f"GUIDES OK: {len(guides)} guides, {total:,} words -> /guides/")


if __name__ == "__main__":
    main()
