#!/usr/bin/env bash
# Cloudflare Workers Builds entry point. The production deploy is done inside the build so
# its failure is visible and stops the pipeline. Never deploy a diagnostic worker from this
# connected build: Cloudflare can attach that second deployment to the custom domain and
# replace the real site even after production deployed successfully.
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

if [ "$BUILD_CODE" -ne 0 ] || [ "$DEPLOY_CODE" -ne 0 ]; then
  echo "build or deploy failed; refusing to replace the current production Worker"
  exit 1
fi
exit 0
