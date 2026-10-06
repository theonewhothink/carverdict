# MotorJury execution — 6 October 2026

A working pilot is implemented on an isolated branch from production commit `d507e355376ff1cf505e4e7a63e9425ae84fbb6b`. Production has not been replaced. Synced project sources were untouched.

## What changed

- Homepage now leads to one complete 2019–2020 US RAV4 buying journey: primary-source guide, gasoline/Hybrid decision guide, version-specific viewing checklist, private save/export/print/share controls and a budget using the reader's inputs.
- Homepage and brief now include a question-led experience: reviewed guided responses, explicit version selection, source links and streaming AI integration when the provider is activated. The live service reports AI disabled; no real model answer is claimed.
- Synthetic prices, insurance and resale estimates have been withdrawn from the wider build and lookup data.
- Missing costs remain unknown. The tool cannot declare an ownership-cost winner without complete inputs. Shared links contain year and powertrain only.
- Complaint and recall services resolve model identities separately. The 2020 Lexus RX 350 regression is covered in both the dataset and VIN service. Unmatched, unavailable and incomplete responses cannot become verified zero results. Recall IDs are deduplicated.
- Predictive reliability scores and automatic buying verdicts are suspended. The assistant receives only source-checked pilot records and reviewed editorial routes, without synthetic market-price or severity claims.
- Global ads are paused. Exact-path review is required to opt a page into advertising. Preview builds remove analytics and ads and cannot deploy through `build.sh`.
- Wikipedia extract/spec harvesting and automatic encyclopaedia catalogue expansion are removed from the production build. Imported biographies and unreviewed guide bodies are withheld. Catalogue identifiers and reference photos still need a separate, measured migration and permission review.
- Earlier comparison routes remain accessible without unsupported winners. A dated inventory preserves all URLs from the current sitemap. Proposed production indexing is restricted to nine selected pilot routes; review traffic before releasing this broad change.

## Verification actually performed

- Full preview build and full production-mode build completed locally. Neither deployed.
- 44 existing/new JavaScript tests passed; 8 Python evidence/publication checks passed.
- Final HTML checks covered 14,655 pages: no broken internal links/assets, no unapproved ad requests, no predictive scores in the assistant index; structure checks found no failures.
- All 2,979 routes captured from the live sitemap remained present. This does not prove coverage of every historical URL.
- Production-mode sitemap agreed with the nine selected index paths. The restored preview has no ads or analytics scripts.
- Browser checks: unknown version, gasoline-specific visibility, incomplete budget, complete budget, checkbox save and restore without automatic calculation, sharing disclosure, export action and clear action. At a 390-pixel phone viewport, homepage and brief had no horizontal overflow.
- Clearly fictional budget inputs: 12,000 miles, $3.50/gallon, five years, 30/40 MPG; complete scenarios returned $28,500/$27,750, a $750 difference. These are arithmetic tests, not market valuations or savings promises.
- Saved screenshots document desktop (1280 pixels) and phone (390 pixels) layouts without horizontal overflow. Question checks covered Hybrid viewing, gasoline-specific refuelling guidance, unsupported Prime/Canada and private-input withholding. Save/restore and actual clipboard contents were checked. The checklist download action ran without a console error, but the in-app browser did not expose a completed download event or file; file contents and operating-system printing remain unverified.
- A local Cloudflare Worker started and served the brief, reported AI disabled, rejected cross-origin and non-JSON AI requests, and rejected an invalid VIN. This does not verify the deployed Worker or production consent.
- The actual AI SDK passed a local streaming transport fixture, private-input/disabled/quota and missing-reference checks. No live provider request or real answer-quality evaluation was performed.

## Remaining work and gates

`BUYER_TEST.md` contains recruitment, consent, tasks and an observation record for ten real buyers. No participants have been recruited or tested; no mechanic endorsement exists. `RELEASE_CHECKLIST.md` covers the migration, release, advertising and measured acquisition gates.

Search Console access through the connected service failed because its subscription was unavailable. No traffic, conversion, RPM or revenue baseline was obtained. No subscription purchase, outreach or advertising submission was made.

The broader editorial collection and monetisation rollout depend on actual reader findings, independent review and measured demand. The remaining public legacy catalogue and reference-image permissions are not presented as fully reviewed or detached from all imported metadata. A clean build alone cannot resolve Google's low-value-content assessment.

## Reproduce safely

Use `MOTORJURY_PREVIEW=1 bash build.sh` with Python/SQLite/Pillow and Node available. The build reads the published dataset; `MOTORJURY_DATA_FILE` can supply a local snapshot and `MOTORJURY_PYTHON` can select the interpreter. A production-mode verification can run `bash scripts/build_inner.sh`; it builds only. Do not run plain `bash build.sh` for a test because its successful production path deploys.

Pilot source refresh is atomic. Failed lookups retain prior evidence with its prior check date. Generated database, redirects, icons and build output are excluded from this change; they are regenerated by the build.
