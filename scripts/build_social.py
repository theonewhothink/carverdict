#!/usr/bin/env python3
"""build_social.py — the daily social factory, and the page you post from.

The old queue wrote seven generic "Car of the Day" captions into a repo folder nobody
opens, with a model count hard-coded two catalogue rebuilds ago. Generic car captions lose
to the thousand accounts already posting generic car captions; the only thing this site has
that they do not is the numbers.

So every package here is built from one real record and leads with the figure: the cost per
mile, the five-year depreciation, the repair bill behind the top complaint cluster, the
worst year of a nameplate people are shopping right now. Three formats a day, seven days
ahead, each with the image, the caption, the hashtags, a spoken script for video and the
link — and all of it on a page that can be opened on a phone and copied out in a minute.

Outputs:
  SOCIAL_QUEUE/queue.json   machine-readable, for whatever posts it
  site/studio/              the human page (noindex) — open, copy, post
  site/follow/              the public link-in-bio page the social profiles point at
"""
import json
import random
import re
import sqlite3
import sys
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = "https://motorjury.com"

HANDLES = [
    ("Instagram", "motorjury", "https://www.instagram.com/motorjury/"),
    ("TikTok", "@motorjury", "https://www.tiktok.com/@motorjury"),
    ("Facebook", "MotorJury", "https://www.facebook.com/motorjury"),
    ("YouTube", "@motorjury", "https://www.youtube.com/@motorjury"),
]

BIO = ("What that car really costs to own. Price, depreciation, repairs, insurance and a "
       "verdict — computed from public NHTSA and EPA data, never opinions.")

TAGS = {
    "instagram": "#usedcars #cartok #carbuying #cardata #carmaintenance #depreciation "
                 "#carsofinstagram #carfacts #carshopping #motorjury",
    "tiktok": "#cartok #usedcars #carbuying #cartips #cardata #carmaintenance #fyp",
    "facebook": "#usedcars #carbuying #cardata #carmaintenance",
}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def money(n):
    return "$" + f"{int(round(n)):,}"


def db():
    con = sqlite3.connect(ROOT / "data" / "cars.sqlite")
    con.row_factory = sqlite3.Row
    return con


def rows(con):
    """Only cars with a real record behind them: a package whose hook is a number needs the
    number to be defensible, and a thin complaint record is not."""
    try:
        return con.execute("""
            SELECT my.id my_id, my.year, my.complaint_count, my.recall_count, my.severe_recalls,
                   mo.name model, mo.slug mslug, mk.name make, mk.slug kslug,
                   cs.reliability_score score, cs.verdict, cs.confidence,
                   p.price_today, p.price_today_low, p.price_today_high, p.depreciation_5y,
                   p.depreciation_per_year, p.insurance_low, p.insurance_high, p.segment,
                   f.annual_fuel_cost, f.mpg_comb
            FROM model_years my
            JOIN models mo ON mo.id = my.model_id
            JOIN makes mk ON mk.id = mo.make_id
            JOIN computed_scores cs ON cs.my_id = my.id
            LEFT JOIN price_estimates p ON p.my_id = my.id
            LEFT JOIN fuel f ON f.my_id = my.id
            WHERE my.complaint_count >= 60 AND cs.confidence IN ('high','medium')
        """).fetchall()
    except sqlite3.OperationalError:
        return []


def top_component(con, my_id):
    # the complaints table stores a per-component tally, not one row per complaint
    r = con.execute("""SELECT component, SUM(count) n FROM complaints WHERE my_id=?
                       GROUP BY component ORDER BY n DESC LIMIT 1""", (my_id,)).fetchone()
    return (r["component"].title(), r["n"]) if r else (None, 0)


def url_of(r):
    return f"{ORIGIN}/cars/{r['kslug']}/{r['mslug']}/{r['year']}/"


def cost_per_mile(r):
    ins = ((r["insurance_low"] or 0) + (r["insurance_high"] or 0)) / 2
    run = (r["annual_fuel_cost"] or 0) + 1400          # fuel + mid maintenance band
    dep = r["depreciation_per_year"] or 0
    return (ins + run + dep) / 12000


def packages(con, all_rows, days=7):
    """Three angles a day, rotated, so the feed never reads as one template."""
    rnd = random.Random(20260825)
    priced = [r for r in all_rows if r["price_today"]]
    worst = {}
    for r in all_rows:
        k = (r["make"], r["model"])
        if k not in worst or (r["score"] or 99) < (worst[k]["score"] or 99):
            worst[k] = r
    worst_list = [r for r in worst.values() if (r["score"] or 99) < 45 and r["complaint_count"] >= 150]
    worst_list.sort(key=lambda r: -(r["complaint_count"] or 0))
    good = [r for r in priced if (r["verdict"] == "BUY" and (r["score"] or 0) >= 80)]
    good.sort(key=lambda r: -(r["complaint_count"] or 0))
    rnd.shuffle(priced)

    out = []
    for i in range(days):
        day = (date.today() + timedelta(days=i)).isoformat()

        # --- angle 1: the cost per mile nobody quotes -------------------------------
        r = priced[i % len(priced)] if priced else None
        if r:
            name = f"{r['year']} {r['make']} {r['model']}"
            cpm = cost_per_mile(r)
            hook = f"A {name} costs about ${cpm:.2f} a mile to own."
            body = (f"Not the sticker. The whole thing:\n"
                    f"• Depreciation {money(r['depreciation_per_year'])} a year\n"
                    f"• Insurance about {money(((r['insurance_low'] or 0) + (r['insurance_high'] or 0)) / 2)} a year\n"
                    f"• Fuel and maintenance on top\n\n"
                    f"Typical price today: {money(r['price_today_low'])}–{money(r['price_today_high'])}.\n"
                    f"Every figure computed from public data, formula published.")
            out.append(pack(day, "cost-per-mile", r, hook, body,
                            script=(f"{hook} Everyone quotes you the price. Nobody quotes you the "
                                    f"{money(r['depreciation_5y'])} it quietly loses over five years, "
                                    f"or the insurance, or the maintenance band. We put all four on one "
                                    f"page and let you type in the price you're actually being asked to "
                                    f"pay. Link's in the bio.")))

        # --- angle 2: the trap year ------------------------------------------------
        if worst_list:
            w = worst_list[(i * 3) % len(worst_list)]
            comp, n = top_component(con, w["my_id"])
            name = f"{w['year']} {w['make']} {w['model']}"
            hook = f"The {w['make']} {w['model']} year to walk away from: {w['year']}."
            body = (f"{w['complaint_count']:,} owner complaints filed with the US safety regulator. "
                    f"{w['recall_count']} recall campaigns"
                    + (f", {w['severe_recalls']} of them safety-critical" if w["severe_recalls"] else "")
                    + ".\n"
                    + (f"Biggest cluster: {comp} — {n} complaints.\n" if comp else "")
                    + f"Score {w['score']}/100. Verdict: {w['verdict']}.\n\n"
                      "Same nameplate, other years, completely different story. That's the whole point.")
            out.append(pack(day, "trap-year", w, hook, body,
                            script=(f"If you're shopping a {w['make']} {w['model']}, skip the {w['year']}. "
                                    f"{w['complaint_count']:,} complaints on the federal record"
                                    + (f", and {n} of them are {comp}. " if comp else ". ")
                                    + "The other years of the same car score far better. We rank every "
                                      "year of every model on the complaint record, not on opinion.")))

        # --- angle 3: the one that actually holds up --------------------------------
        if good:
            g = good[(i * 2) % len(good)]
            name = f"{g['year']} {g['make']} {g['model']}"
            hook = f"{name}: {g['score']}/100, and the data isn't thin."
            body = (f"{g['complaint_count']:,} complaints on record and it still scores {g['score']}. "
                    f"That's the version of a good score that means something — a car nobody complains "
                    f"about because nobody bought it isn't reliable, it's unmeasured.\n\n"
                    f"Typical price today: {money(g['price_today_low'])}–{money(g['price_today_high'])}. "
                    f"About {money(g['depreciation_per_year'])} a year in depreciation.")
            out.append(pack(day, "the-good-one", g, hook, body,
                            script=(f"Here's a used car the data actually likes. The {name}. "
                                    f"{g['complaint_count']:,} complaints on the federal record and it "
                                    f"still scores {g['score']} out of 100, because the score compares a "
                                    f"year against its own nameplate instead of punishing whatever sold "
                                    f"the most. Price today, roughly "
                                    f"{money(g['price_today_low'])} to {money(g['price_today_high'])}.")))
    return out


def pack(day, angle, r, hook, body, script):
    link = url_of(r)
    return {
        "date": day,
        "angle": angle,
        "car": f"{r['year']} {r['make']} {r['model']}",
        "link": link,
        "hook": hook,
        "posts": {
            "instagram": f"{hook}\n\n{body}\n\nFull breakdown → link in bio\n\n{TAGS['instagram']}",
            "tiktok": f"{hook}\n\n{TAGS['tiktok']}",
            "facebook": f"{hook}\n\n{body}\n\n{link}\n\n{TAGS['facebook']}",
        },
        "script": script,
        "image_hint": f"Screen-record the price panel on {link} — the numbers are the visual.",
    }


def studio_page(items):
    """The page the posting actually happens from. Deliberately plain, deliberately noindex,
    and built so every block is one tap to copy on a phone."""
    days = {}
    for it in items:
        days.setdefault(it["date"], []).append(it)

    blocks = ""
    for day, its in sorted(days.items()):
        cards = ""
        for it in its:
            posts = "".join(
                f'<div class="st-post"><div class="st-plat">{plat.title()}'
                f'<button class="st-copy" data-copy="{esc(text)}">Copy</button></div>'
                f'<pre>{esc(text)}</pre></div>'
                for plat, text in it["posts"].items())
            cards += (
                f'<article class="st-card"><h3>{esc(it["hook"])}</h3>'
                f'<p class="st-meta">{esc(it["angle"])} · <a href="{it["link"]}">{esc(it["car"])}</a></p>'
                f'{posts}'
                f'<div class="st-post"><div class="st-plat">Spoken script (video)'
                f'<button class="st-copy" data-copy="{esc(it["script"])}">Copy</button></div>'
                f'<pre>{esc(it["script"])}</pre></div>'
                f'<p class="st-hint">{esc(it["image_hint"])}</p></article>')
        blocks += f'<section class="st-day"><h2>{day}</h2>{cards}</section>'

    handles = "".join(
        f'<li><b>{n}</b> — <a href="{u}" rel="noopener">{esc(h)}</a></li>' for n, h, u in HANDLES)

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Social studio | MotorJury</title>
<link rel="stylesheet" href="/assets/site.css">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
.st-day{{margin:28px 0}}.st-day h2{{font-size:15px;color:var(--faint);letter-spacing:.08em;
text-transform:uppercase;margin-bottom:12px}}
.st-card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;
margin-bottom:14px;box-shadow:var(--shadow)}}
.st-card h3{{font-size:17px;line-height:1.3}}
.st-meta{{font-size:12px;color:var(--faint);margin:4px 0 14px}}
.st-post{{border:1px solid var(--line);border-radius:12px;margin-bottom:10px;overflow:hidden}}
.st-plat{{display:flex;align-items:center;justify-content:space-between;gap:10px;
background:var(--card2);padding:8px 12px;font-size:12px;font-weight:800;letter-spacing:.05em;
text-transform:uppercase;color:var(--muted)}}
.st-copy{{min-height:36px;padding:0 14px;border:1px solid var(--line);border-radius:999px;
background:var(--card);font:inherit;font-size:13px;font-weight:600;cursor:pointer;color:var(--brand)}}
.st-copy.done{{background:var(--good);color:#fff;border-color:var(--good)}}
.st-post pre{{margin:0;padding:12px;white-space:pre-wrap;word-break:break-word;
font:inherit;font-size:14px;color:var(--text)}}
.st-hint{{font-size:12px;color:var(--faint)}}
</style></head><body><a class="skip" href="#content">Skip to content</a>
<main id="content"><div class="wrap" style="padding:28px 0 60px;max-width:760px">
<h1>Social studio</h1>
<p class="sub">Seven days of ready packages, rebuilt every night from the live data. Copy,
post, done. This page is not indexed and not linked from the site.</p>
<div class="card" style="margin:18px 0">
<h2>The accounts</h2><ul style="list-style:none;display:grid;gap:6px;font-size:14px">{handles}</ul>
<h3 style="margin-top:14px">Bio, all four</h3>
<p style="font-size:14px;color:var(--text)">{esc(BIO)}</p>
<p style="font-size:14px;margin-top:8px">Link in bio → <a href="{ORIGIN}/follow/">{ORIGIN}/follow/</a></p>
<p style="font-size:13px;color:var(--faint);margin-top:8px">Profile picture:
<a href="/icon-512.png">icon-512.png</a> · cover / share card:
<a href="/og/default.png">og/default.png</a></p>
</div>
{blocks}
</div></main>
<script>
document.addEventListener('click', function (e) {{
  var b = e.target.closest('.st-copy'); if (!b) return;
  navigator.clipboard.writeText(b.getAttribute('data-copy')).then(function () {{
    b.textContent = 'Copied'; b.classList.add('done');
    setTimeout(function () {{ b.textContent = 'Copy'; b.classList.remove('done'); }}, 1800);
  }});
}});
</script></body></html>"""


def follow_page(model_count, brand_count):
    """The link-in-bio page every social profile points at. One screen, thumb-sized targets,
    no hero image to wait for."""
    links = [
        ("Every car ever made", f"The library — {model_count:,} models from {brand_count:,} marques", "/library/"),
        ("What will it cost me?", "Price, depreciation, insurance and running cost", "/calculators/"),
        ("Today's car quiz", "One car a day, guess it in three clues", "/play/"),
        ("The most-loved cars", "Voted by readers, one vote per account", "/loved/"),
        ("Trap years to avoid", "Ranked on the federal complaint record", "/cars/"),
        ("How the numbers work", "Every formula, published", "/methodology/"),
    ]
    rows_html = "".join(
        f'<a class="fl-link" href="{u}"><b>{esc(t)}</b><span>{esc(d)}</span></a>'
        for t, d, u in links)
    socials = "".join(
        f'<a class="fl-soc" href="{u}" rel="noopener">{n}</a>' for n, _h, u in HANDLES)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>MotorJury — start here</title>
<meta name="description" content="{esc(BIO)}">
<link rel="canonical" href="{ORIGIN}/follow/">
<link rel="stylesheet" href="/assets/site.css">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:title" content="MotorJury"><meta property="og:image" content="{ORIGIN}/og/default.png">
<meta property="og:description" content="{esc(BIO)}">
<style>
.fl{{max-width:520px;margin:0 auto;padding:36px 18px 60px;text-align:center}}
.fl img.avatar{{width:88px;height:88px;border-radius:24px;margin:0 auto 14px}}
.fl h1{{font-size:26px}}
.fl p.bio{{color:var(--muted);font-size:15px;margin:8px 0 22px}}
.fl-link{{display:block;text-align:left;background:var(--card);border:1px solid var(--line);
border-radius:14px;padding:14px 16px;margin-bottom:10px;color:var(--text);min-height:60px}}
.fl-link:hover{{border-color:var(--brand);text-decoration:none}}
.fl-link b{{display:block;font-size:15px}}
.fl-link span{{font-size:13px;color:var(--muted)}}
.fl-socs{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:22px}}
.fl-soc{{min-height:44px;display:inline-flex;align-items:center;padding:0 16px;border-radius:999px;
border:1px solid var(--line);font-size:14px;font-weight:600;color:var(--muted)}}
.fl-soc:hover{{color:var(--brand);border-color:var(--brand);text-decoration:none}}
</style></head><body><main id="content">
<div class="fl">
<img class="avatar" src="/icon-192.png" alt="MotorJury" width="88" height="88">
<h1>MotorJury</h1>
<p class="bio">{esc(BIO)}</p>
{rows_html}
<div class="fl-socs">{socials}</div>
<p style="margin-top:22px;font-size:12px;color:var(--faint)">
<a href="/">motorjury.com</a> · <a href="/methodology/">methodology</a> · <a href="/privacy/">privacy</a></p>
</div></main></body></html>"""


def main():
    con = db()
    all_rows = rows(con)
    if not all_rows:
        print("SOCIAL SKIPPED: no scored rows")
        return 0
    items = packages(con, all_rows)
    con.close()

    q = ROOT / "SOCIAL_QUEUE"
    q.mkdir(exist_ok=True)
    (q / "queue.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))

    (SITE / "studio").mkdir(parents=True, exist_ok=True)
    (SITE / "studio" / "index.html").write_text(studio_page(items))
    (SITE / "follow").mkdir(parents=True, exist_ok=True)
    try:
        from build_library import load_model_index, build_dataset
        load_model_index()
        catalogue = build_dataset()
        model_count = sum(len(v) for v in catalogue.values())
        brand_count = len(catalogue)
    except Exception:
        model_count, brand_count = 0, 0
    (SITE / "follow" / "index.html").write_text(follow_page(model_count, brand_count))
    print(f"SOCIAL OK: {len(items)} packages over 7 days -> /studio/ (noindex) + /follow/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
