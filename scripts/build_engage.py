#!/usr/bin/env python3
"""build_engage.py — engagement surfaces:
  /play/            Car of the Day + Car of the Week + daily Guess-the-Car + streak
  /garage/          saved cars + recently viewed (device-local, no account)
  /superlatives/    most expensive, rarest, fastest, oldest — data-backed lists
  /notify/          notification + curated-content preference centre (local, opt-in)
Also emits SOCIAL_QUEUE/ posts for the auto-poster (TikTok/IG/X/LinkedIn).
"""
import json, os, sys, random, html
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import LANGS, RTL, t

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://carsite.adir-073.workers.dev").rstrip("/")
BRAND = "CarVerdict"
LIB = json.load(open(ROOT / "data" / "car_library.json"))

# curated, sourced superlatives (facts verifiable; each row cites where the claim comes from)
SUPERLATIVES = {
    "Most expensive cars ever sold at auction": [
        ("1955 Mercedes-Benz 300 SLR Uhlenhaut Coupé", "$142M", "RM Sotheby's private sale, 2022"),
        ("1962 Ferrari 250 GTO", "$48.4M", "RM Sotheby's Monterey, 2018"),
        ("1955 Ferrari 410 Sport Spider", "$22M", "RM Sotheby's, 2022"),
        ("1957 Ferrari 335 S Spider Scaglietti", "$35.7M", "Artcurial Paris, 2016"),
    ],
    "Rarest production cars": [
        ("Ferrari 250 GTO", "36 built", "1962–64 production run"),
        ("Bugatti Royale", "6 built", "1927–33, three sold new"),
        ("Aston Martin Bulldog", "1 built", "1979 concept, never produced"),
        ("Lamborghini Veneno Coupé", "4 built", "2013, incl. prototype"),
    ],
    "Cars that defined an era": [
        ("Ford Model T", "16.5M built", "1908–27, first mass-market car"),
        ("Volkswagen Beetle (Type 1)", "21.5M built", "longest single-platform run"),
        ("Toyota Corolla", "50M+ built", "best-selling nameplate ever"),
        ("Mini (classic)", "5.3M built", "1959–2000, transverse-FWD blueprint"),
    ],
}


def esc(s):
    return html.escape(str(s), quote=True)


def shell(lang, title, desc, path, body, extra_js=""):
    d = ' dir="rtl"' if lang in RTL else ""
    pre = "" if lang == "en" else f"/{lang}"
    canon = ORIGIN + pre + path
    hre = "".join(f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}{"" if l=="en" else "/"+l}{path}">' for l in LANGS)
    return f"""<!doctype html><html lang="{lang}"{d}><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0B0D10"><title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/site.css">{hre}</head><body>
<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="{pre or '/'}">Car<em>Verdict</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="{esc(t(lang,'search_ph'))}" autocomplete="off" aria-label="search" data-none="{esc(t(lang,'search_none'))}"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/cars/">{t(lang,'nav_browse')}</a><a href="/library/">{t(lang,'nav_library')}</a><a href="/events/">Events</a><a href="/play/" class="cur">Play</a><a href="/calculators/">{t(lang,'nav_calculators')}</a></nav>
<details class="langs"><summary>{lang.upper()}</summary><div>{''.join(f'<a{" class=cur" if l==lang else ""} href="{"/" if l=="en" else "/"+l+"/"}">{l.upper()}</a>' for l in LANGS)}</div></details>
</div></header>
<div class="geo-bar wrap" data-geo-chip></div>
{body}
<footer><div class="wrap"><p>{t(lang,'footer_data')} · <a href="/methodology/">{t(lang,'nav_methodology')}</a> · <a href="/notify/">Preferences</a></p></div></footer>
<script src="/assets/site.js" defer></script>
<script src="/assets/lightbox.js" defer></script><script src="/assets/geo.js" defer></script>
<script src="/assets/engage.js" defer></script>{extra_js}</body></html>"""


def write(rel, html_str):
    p = SITE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str)


def play_page(lang="en"):
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>Play</h1><p class="sub">A new car every day, a new quiz every day. Build your streak.</p></div></div>
<div class="wrap">
<div class="card game-card" data-game><p class="muted">Loading today's game…</p></div>
<h2 class="sec">Today's picks</h2>
<p class="muted" style="margin:-6px 0 12px">Not part of the game — two cars worth a look.</p>
<div class="daily-grid" data-daily></div>
<div class="card"><h2>Keep your streak</h2>
<p class="muted">Your streak, saved cars and preferences live on this device only — no account, no email required.
Want a daily nudge? <a href="/notify/">Turn on reminders</a>.</p></div>
<h2 class="sec">Explore the extremes</h2>
<div class="rel-grid"><a href="/superlatives/">Most expensive · rarest · era-defining<small>data-backed lists</small></a>
<a href="/library/">Every model ever made<small>{len(LIB):,} cars</small></a>
<a href="/garage/">My Garage<small>your saved cars</small></a></div>
</div>"""
    write("play/index.html", shell(lang, f"Play — Car of the Day & Guess the Car | {BRAND}",
          "A new Car of the Day, a daily Guess-the-Car quiz, and streaks. Free, no account.", "/play/", body))


def garage_page(lang="en"):
    body = """<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>My Garage</h1><p class="sub">Saved cars and recent views — stored on this device.</p></div></div>
<div class="wrap"><div class="card" data-garage-list></div>
<div class="card"><h2>Recently viewed</h2><div id="recent" class="rel-grid"></div></div></div>
<script>document.addEventListener('DOMContentLoaded',function(){var p={};try{p=JSON.parse(localStorage.getItem('cv_prefs')||'{}')}catch(e){}
var r=(p.recent||[]);document.getElementById('recent').innerHTML=r.length?r.map(function(x){return '<a href="'+x.u+'">'+x.t+'<small>viewed</small></a>'}).join(''):'<p class="muted">No history yet.</p>';});</script>"""
    write("garage/index.html", shell(lang, f"My Garage | {BRAND}", "Your saved cars and recent views.", "/garage/", body))


def superlatives_page(lang="en"):
    photos = {x["n"].lower(): x["p"] for x in LIB if x.get("p")}

    def pic(name):
        for k, v in photos.items():
            if name.split("(")[0].strip().lower() in k:
                return ('<img src="https://commons.wikimedia.org/wiki/Special:FilePath/'
                        + v.replace(" ", "_") + '?width=560" alt="' + esc(name) + '" loading="lazy">')
        return ""

    blocks = ""
    for title, rows in SUPERLATIVES.items():
        cards = "".join(
            f'<div class="sup-card">{pic(n)}<div class="sup-b"><b>{esc(n)}</b>'
            f'<span class="sup-v">{esc(v)}</span><small>{esc(src)}</small></div></div>'
            for n, v, src in rows)
        blocks += f'<h2 class="sec">{esc(title)}</h2><div class="sup-grid">{cards}</div>'
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>The extremes</h1><p class="sub">Most expensive, rarest, era-defining — every figure with its source.</p></div></div>
<div class="wrap">{blocks}
<p class="lib-note">Auction results as reported by the auction houses; production counts from manufacturer records.
Photos: Wikimedia Commons.</p></div>"""
    write("superlatives/index.html", shell(lang, f"Most Expensive, Rarest & Era-Defining Cars | {BRAND}",
          "The most expensive cars ever sold, the rarest production cars, and the models that defined eras — with sources.",
          "/superlatives/", body))


def notify_page(lang="en"):
    body = """<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>Your preferences</h1><p class="sub">Curated content, reminders and ad relevance — all opt-in, all on this device.</p></div></div>
<div class="wrap"><div class="card"><h2>Interests</h2>
<div id="int" class="chips"></div>
<h2 style="margin-top:22px">Daily reminder</h2>
<p class="muted">Browser notification when the new Car of the Day and quiz go live.</p>
<button id="notify" class="btn">Enable reminders</button>
<h2 style="margin-top:22px">Ad personalisation</h2>
<label class="sw"><input type="checkbox" id="ads"> Use my interests to choose more relevant ads (no personal data leaves this device)</label>
<h2 style="margin-top:22px">Data</h2>
<button id="wipe" class="btn ghost">Erase everything stored on this device</button></div></div>
<script>
(function(){var K='cv_prefs';function P(){try{return JSON.parse(localStorage.getItem(K)||'{}')}catch(e){return{}}}
function S(p){localStorage.setItem(K,JSON.stringify(p))}
var TAGS=['EV','SUV','Trucks','Classics','Japanese','German','Budget','Performance'];
function draw(){var p=P();p.tags=p.tags||[];document.getElementById('int').innerHTML=TAGS.map(function(t){
return '<button class="chip'+(p.tags.indexOf(t)>-1?' on':'')+'" data-t="'+t+'">'+t+'</button>'}).join('');
document.querySelectorAll('.chip').forEach(function(b){b.onclick=function(){var p=P();p.tags=p.tags||[];
var i=p.tags.indexOf(b.dataset.t);i>-1?p.tags.splice(i,1):p.tags.push(b.dataset.t);S(p);draw()}});
document.getElementById('ads').checked=!!p.adsPersonal;}
draw();
document.getElementById('ads').onchange=function(e){var p=P();p.adsPersonal=e.target.checked;S(p)};
document.getElementById('notify').onclick=function(){if(!('Notification' in window))return alert('Not supported here');
Notification.requestPermission().then(function(s){var p=P();p.notify=(s==='granted');S(p);
document.getElementById('notify').textContent=p.notify?'Reminders on ✓':'Blocked by browser'})};
document.getElementById('wipe').onclick=function(){localStorage.clear();location.reload()};
})();
</script>"""
    write("notify/index.html", shell(lang, f"Preferences & Notifications | {BRAND}",
          "Choose your interests, enable daily reminders, control ad personalisation. Nothing leaves your device.",
          "/notify/", body))


def social_queue():
    """Generate ready-to-post packages for the auto-poster (7 days x 3 platforms)."""
    q = ROOT / "SOCIAL_QUEUE"
    q.mkdir(exist_ok=True)
    photos = [x for x in LIB if x.get("p")]
    rnd = random.Random(20260719)
    out = []
    for i in range(7):
        day = date.today() + timedelta(days=i)
        car = rnd.choice(photos)
        img = "https://commons.wikimedia.org/wiki/Special:FilePath/" + car["p"].replace(" ", "_") + "?width=1200"
        out.append({
            "date": day.isoformat(),
            "slot": "09:00",
            "asset": img,
            "credit": "Photo: Wikimedia Commons",
            "posts": {
                "instagram": f"Car of the Day: {car['n']}\n\nEvery model ever made — with the ownership data most sites won't show you.\nLink in bio → carverdict\n\n#cars #{(car['m'] or 'auto').replace(' ', '')} #carsofinstagram #cardata",
                "tiktok": f"POV: you're about to buy a {car['n']} — here's what NHTSA complaint data actually says. 🚗📊 #cartok #cars #cardata #usedcars",
                "x": f"Car of the Day: {car['n']}.\n\nWe indexed 12,747 models and every NHTSA complaint we could get. Which years are traps? →",
                "linkedin": f"Car of the Day: {car['n']}.\n\nWe built an open, sourced dataset of vehicle ownership costs — NHTSA complaints, recalls, EPA economy, regional fuel and energy prices — and published the methodology. Data over opinions.",
            },
            "cta": f"{ORIGIN}/play/",
        })
    (q / "queue.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return len(out)


def main():
    for fn in (play_page, garage_page, superlatives_page, notify_page):
        fn("en")
    n = social_queue()
    # ship the geo table to the site
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "geo-prices.json").write_text((ROOT / "data" / "geo_prices.json").read_text())
    print(f"ENGAGE OK: /play/ /garage/ /superlatives/ /notify/ + geo-prices.json + {n} social packages")


if __name__ == "__main__":
    main()
