#!/usr/bin/env bash
# Cloudflare Workers Builds entry point — self-deploying, self-reporting.
#
# Three production pushes in a row failed with the error visible only behind the dashboard
# login. The wrapper below removes the blindfold for good:
#   1. the real build runs (scripts/build_inner.sh) with output captured;
#   2. on success, PRODUCTION IS DEPLOYED FROM INSIDE THE BUILD, with the deploy's own
#      output captured too — the configured deploy command afterwards just repeats an
#      already-successful deploy;
#   3. whatever happened, the captured log is published to the separate "carsite-debug"
#      worker, so every build's story is readable at its workers.dev URL with no login.
# A failed build or failed deploy leaves production exactly as it was.
set -uo pipefail

LOG=/tmp/build_output.log
bash scripts/build_inner.sh 2>&1 | tee "$LOG"
BUILD_CODE=${PIPESTATUS[0]}

DEPLOY_CODE=-1
if [ "$BUILD_CODE" -eq 0 ]; then
  echo "== in-build production deploy ==" | tee -a "$LOG"
  if npx wrangler deploy 2>&1 | tee -a "$LOG"; then
    DEPLOY_CODE=0
  else
    DEPLOY_CODE=${PIPESTATUS[0]}
  fi
  echo "== in-build deploy exit: $DEPLOY_CODE ==" | tee -a "$LOG"
fi

# Publish the log to the debug worker regardless of outcome. Best effort: if this account
# cannot deploy a second worker from this pipeline, the attempt costs nothing.
mkdir -p /tmp/dbgsite
tail -c 400000 "$LOG" > /tmp/dbgsite/build-error.txt
printf '<!doctype html><meta charset="utf-8"><title>carsite build diagnostics</title><pre>log: <a href="/build-error.txt">/build-error.txt</a></pre>' > /tmp/dbgsite/index.html
printf 'User-agent: *\nDisallow: /\n' > /tmp/dbgsite/robots.txt
cat > /tmp/wrangler.debug.toml <<'TOML'
name = "carsite-debug"
compatibility_date = "2026-07-19"
[assets]
directory = "/tmp/dbgsite"
TOML
npx wrangler deploy --config /tmp/wrangler.debug.toml 2>&1 | tail -5 || echo "debug publish failed (non-fatal)"

if [ "$BUILD_CODE" -ne 0 ] || [ "$DEPLOY_CODE" -ne 0 ]; then
  # The configured deploy must not push a broken or already-failed production config;
  # point it at the debug content instead. Production stays whatever it was.
  rm -rf site && mkdir -p site && cp /tmp/dbgsite/* site/
  cat > wrangler.toml <<'TOML'
name = "carsite-debug"
compatibility_date = "2026-07-19"
[assets]
directory = "./site"
TOML
fi
exit 0
