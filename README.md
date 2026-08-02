# CarVerdict

True car ownership costs computed from public data — NHTSA complaints and recalls, EPA fuel
economy — re-priced automatically for the visitor's country. Plus a catalogue of **15,212 car
models** across **1,162 marques** with **11,972** freely-licensed photographs.

Live: https://carsite.adir-073.workers.dev

## What the build produces

| Surface | What it is |
|---|---|
| `/` | Image-led home: hero mosaic, Car of the Day, EV cluster, years to avoid |
| `/cars/**` | Model-year verdict pages (BUY / CAUTION / AVOID) from NHTSA + EPA data |
| `/library/**` | Every marque, every catalogued model, one page per model |
| `/play/` | Car of the Day + Car of the Week + daily Guess-the-Car with streaks |
| `/superlatives/` | Most expensive, rarest, era-defining — every figure sourced |
| `/calculators/` | True-cost calculator, priced for your country |
| `/garage/`, `/notify/` | Saved cars, interests, reminders (device-local, no account) |
| `/pt/ /es/ /fr/ /de/ /he/` | Full localisations; Hebrew is RTL |

## Build order (matters — `gen_site.py` clears `site/`)

```bash
pip install pillow
python scripts/build_models.py --plan   # decides which models get pages
python scripts/gen_site.py              # data pages + home + assets
python scripts/build_models.py          # one page per model
python scripts/build_library.py         # marque pages + search index
python scripts/build_engage.py          # play / garage / superlatives / notify
python scripts/localize.py              # 5 languages + sitemap
```

`MAX_MODEL_PAGES` in `scripts/build_models.py` caps model pages. CI raises it to 15,300;
local/manual deploys through the Cloudflare dashboard need a lower value because that
uploader is limited to roughly 4,800 files per upload.

## Operating laws

1. Data or nothing — no page without unique structured data and a computed verdict.
2. Never fabricate — every number traces to NHTSA/EPA or a cited source; estimates are labelled.
3. Photographs are hotlinked from Wikimedia Commons with per-file credit; no files are copied.
4. A photo click always opens the car's page — never an image file, never an external site.
5. Ads never degrade UX: reserved heights, consent never covers content.

## Secrets CI needs

| Name | Where | Purpose |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | repo → Settings → Secrets → Actions | deploy |
| `CLOUDFLARE_ACCOUNT_ID` | same | deploy target account |
| `SITE_ORIGIN` | repo → Settings → Variables | canonical URLs once a domain exists |
| `INDEXNOW_KEY` | secrets (optional) | ping Bing/DDG/Yandex on each deploy |

## Data sources

- [NHTSA](https://www.nhtsa.gov) complaints, recalls, investigations (public API)
- [EPA fueleconomy.gov](https://www.fueleconomy.gov) economy and energy cost
- [Wikidata](https://www.wikidata.org) model catalogue (CC0)
- [Wikimedia Commons](https://commons.wikimedia.org) photography (CC, credited per file)
- Regional fuel/electricity/insurance indices in `data/geo_prices.json` — labelled estimates
