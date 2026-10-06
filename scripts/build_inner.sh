#!/usr/bin/env bash
# Build only. Production deployment is controlled by build.sh; preview never deploys.
set -euo pipefail
PY="${MOTORJURY_PYTHON:-}"
if [ -z "$PY" ]; then
  for candidate in /usr/bin/python3 /usr/bin/python3.12 /usr/bin/python3.11 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sqlite3' >/dev/null 2>&1; then
      PY="$candidate"; break
    fi
  done
fi
if [ -z "$PY" ]; then echo 'No Python interpreter with SQLite is available'; exit 1; fi
if ! "$PY" -c 'import PIL' >/dev/null 2>&1; then
  "$PY" -m venv /tmp/motorjury-image-runtime
  /tmp/motorjury-image-runtime/bin/pip install --quiet --disable-pip-version-check pillow
  image_site=$(/tmp/motorjury-image-runtime/bin/python -c 'import site; print(site.getsitepackages()[0])')
  export PYTHONPATH="$image_site${PYTHONPATH:+:$PYTHONPATH}"
fi
export SITE_ORIGIN="${SITE_ORIGIN:-https://motorjury.com}"
export MOTORJURY_PREVIEW="${MOTORJURY_PREVIEW:-0}"
if [ -n "${MOTORJURY_DATA_FILE:-}" ]; then
  "$PY" scripts/adopt_dataset.py "$MOTORJURY_DATA_FILE"
else
  DATA_URL="${DATA_URL:-https://github.com/theonewhothink/carverdict/releases/download/data-latest/cars.sqlite}"
  if curl -fsSL --max-time 90 -o /tmp/motorjury-dataset.sqlite "$DATA_URL"; then
    "$PY" scripts/adopt_dataset.py /tmp/motorjury-dataset.sqlite
  else
    echo "Dataset unavailable; retaining the existing snapshot."
  fi
fi
if [ ! -d node_modules/@anthropic-ai/sdk ]; then
  npm install --no-save --no-package-lock --no-audit --no-fund --ignore-scripts @anthropic-ai/sdk@0.128.0
fi
# Imported encyclopedia harvests and automatic catalogue expansion are intentionally stopped.
# The committed reference catalogue is retained for existing URLs during the measured migration.
"$PY" scripts/canonicalize_models.py
if [ "$MOTORJURY_PREVIEW" != '1' ]; then "$PY" scripts/refresh_pilot.py; fi
"$PY" scripts/score_model_years.py
PYTHONPATH="scripts${PYTHONPATH:+:$PYTHONPATH}" "$PY" -c "from build_record_pages import apply_pilot; import sqlite3; c=sqlite3.connect('data/cars.sqlite'); apply_pilot(c); c.close()"
"$PY" scripts/price_model.py
"$PY" scripts/fill_fuel.py
"$PY" scripts/make_icons.py
"$PY" scripts/build_models.py --plan
"$PY" scripts/gen_site.py
"$PY" scripts/build_models.py
"$PY" scripts/build_library.py
"$PY" scripts/build_engage.py
"$PY" scripts/build_events.py
"$PY" scripts/build_stories.py
"$PY" scripts/build_problems.py
"$PY" scripts/build_guides.py
"$PY" scripts/build_report.py
"$PY" scripts/build_people.py --from-cache
"$PY" scripts/build_social.py
"$PY" scripts/build_buying_brief.py
"$PY" scripts/build_record_pages.py
"$PY" scripts/build_genius.py
"$PY" scripts/tag_site.py
"$PY" scripts/localize.py
"$PY" scripts/polish.py
"$PY" scripts/publication_policy.py
"$PY" scripts/qa_site.py
"$PY" scripts/qa_publication.py
"$PY" -m unittest discover -s tests -v
node --test workers/*.test.mjs assets/buying-*.test.mjs assets/catalogue-*.test.mjs
 echo "Verified site build complete; no deployment was performed."
