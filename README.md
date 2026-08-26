# MotorJury

What a car really costs to own — purchase price, depreciation, repairs, insurance and a
computed verdict — from public data (NHTSA complaints and recalls, EPA fuel economy),
re-priced automatically for the visitor's country. Plus a catalogue of **16,235 car models**
across **1,096 marques** with **12,859** freely-licensed photographs.

Live: https://motorjury.com

## What the build produces

| Surface | What it is |
|---|---|
| `/` | Image-led home: hero mosaic, Car of the Day, the highest-scoring cars, most-loved |
| `/cars/**` | Model-year verdict pages (BUY / CAUTION / AVOID) from NHTSA + EPA data |
| `/library/**` | Every marque, every catalogued model, one page per model |
| `/play/` | Car of the Day + Car of the Week + daily Guess-the-Car with streaks |
| `/superlatives/` | Most expensive, rarest, era-defining — every figure sourced |
| `/calculators/` | True-cost calculator, priced for your country |
| `/login/`, `/account/` | Accounts: email and password, plus Google and Apple when configured |
| `/loved/` | The love-button leaderboard, counted live, one vote per account |
| `/garage/`, `/notify/` | Saved cars, interests, reminders — synced to the account when signed in |
| `/follow/` | The public link-in-bio page the social profiles point at |
| `/studio/` | Seven days of ready-to-post social packages (noindex, not linked) |
| `/pt/ /es/ /fr/ /de/ /he/` | Full localisations; Hebrew is RTL |

## Build order (matters — `gen_site.py` clears `site/`)

```bash
pip install pillow
python scripts/canonicalize_models.py   # fold vPIC trim spam onto the marketing model name
python scripts/score_model_years.py     # reliability score, verdict, cost curve
python scripts/price_model.py           # price, depreciation, resale, insurance
python scripts/make_icons.py            # the mark, every icon size, the default OG card
python scripts/build_models.py --plan   # decides which models get pages
python scripts/gen_site.py              # data pages + home + assets
python scripts/build_models.py          # one page per model
python scripts/build_library.py         # marque pages + search index
python scripts/build_engage.py          # play / garage / superlatives / notify
python scripts/build_social.py          # social packages + /studio/ + /follow/
python scripts/localize.py              # 5 languages + sitemap
python scripts/polish.py                # chrome, icons, cards, landmarks on every page
```

`MAX_MODEL_PAGES` in `scripts/build_models.py` caps model pages. CI raises it to 15,300;
local/manual deploys through the Cloudflare dashboard need a lower value because that
uploader is limited to roughly 4,800 files per upload.

## Accounts, and the database that is not a database

Everything a reader builds up — the cars they love, their garage, their country, their
owner-survey answers — lives in a **Durable Object with the SQLite storage backend**
(`workers/hub.js`), bound as `HUB` in `wrangler.toml`.

That choice is the whole reason accounts shipped. D1 and KV each need a namespace created in
the Cloudflare console and an id pasted into a config file; a Durable Object namespace is
provisioned by the deploy itself. There is no credential, no id, and nothing for anyone to do
before the login works.

* **Email and password work with no configuration at all.** Passwords are PBKDF2-SHA256 at
  210,000 iterations; session tokens are stored hashed, so a database dump cannot be replayed
  as a login.
* **Google and Apple light up when their secrets exist** — `/api/auth/providers` reports what
  is live and the sign-in page renders only those buttons:

```
npx wrangler secret put GOOGLE_CLIENT_ID
npx wrangler secret put GOOGLE_CLIENT_SECRET
npx wrangler secret put APPLE_CLIENT_ID      # the Services ID, e.g. com.motorjury.web
npx wrangler secret put APPLE_TEAM_ID
npx wrangler secret put APPLE_KEY_ID
npx wrangler secret put APPLE_PRIVATE_KEY    # the .p8 contents
```

Redirect URIs to register: `https://motorjury.com/api/auth/google/callback` and
`https://motorjury.com/api/auth/apple/callback`.

| Endpoint | What it does |
|---|---|
| `POST /api/auth/signup` · `login` · `logout`, `GET /api/auth/me` | sessions, HttpOnly cookie |
| `GET /api/auth/google` · `apple` (+ `/callback`) | OAuth, gated on the secrets above |
| `GET/POST /api/love`, `GET /api/most-loved` | the love button and its leaderboard |
| `GET/POST /api/survey` | owner satisfaction; averages publish at 5 responses |
| `POST /api/prefs`, `POST /api/subscribe`, `GET /api/stats` | preferences, email capture, counts |

## The money layer

`scripts/price_model.py` computes purchase price, depreciation, resale and insurance for
every model-year, from published constants in `data/price_model.json` (also served at
`/assets/price-model.json`). No free dataset carries per-model prices, so these are
**class-level estimates** with the formula published on `/methodology/#prices` and a band
around every figure — and every price panel lets the reader type the price they are actually
being quoted and recomputes from it.

## Operating laws

1. Data or nothing — no page without unique structured data and a computed verdict.
2. Never fabricate — every number traces to NHTSA/EPA or a cited source; estimates are labelled.
3. Photographs are hotlinked from Wikimedia Commons with per-file credit; no files are copied.
4. A photo click always opens the car's page — never an image file, never an external site.
5. Ads never degrade UX: reserved heights, consent never covers content.
6. Two link gates, both hard: the static one reads `href=` out of the HTML, and the
   client-side one checks the JSON the browser builds links from. The second exists because
   the first was blind to the search box, which was linking a model page for 7,992 models
   that had none.
7. Account data is the reader's: stored for the features they asked for, never sold, never
   used to target advertising, deleted on request.

## How it publishes

Cloudflare Workers Builds is connected straight to this repository (Worker **carsite**).
Every push to `main` makes Cloudflare run:

```
build command   bash build.sh          # installs deps, builds, gates dead links, runs tests
deploy command  npx wrangler deploy    # uploads ./site as Worker static assets
```

**There is no Cloudflare API token in this repository** — the connection is a GitHub App grant,
so there is no credential to rotate, leak, or misname. GitHub Actions still runs on every push
as a pre-flight check (build + dead-link gate + unit tests) but no longer deploys.

| Optional setting | Where | Purpose |
|---|---|---|
| `SITE_ORIGIN` | repo → Settings → Variables | canonical URLs once a real domain exists |
| `INDEXNOW_KEY` | repo → Settings → Secrets | ping Bing/DuckDuckGo/Yandex after a build |

## Data sources

- [NHTSA](https://www.nhtsa.gov) complaints, recalls, investigations (public API)
- [EPA fueleconomy.gov](https://www.fueleconomy.gov) economy and energy cost
- [Wikidata](https://www.wikidata.org) model catalogue (CC0)
- [Wikimedia Commons](https://commons.wikimedia.org) photography (CC, credited per file)
- Regional fuel/electricity/insurance indices in `data/geo_prices.json` — labelled estimates
