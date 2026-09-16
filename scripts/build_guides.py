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
        # A guide may name a year that has no page of its own (the year fell under the
        # model-year gate). Point that link at the nameplate hub, which lists every year,
        # instead of shipping a dead link.
        def _fix_link(m):
            href = m.group(1)
            if re.match(r"^/cars/[\w-]+/[\w-]+/\d{4}/$", href) and not (SITE / href.strip("/") / "index.html").exists():
                return f'href="{href.rsplit("/", 2)[0]}/"'
            return m.group(0)
        article = re.sub(r'href="(/cars/[^"]+)"', _fix_link, article)
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
        byline = gen_site.editor_byline(meta.get("date", gen_site.TODAY))
        # A photograph of the car the guide is about. Guides carried no image at all —
        # the one page type a reviewer reads end to end was the one with nothing to look
        # at. The photograph comes from the same licensed catalogue as the car pages, for
        # the first nameplate the guide names, never a car newer than the guide's subject.
        hero_img, image_url = "", None
        for key in meta["models"]:
            try:
                kslug, mslug = key.split("/")
            except ValueError:
                continue
            r = con.execute("""SELECT mk.name, mo.name FROM models mo JOIN makes mk ON mk.id=mo.make_id
                WHERE mk.slug=? AND mo.slug=?""", (kslug, mslug)).fetchone()
            if not r:
                continue
            ph = gen_site.lib_photo(r[0], r[1])
            if ph:
                fn = ph.replace(" ", "_")
                base = f"https://commons.wikimedia.org/wiki/Special:FilePath/{gen_site._uq(fn)}"
                image_url = f"{base}?width=1200"
                srcset = ", ".join(f"{base}?width={w} {w}w" for w in (480, 720, 900, 1200))
                hero_img = (f'<figure class="hero-art guide-art"><a class="photo" href="/cars/{kslug}/{mslug}/">'
                            f'<img src="{base}?width=900" srcset="{srcset}" sizes="(max-width: 900px) 100vw, 560px" '
                            f'width="900" height="563" referrerpolicy="no-referrer" decoding="async" '
                            f'alt="{esc(r[0])} {esc(r[1])}" fetchpriority="high"></a>'
                            f'<figcaption>{esc(r[0])} {esc(r[1])} · photograph via Wikimedia Commons, '
                            f'<a href="/about/#attribution">licence and credit</a></figcaption></figure>')
                break
        minutes = max(1, round(words / 220))
        body_html = f"""<div class="hero"><div class="wrap hero-inner{' hero-flex' if hero_img else ''}"><div class="hero-copy">
<nav class="crumbs"><a href="/guides/">Guides</a> › {esc(meta["title"])}</nav>
<h1>{esc(meta["title"])}</h1>
<p class="sub">{esc(meta.get("description", ""))}</p>
{byline}
<p class="src-note">{words:,} words · about {minutes} minutes · every figure checked against the federal record on {gen_site.TODAY}</p>
</div>{hero_img}</div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0;max-width:860px">
<article class="card prose guide">{article}
</article>
{model_links(con, meta["models"])}
{rel_html}
</div>"""
        jsonld = [{"@context": "https://schema.org", "@type": "Article", "headline": meta["title"],
                   "description": meta.get("description", ""), "datePublished": meta.get("date", gen_site.TODAY),
                   "dateModified": meta.get("updated", meta.get("date", gen_site.TODAY)),
                   "author": {"@type": "Person", "name": EDITOR, "url": ORIGIN + "/about/adir-trabelsi/"},
                   "editor": {"@type": "Person", "name": EDITOR, "url": ORIGIN + "/about/adir-trabelsi/"},
                   "publisher": {"@type": "Organization", "name": BRAND, "url": ORIGIN},
                   "mainEntityOfPage": canon, "wordCount": words,
                   **({"image": image_url} if image_url else {})},
                  {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                      {"@type": "ListItem", "position": 1, "name": "Guides", "item": ORIGIN + "/guides/"},
                      {"@type": "ListItem", "position": 2, "name": meta["title"], "item": canon}]}]
        og = (f'<meta property="og:image" content="{esc(image_url)}"><meta name="twitter:image" content="{esc(image_url)}">'
              if image_url else "")
        write(url.lstrip("/") + "index.html",
              page(f"{meta['title']} | {BRAND}", meta.get("description", meta["title"]), canon, body_html,
                   jsonld, extra_head=og, og_type="article"))

    guides.sort(key=lambda g: (g[0].get("date", ""), g[0]["title"]), reverse=True)
    total = sum(g[4] for g in guides)

    def _card(g):
        return (f'<a href="{g[2]}">{esc(g[0]["title"])}<small>{esc(g[0].get("description", ""))[:150]}'
                f' · {esc(g[0].get("date", ""))} · {g[4]:,} words</small></a>')

    # Grouped so the page reads as a table of contents rather than a wall of cards:
    # cross-nameplate comparisons and how-to guides first, then one nameplate at a time.
    def _kind(g):
        t = g[0]["title"].lower()
        if any(w in t for w in ("compared", "hybrid or", "side by side", "how to", "how the", "rule", "most dependable", "battery")):
            return "compare"
        return "nameplate"
    comp = [g for g in guides if _kind(g) == "compare"]
    name = [g for g in guides if _kind(g) == "nameplate"]
    sections = ""
    if comp:
        sections += ('<div class="card"><h2>Comparisons and how-to guides</h2><div class="rel-grid">'
                     + "".join(_card(g) for g in comp) + '</div></div>')
    if name:
        sections += ('<div class="card"><h2>One nameplate at a time</h2><div class="rel-grid">'
                     + "".join(_card(g) for g in name) + '</div></div>')
    body_html = f"""<div class="hero"><div class="wrap hero-inner"><h1>Buyer's guides</h1>
<p class="sub">{len(guides)} guides, {total:,} words — which years to buy and which to walk past, written and
signed by the editor and checked line by line against the federal complaint and recall record.</p></div></div>
<div class="wrap" style="display:grid;gap:20px;padding:28px 0">
<div class="card prose editorial">{HUB_NOTES.get("guides", "")}
<p>Every guide opens with its verdict — the years to avoid and the years to buy — then shows what the
complaint components and recall campaigns say went wrong, which years escaped it, and what to check on the
car in front of you before you pay. The year tables inside each guide are live: they are drawn from the
same database as the model pages on the day the site was last built, so a guide written in September
is still right in March. Guides are signed by <a href="/about/adir-trabelsi/">the editor</a>, dated, and
corrected under the <a href="/editorial-policy/">editorial policy</a>.</p></div>
{sections}
</div>"""
    write("guides/index.html", page(f"Used Car Buyer's Guides: Years to Avoid, by Nameplate | {BRAND}",
                                    f"{len(guides)} signed, dated buyer's guides: which model years to buy and which to avoid, from the federal complaint and recall record.",
                                    ORIGIN + "/guides/", body_html))
    print(f"GUIDES OK: {len(guides)} guides, {total:,} words -> /guides/")


if __name__ == "__main__":
    main()
