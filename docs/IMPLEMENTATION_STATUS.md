# MotorJury execution — 6 October 2026

A working pilot is implemented on an isolated branch from production commit `d507e355376ff1cf505e4e7a63e9425ae84fbb6b`. Production has not been replaced. Synced project sources were untouched.

## What changed

- Homepage now leads with car photography and search of the complete stored collection. The 2019–2020 US RAV4 buying journey remains prominent: primary-source guide, gasoline/Hybrid comparison, version-specific checklist, private save/export/print/share and a budget using the reader's inputs.
- The buying brief includes a question-led experience: reviewed guided responses, explicit version selection, source links and streaming AI integration when the provider is activated. The live service reports AI disabled; no real model answer is claimed.
- Synthetic prices, insurance and resale estimates have been withdrawn from the wider build and lookup data.
- Missing costs remain unknown. The tool cannot declare an ownership-cost winner without complete inputs. Shared links contain year and powertrain only.
- Complaint and recall services resolve model identities separately. The 2020 Lexus RX 350 regression is covered in both the dataset and VIN service. Unmatched, unavailable and incomplete responses cannot become verified zero results. Recall IDs are deduplicated.
- Predictive reliability scores and automatic buying verdicts are suspended. The assistant receives only source-checked pilot records and reviewed editorial routes, without synthetic market-price or severity claims.
- Global ads are paused. Exact-path review is required to opt a page into advertising. Preview builds remove analytics and ads and cannot deploy through `build.sh`.
- Wikipedia extract/spec harvesting and automatic encyclopaedia catalogue expansion are removed from the production build. Imported biographies and unreviewed guide bodies are withheld. Catalogue identifiers and reference photos still need a separate, measured migration and permission review.
- Earlier comparison routes remain accessible without unsupported winners. A dated inventory preserves all URLs from the current sitemap. The broad nine-route indexing restriction has been removed: production now preserves each builder's individual indexing gate. Unreviewed model pages remain held; the collection root, complete-directory root and coverage notes are accessible for indexing. Review traffic and the remaining individual exclusions before release.

## Collection and mobile update

- Stored source catalogue unchanged: 16,235 raw rows and 12,859 photo references. Existing duplicate merging produces 15,888 distinct entries across 1,096 marques, with 12,609 photo references. This is not verified coverage of every car ever made.
- Complete search covers names and marques, including entries without photos or dates. Explicit decade/photo filters and 24-card batches avoid loading thousands of images at once. The 2.45 MB search JSON is fetched on interaction; compressed size and browser checks are recorded in MOBILE_COLLECTION.md.
- Every distinct entry appears exactly once in 133 paginated HTML directory pages. All marque pages contain their complete static roster. Models beyond the existing 6,500 standalone-page limit link to an anchored roster entry rather than a missing page.
- Featured photographs have checked Commons author/licence metadata and per-file attribution links. Historical record photos are labelled illustrations; RAV4 records use a sourced 2019 LE photo rather than a 2025 prototype. Remaining inherited photo permissions are not presented as reviewed.
- Mobile buying flow uses four expandable steps and persistent section navigation. Four fuel inputs are visible when the budget step opens; the additional ownership inputs are optional. Unknown ownership costs still prevent an invented winner. Task prompts follow the selected version.

## Latest collection verification

46 JavaScript and nine Python tests passed after this update. Final structure checks passed for 14,788 audited pages; publication checks covered all 14,789 generated HTML pages. All 15,888 search/directory entries, every destination and roster anchor, and all 2,979 baseline routes were verified. Browser checks cover 320/390/430 px phones and 1280 px desktop, photo loading, search/filter/reset/pagination, catalogue-only photo previews, version-aware prompts and incomplete fuel-budget results. See MOBILE_COLLECTION.md for precise observations and remaining limits.

## Earlier pilot verification actually performed

- Full preview build and full production-mode build completed locally. Neither deployed.
- 44 existing/new JavaScript tests passed; 8 Python evidence/publication checks passed.
- Final HTML checks covered 14,655 pages: no broken internal links/assets, no unapproved ad requests, no predictive scores in the assistant index; structure checks found no failures.
- All 2,979 routes captured from the live sitemap remained present. This does not prove coverage of every historical URL.
- The earlier production-mode check verified the then-current nine-path policy. The subsequent collection update replaces that policy with tested per-template gates. The restored preview has no ads or analytics scripts.
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

## 7 October — collection release candidate

The candidate now includes six original manufacturer-archive design profiles (F40, Miura, original E30 M3, original MX-5, original NSX and 300 SL), three curated reading journeys, a labelled browser-only discovery guide, saving across static/dynamic catalogue cards and all 6,500 model pages, three-car scoped design comparisons and a downloadable/copyable shortlist. Remaining reference pages use the same navigation, preserve their original photograph/gallery and community-control hooks, and stay noindex. Earlier and later generations are explicitly distinguished. The six researched profile paths are individually indexable and present in the production-mode sitemap.

Car Genius can search and read the full text of reviewed pages, preserving version scope and primary-source links. `read_page` fails closed outside that index. Live status returned `enabled:false` on 7 October; no real provider answer or activation is claimed.

Production Google Analytics uses explicit opt-in, stays unloaded after Necessary only, and can be withdrawn through Privacy choices. Advertising consent remains denied. Task events contain only task types, excluding saved names and private input values. Analytics page configuration strips query/fragment data from page locations and referrers. The older privacy/disclosure claims of a certified CMP, established advertising funding and unverified retention periods have been replaced with descriptions of the implemented behaviour. This is not advertising CMP certification or a verified GA reporting baseline.

Verification: 54 JavaScript plus 12 Python tests passed. Final structure checks passed for 14,790 audited pages; publication checks covered 14,791 HTML pages. All 15,888 distinct catalogue entries, 12,609 distinct photo references and 2,979 baseline routes remain available. The raw catalogue and existing featured-photo metadata are byte-for-byte unchanged: 16,235 raw entries / 12,859 photo references. All six profiles are available as readable assistant references. Source snapshots refreshed successfully for the three public-record pilot vehicles on 7 October.

Browser evidence: 320 px discovery and 390 px model/shortlist flows, 1280 px desktop discovery, no horizontal overflow in these views, all six discovery photos loaded, three saves persisted between pages, comparison version labels remained explicit, photo viewer showed the correct author/licence and trapped Tab / closed with Escape. A native file-download event was not confirmed by the embedded browser; the new copyable shortlist text was visibly verified as a fallback. Test saved cars were removed. Necessary only left the Google library unloaded. No preview analytics controller remains after restoring preview isolation.

Screenshots: `collection-discovery-desktop.png`, `collection-story-phone.png`, `collection-shortlist-phone.png`.

This entry records the validated candidate, not an already completed deployment. CI and production deployment must be verified separately. Reader participation, qualified mechanic review, physical-device / field performance, broader image-permission review, provider activation and actual audience/revenue evidence remain outstanding. No outreach or AdSense resubmission was performed.
