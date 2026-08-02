#!/usr/bin/env bash
# Cloudflare Workers Builds entry point. Set as the Worker's build command: bash build.sh
# Deploy command stays: npx wrangler deploy
set -euo pipefail

echo "python: $(python3 --version)"

# Pillow is only needed for the 1200x630 Open Graph cards; the build must not die without it.
python3 -m pip install --quiet --disable-pip-version-check pillow \
  || python3 -m pip install --quiet --break-system-packages pillow \
  || echo "WARNING: pillow unavailable - OG cards will be skipped"

# CI has no upload ceiling, so publish the complete catalogue (site file cap is 20,000).
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("scripts/build_models.py")
p.write_text(re.sub(r"(?m)^MAX_MODEL_PAGES = .*", "MAX_MODEL_PAGES = 15300", p.read_text()))
print("MAX_MODEL_PAGES set to 15300")
PY

# Build order matters: gen_site.py clears site/, and the --plan pass decides which
# models get their own page so sibling links can never point at a missing page.
python3 scripts/build_models.py --plan
python3 scripts/gen_site.py
python3 scripts/build_models.py
python3 scripts/build_library.py
python3 scripts/build_engage.py
python3 scripts/localize.py

# Gate: a dead internal link must never reach production.
python3 - <<'PY'
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
PY

node --test workers/calc.test.mjs
echo "build complete"
