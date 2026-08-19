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
export SITE_ORIGIN="${SITE_ORIGIN:-https://carsite.adir-073.workers.dev}"
echo "origin: $SITE_ORIGIN"

# CI has no upload ceiling, so publish the complete catalogue (site file cap is 20,000).
"$PY" - <<'PY_EOF'
import os, re, pathlib
p = pathlib.Path("scripts/build_models.py")
p.write_text(re.sub(r"(?m)^MAX_MODEL_PAGES = .*", "MAX_MODEL_PAGES = 17500", p.read_text()))
print("MAX_MODEL_PAGES set to 17500")

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

# Refresh the catalogue from Wikidata. The committed car_library.json is the floor; this
# adds the classes the first harvest missed (automobile model series, racing automobile
# model - i.e. Cayenne, Boxster, 911, 917, 962). Never fails the build: on a Wikidata
# outage the committed catalogue is used unchanged.
"$PY" scripts/harvest_wikidata.py || echo "WARNING: catalogue refresh skipped"

# Per-model technical facts (engine, mass, top speed, units built, Commons gallery category).
# Optional: if this fails the model pages simply render without a specifications table.
# IMG_SCORE_BUDGET caps the Commons image-quality pass (Wikidata P18 candidates scored
# against the Commons file record). 90 seconds is the worst case it can add to a build
# that already lands near 15m30s of the 20-minute build+deploy cap; the pass stops on the
# clock and keeps whatever it scored, so a slow Commons day cannot cost the deploy.
IMG_SCORE_BUDGET="${IMG_SCORE_BUDGET:-90}" "$PY" scripts/harvest_specs.py || echo "WARNING: specification refresh skipped"

# Real specifications — engine, power output, production years, kerb weight, transmission,
# layout, assembly — parsed from Wikipedia infoboxes (CC BY-SA). Batched 50 pages per
# request, so the whole catalogue costs ~700 calls rather than 17,000.
"$PY" scripts/harvest_wiki_specs.py || echo "WARNING: infobox specification refresh skipped"

# Resolve the Legends roster before gen_site runs, so the home page knows whether the
# /legends/ section can be linked. The pages themselves are written after gen_site, which
# wipes site/ on every run.
"$PY" scripts/build_people.py --harvest-only || echo "WARNING: legends roster unavailable"

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
"$PY" scripts/build_people.py --from-cache || echo "WARNING: legends section skipped"
"$PY" scripts/localize.py

# Gate: a dead internal link must never reach production.
"$PY" - <<'PY_EOF'
import re, os, glob, sys
pages = glob.glob('site/**/*.html', recursive=True)
hrefs = set()
for p in pages:
    hrefs.update(re.findall(r'href="(/[^"#?]*)"', open(p).read()))
skip = ('/api', '/assets', '/cdn-cgi')
allow = {'/sitemap.xml', '/llms.txt', '/robots.txt', '/ads.txt'}
dead = [u for u in hrefs
        if not (os.path.exists('site' + u) or os.path.exists(('site' + u).rstrip('/') + '/index.html'))
        and not u.startswith(skip) and u not in allow]
files = sum(len(f) for _, _, f in os.walk('site'))
print(f"pages={len(pages)} files={files} links={len(hrefs)} dead={len(dead)}")
if files > 19800:
    print("ABORT: over the 20,000 static-asset cap"); sys.exit(1)
if dead:
    print("DEAD:", dead[:20]); sys.exit(1)
PY_EOF

node --test workers/calc.test.mjs
echo "build complete"
