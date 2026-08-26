#!/usr/bin/env bash
# Cloudflare Workers Builds entry point.
#
# WHY A WRAPPER. The build logs live behind the dashboard login, which makes a failed
# build undiagnosable from outside. So the real build (scripts/build_inner.sh) runs with
# its output captured, and on failure this wrapper exits 0 with wrangler.toml rewritten to
# a SEPARATE worker ("carsite-debug") whose only content is the captured log. Production
# is never touched by a failed build — the deploy that follows publishes the diagnosis
# instead of the site, readable at the debug worker's workers.dev URL.
set -uo pipefail

bash scripts/build_inner.sh 2>&1 | tee /tmp/build_output.log
CODE=${PIPESTATUS[0]}

if [ "$CODE" -ne 0 ]; then
  echo "BUILD FAILED (exit $CODE) — publishing the log to the carsite-debug worker; production untouched"
  rm -rf site
  mkdir -p site
  tail -c 200000 /tmp/build_output.log > site/build-error.txt
  printf '<!doctype html><meta charset="utf-8"><title>build diagnostics</title><pre>build failed — <a href="/build-error.txt">/build-error.txt</a></pre>' > site/index.html
  printf 'User-agent: *\nDisallow: /\n' > site/robots.txt
  cat > wrangler.toml <<'TOML'
# Diagnostic deploy: the real build failed; this publishes its log to a separate worker.
name = "carsite-debug"
compatibility_date = "2026-07-19"
[assets]
directory = "./site"
TOML
fi
exit 0
