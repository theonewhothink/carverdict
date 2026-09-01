#!/usr/bin/env bash
# Cloudflare Workers Builds entry point. Set as the Worker's build command: bash build.sh
# Deploy command stays: npx wrangler deploy
set -euo pipefail

# Pick an interpreter that actually has sqlite3. The Cloudflare build image's default
# asdf Python (3.13.x) is compiled without _sqlite3, and every generator reads data/cars.sqlite.
PY=""
for CAND in /usr/bin/python3 /usr/bin/python3.12 /usr/bin/python3.11 python3.12 python3.11 python3; do
  if command -v "$CAND" >/dev/null 2>&1 && "$CAND" -c "import sqlite3" >/dev/null 2>&1; then
    PY="$CAND"; break
  fi
done
if [ -z "$PY" ]; then
  echo "FATAL: no Python interpreter with the sqlite3 module is available"; exit 1
fi
echo "python: $PY -> $($PY --version)"

# Pillow drives the 1200x630 Open Graph cards. The distro Python has no pip on this image,
# so bootstrap one; never let a missing image library kill an otherwise good build.
install_pillow() {
  "$PY" -c "import PIL" 2>/dev/null && { echo "pillow: already present"; return 0; }
  # A venv always carries its own pip, even when the distro python ships without one.
  # PYTHONPATH exposes the venv's site-packages to $PY so every generator sees PIL.
  VENV=/tmp/ogvenv
  "$PY" -m venv "$VENV" >/dev/null 2>&1 &&
  "$VENV/bin/pip" install --quiet --disable-pip-version-check pillow >/dev/null 2>&1 && {
    SITE=$(ls -d "$VENV"/lib/python*/site-packages 2>/dev/null | head -1)
    [ -n "$SITE" ] && export PYTHONPATH="$SITE${PYTHONPATH:+:$PYTHONPATH}"
  }
  "$PY" -c "import PIL" 2>/dev/null && return 0
  "$PY" -m pip install --user --quiet --disable-pip-version-check pillow >/dev/null 2>&1 ||
  "$PY" -m pip install --quiet --break-system-packages pillow >/dev/null 2>&1 || return 1
  "$PY" -c "import PIL" 2>/dev/null
}
if install_pillow; then echo "pillow: ready"; else echo "WARNING: pillow unavailable - OG cards will be skipped"; fi

# Canonical origin for canonicals, hreflang, JSON-LD and the sitemap. Point this at the real
# domain (Cloudflare build variable SITE_ORIGIN) the moment one is bought; until then the
# workers.dev hostname is the truth. A placeholder domain in canonical tags is an SEO own-goal.
export SITE_ORIGIN="${SITE_ORIGIN:-https://motorjury.com}"
echo "origin: $SITE_ORIGIN"

# CI has no upload ceiling, but the site file cap is 20,000 and the guides + OG cards need
# headroom: 10,000 library model pages (the rest live on their marque page and in the deep index).
"$PY" - <<'PY_EOF'
import os, re, pathlib
p = pathlib.Path("scripts/build_models.py")
p.write_text(re.sub(r"(?m)^MAX_MODEL_PAGES = .*", "MAX_MODEL_PAGES = 10000", p.read_text()))
print("MAX_MODEL_PAGES set to 10000")

# Some generators still carry the old placeholder origin as a literal. Rewrite it in place so
# every emitted URL agrees with SITE_ORIGIN. No-op once the generators read the variable.
origin, n = os.environ["SITE_ORIGIN"].rstrip("/"), 0
for f in pathlib.Path("scripts").glob("*.py"):
    s = f.read_text()
    if "https://carverdict.example" in s:
        f.write_text(s.replace("https://carverdict.example", origin))
        n += 1
print(f"origin literals rewritten in {n} generator file(s)")
PY_EOF

# The ownership dataset is no longer fetched here. It is fetched nightly by the
# "Ownership data" GitHub Action, which has hours instead of the ~5 minutes this stage could
# afford, and is published as the rolling `data-latest` release asset. This build just
# downloads it. Two things follow: the 20-minute build+deploy cap stops governing how much
# data the site can carry, and coverage compounds night over night instead of resetting to
# whatever one build window could fetch.
#
# The download is advisory. If the asset is missing, stale-URL, or smaller than the database
# committed in the repository, the committed one is kept and the build continues.
DATA_URL="${DATA_URL:-https://github.com/theonewhothink/carverdict/releases/download/data-latest/cars.sqlite}"
if curl -fsSL --max-time 120 -o /tmp/cars.remote.sqlite "$DATA_URL"; then
  "$PY" scripts/adopt_dataset.py /tmp/cars.remote.sqlite
else
  echo "WARNING: published dataset unreachable; building on the committed database"
fi

# The specification files harvested overnight with an hour's budget (Ownership data
# workflow). Downloaded first so the timeboxed harvests below only add to them.
for F in wiki_specs.json car_specs.json; do
  if curl -fsSL --max-time 60 -o "/tmp/$F" "https://github.com/theonewhothink/carverdict/releases/download/data-latest/$F" \
     && [ -s "/tmp/$F" ]; then
    cp "/tmp/$F" "data/$F" && echo "specs: adopted published $F ($(wc -c < data/$F) bytes)"
  else
    echo "specs: no published $F yet"
  fi
done

# vPIC ships one "model" per drivetrain, body and trim combination, which fragments a
# nameplate across half a dozen URLs and targets phrases nobody searches. Fold them onto the
# marketing model name before anything is generated, and record the 301s.
"$PY" scripts/canonicalize_models.py

# Verdicts are recomputed from the raw complaint and recall records on every build, so a
# change to the scoring model reaches production with the next deploy instead of waiting for
# the dataset release to be rebuilt. The model itself lives in scripts/score_model_years.py.
"$PY" scripts/score_model_years.py

# The nightly deep harvest embeds its full Wikidata catalogue inside the dataset;
# adopt it when it is bigger than the committed car_library.json.
"$PY" scripts/extract_library.py || echo "WARNING: catalogue extraction skipped"

# Refresh the catalogue from Wikidata. The committed car_library.json is the floor; this
# adds the classes the first harvest missed (automobile model series, racing automobile
# model - i.e. Cayenne, Boxster, 911, 917, 962). Never fails the build: on a Wikidata
# outage the committed catalogue is used unchanged.
timeout 120 "$PY" scripts/harvest_wikidata.py || echo "WARNING: catalogue refresh skipped or over budget"

# Per-model technical facts (engine, mass, top speed, units built, Commons gallery category).
# Optional: if this fails the model pages simply render without a specifications table.
# IMG_SCORE_BUDGET caps the Commons image-quality pass (Wikidata P18 candidates scored
# against the Commons file record). 90 seconds is the worst case it can add to a build
# that already lands near 15m30s of the 20-minute build+deploy cap; the pass stops on the
# clock and keeps whatever it scored, so a slow Commons day cannot cost the deploy.
# Hard wall-clock bounds on every harvest. The whole build+deploy has a 20-minute cap and
# the last three production builds died on it: the previous budget spent up to 8.5 minutes
# on Wikipedia alone, generation grew with the dataset, and the first (cache-cold) build of
# every push tipped over the cap — which is why even the currently-live commit only
# deployed on a manual retry. Freshness compounds nightly; a failed deploy compounds nothing.
IMG_SCORE_BUDGET="${IMG_SCORE_BUDGET:-30}" timeout 150 "$PY" scripts/harvest_specs.py || echo "WARNING: specification refresh skipped or over budget"

# Real specifications — engine, power output, production years, kerb weight, transmission,
# layout, assembly — parsed from Wikipedia infoboxes (CC BY-SA). Batched 50 pages per
# request, so the whole catalogue costs ~700 calls rather than 17,000.
WIKI_SPECS_BUDGET="${WIKI_SPECS_BUDGET:-90}" timeout 150 "$PY" scripts/harvest_wiki_specs.py || echo "WARNING: infobox specification refresh skipped or over budget"

# The ownership-price layer: what the car cost new, what it is worth now, what it will be
# worth in five years and what it costs to insure. Runs after the wiki harvest so a
# published MSRP can anchor the estimate, and before every generator, because the price
# card, the verdict card and the calculator all read the same table.
"$PY" scripts/price_model.py

# Every model-year gets a fuel figure: EPA's, else the nearest EPA-covered year of the same
# nameplate, else the segment mean — written into the database with its provenance so all
# generators agree and every page labels the estimate. Fixes the "fuel unavailable" holes.
"$PY" scripts/fill_fuel.py

# The mark and the whole icon set, drawn from one definition so the favicon, the app icons
# and the default social card can never drift apart again.
"$PY" scripts/make_icons.py || echo "WARNING: icon generation skipped"

# Resolve the Legends roster before gen_site runs, so the home page knows whether the
# /legends/ section can be linked. The pages themselves are written after gen_site, which
# wipes site/ on every run.
timeout 90 "$PY" scripts/build_people.py --harvest-only || echo "WARNING: legends roster unavailable"

# Build order matters: gen_site.py clears site/, and the --plan pass decides which
# models get their own page so sibling links can never point at a missing page.
"$PY" scripts/build_models.py --plan
"$PY" scripts/gen_site.py
"$PY" scripts/build_models.py
"$PY" scripts/build_library.py
"$PY" scripts/build_engage.py
"$PY" scripts/build_events.py || echo "WARNING: events calendar skipped"
"$PY" scripts/build_stories.py || echo "WARNING: data stories skipped"
"$PY" scripts/build_problems.py || echo "WARNING: problems pages skipped"

# The written layer: signed, dated buyer's guides from data/guides/*.md. Runs after the
# model pages exist so every year table and model link resolves. A missing guide is a
# build failure, not a warning: these pages are the site's answer to AdSense's
# "low value content" finding and must never silently drop out of a deploy.
"$PY" scripts/build_guides.py
"$PY" scripts/build_people.py --from-cache || echo "WARNING: legends section skipped"

# The social factory: seven days of data-backed packages, the /studio/ page they are posted
# from, and the /follow/ link-in-bio page the profiles point at. Runs before the localiser
# so /follow/ enters the sitemap and /studio/, being noindex, does not.
"$PY" scripts/build_social.py || echo "WARNING: social factory skipped"

"$PY" scripts/localize.py

# One normalising pass over every page: icons, the correct theme-colour pair, social
# cards, de-duplicated hreflang, and the <main>/skip-link landmarks. Nine generators each
# have their own HTML shell, so this is the only place that can cover all of them.
"$PY" scripts/polish.py

# Google AdSense + Google Analytics 4: one auto-ads loader and one gtag.js snippet in
# every page head, plus ads.txt at the root. The AdSense loader is inert until approval
# lands; overlay formats (anchor, vignette) are disabled account-side so mobile screens
# are never covered. GA4 property: MotorJury (account GENIUSES.CLUB), stream 15473007218.
export ADS_CLIENT="${ADS_CLIENT:-ca-pub-6675837012921030}"
export GA4_ID="${GA4_ID:-G-SD0YYNQ19N}"
"$PY" - <<'PY_EOF'
import glob, os
ads = ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
       '?client=%s" crossorigin="anonymous"></script>' % os.environ["ADS_CLIENT"])
# Google Consent Mode v2. Everything starts DENIED, and the certified consent message
# (AdSense -> Privacy & messaging) is what grants it. Without this block the tags fire on
# European visitors before anyone has agreed to anything - a GDPR exposure, and the reason
# Google restricts EEA ad serving for publishers with no working CMP.
consent = ("<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}"
           "gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',"
           "ad_personalization:'denied',analytics_storage:'denied',"
           "functionality_storage:'granted',security_storage:'granted',wait_for_update:2000});"
           "gtag('set','ads_data_redaction',true);gtag('set','url_passthrough',true);</script>")
ga = ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>'
      '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
      "gtag('js',new Date());gtag('config','%s',{anonymize_ip:true});</script>"
      % (os.environ["GA4_ID"], os.environ["GA4_ID"]))
n = 0
for p in glob.glob('site/**/*.html', recursive=True):
    s = open(p).read()
    if '<head>' not in s:
        continue
    tag = ('' if "gtag('consent'" in s else consent) \
        + ('' if 'adsbygoogle.js' in s else ads) \
        + ('' if 'googletagmanager.com/gtag' in s else ga)
    if not tag:
        continue
    open(p, 'w').write(s.replace('<head>', '<head>' + tag, 1))
    n += 1
open('site/ads.txt', 'w').write('google.com, %s, DIRECT, f08c47fec0942fa0\n'
                                % os.environ["ADS_CLIENT"].replace('ca-pub-', 'pub-'))
print(f"ADSENSE+GA4 OK: tags injected into {n} pages + ads.txt")
PY_EOF

# Final-output accessibility and structure gate. A template mistake multiplies across
# thousands of pages, so duplicate ids, missing landmarks/headings, non-semantic lightbox
# links, missing image text or placeholder zero prices must stop the deploy.
"$PY" scripts/qa_site.py

# Gate: the links the BROWSER builds must resolve too.
# The static gate below only ever saw href="" in the HTML. Half of this site's navigation is
# built client-side from JSON — the search box, the daily picks, the marque grids — and that
# half was linking a model URL for every model in the catalogue while only half the models
# had a page. That is where the site's 404s came from: 7,992 of 16,235 search results.
"$PY" - <<'PY_EOF'
import json, os, re, sys

def mslug(s):
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:60] or "x"

def exists(u):
    return os.path.exists("site" + u) or os.path.exists(("site" + u).rstrip("/") + "/index.html")

bad = 0
checked = 0
lib = json.load(open("site/assets/library-data.json"))
for brand, v in lib.items():
    if not exists("/library/%s/" % v["s"]):
        print("DEAD marque page:", v["s"]); bad += 1
    for m in v["m"]:
        checked += 1
        # m[3] is the has-page flag; a model without one is linked to its marque page
        if len(m) > 3 and m[3] and not exists("/library/%s/%s/" % (v["s"], mslug(m[0]))):
            if bad < 10:
                print("DEAD search target:", v["s"], m[0])
            bad += 1
pool = json.load(open("site/assets/daily-pool.json"))
for r in pool:
    checked += 1
    if not exists("/library/%s/%s/" % (r[2], mslug(r[0]))):
        if bad < 10:
            print("DEAD daily pick:", r[0])
        bad += 1
print(f"client-side link targets checked={checked} dead={bad}")
if bad:
    sys.exit(1)
PY_EOF

# Gate: a dead internal link must never reach production.
"$PY" - <<'PY_EOF'
import re, os, glob, sys
pages = glob.glob('site/**/*.html', recursive=True)
hrefs = set()
# Quote-agnostic. The old pattern matched double quotes only, so it was blind to every
# link the model-page generator writes with single quotes - which is where all of the
# 404s that reached production came from.
PAT = re.compile(r"""href=(?:"(/[^"#?]*)"|'(/[^'#?]*)')""")
for p in pages:
    for a, b in PAT.findall(open(p).read()):
        hrefs.add(a or b)
skip = ('/api', '/assets', '/cdn-cgi', '/og/')
allow = {'/sitemap.xml', '/llms.txt', '/robots.txt', '/ads.txt', '/favicon.ico',
         '/favicon.svg', '/site.webmanifest', '/mask-icon.svg', '/apple-touch-icon.png'}
dead = [u for u in hrefs
        if not (os.path.exists('site' + u) or os.path.exists(('site' + u).rstrip('/') + '/index.html'))
        and not u.startswith(skip) and u not in allow]
files = sum(len(f) for _, _, f in os.walk('site'))
print(f"pages={len(pages)} files={files} links={len(hrefs)} dead={len(dead)}")
if dead:
    print("DEAD:", dead[:20])
if files > 19800:
    print("ABORT: over the 20,000 static-asset cap"); sys.exit(1)
if files > 19000:
    # visible in every published build log: the nightly dataset growth is eating the
    # remaining headroom, and MAX_MODEL_PAGES needs lowering (or pages need to go dynamic)
    # BEFORE the abort above starts rejecting deploys.
    print(f"WARNING: {files} files - within 800 of the static-asset abort; reduce MAX_MODEL_PAGES soon")
if dead:
    sys.exit(1)
PY_EOF

# IndexNow: instant URL submission to Bing, Yandex, Seznam and Naver (DuckDuckGo serves
# from Bing's index). The key file must be served from the site root for the engines to
# verify ownership; it goes live with this same deploy, and every nightly build re-pings,
# so the first ping after any key change self-heals. Google ignores IndexNow — Search
# Console already carries the sitemap there. Never fails the build.
export INDEXNOW_KEY="${INDEXNOW_KEY:-b7e4f2c8a91d4e6f8c3b5a2d7f9e1c04}"
printf '%s' "$INDEXNOW_KEY" > "site/$INDEXNOW_KEY.txt"
"$PY" - <<'PY_EOF' || echo "WARNING: IndexNow ping skipped"
import json, os, re, urllib.request
urls = re.findall(r"<loc>([^<]+)</loc>", open("site/sitemap-0.xml").read())[:10000]
body = json.dumps({"host": "motorjury.com", "key": os.environ["INDEXNOW_KEY"],
                   "keyLocation": "https://motorjury.com/%s.txt" % os.environ["INDEXNOW_KEY"],
                   "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                             headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"INDEXNOW OK: {len(urls)} urls submitted (HTTP {r.status})")
except Exception as e:
    print(f"WARNING: IndexNow ping failed ({e}); key file still deployed")
PY_EOF

node --test workers/calc.test.mjs workers/hub.test.mjs workers/oauth.test.mjs workers/gis.test.mjs workers/vin.test.mjs
echo "build complete"
