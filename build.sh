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
  "$PY" -m pip --version >/dev/null 2>&1 || "$PY" -m ensurepip --user >/dev/null 2>&1 || {
    curl -sSfL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py 2>/dev/null &&
    "$PY" /tmp/get-pip.py --user --quiet >/dev/null 2>&1
  }
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

# Rebuild the ownership dataset from NHTSA and EPA. This is the substance of the site:
# complaint volumes, recall campaigns and real fuel economy for thousands of model-years,
# fetched fresh on every deploy. It refuses to overwrite the committed database with a
# smaller or emptier one, so a bad API day leaves the last good data in place.
# 1,100 model-years costs about four minutes of the twenty-minute build window, which leaves
# room for the Wikidata and Wikipedia harvests. Raise it only if the build finishes early.
# Cloudflare kills the Building stage at 20 minutes. 1,100 model-years cost 10 of them and
# the rest of the pipeline needs 12, so the build died at the cap. 450 fits: ingest ~5 min,
# still 28x the old seed, and the round-robin keeps the most-searched cars covered first.
# The 20-minute clock covers build AND deploy. 450 model-years left the deploy only ~3
# minutes and it was killed mid-upload. 200 keeps the whole run near 16 minutes: still
# 12x the old seed, and the budget can rise once a deploy lands and uploads shrink to diffs.
INGEST_BUDGET="${INGEST_BUDGET:-200}" "$PY" scripts/ingest_scale.py || echo "WARNING: ingest skipped, using committed dataset"

# Refresh the catalogue from Wikidata. The committed car_library.json is the floor; this
# adds the classes the first harvest missed (automobile model series, racing automobile
# model - i.e. Cayenne, Boxster, 911, 917, 962). Never fails the build: on a Wikidata
# outage the committed catalogue is used unchanged.
"$PY" scripts/harvest_wikidata.py || echo "WARNING: catalogue refresh skipped"

# Per-model technical facts (engine, mass, top speed, units built, Commons gallery category).
# Optional: if this fails the model pages simply render without a specifications table.
"$PY" scripts/harvest_specs.py || echo "WARNING: specification refresh skipped"

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
