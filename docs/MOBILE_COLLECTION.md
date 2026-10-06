# Car collection and phone experience — 6 October 2026

The local preview now leads with cars, photographs and complete catalogue discovery. Production has not changed. This is an implementation and browser check, not a claim of perfect usability, historical completeness, Google approval or reader demand.

## Preserved collection

The source `data/car_library.json` is unchanged: 16,235 raw entries and 12,859 photo references. Existing deduplication produces 15,888 distinct entries across 1,096 marques, including 12,609 photo references. No stored cars or photographs were deleted. The inherited 6,500 standalone model-page limit is unchanged.

Search includes every distinct entry, including missing photos/dates. Decade and photo filters exclude those records only when explicitly selected. The complete HTML A–Z list has 133 pages of at most 120 entries; each marque also has its full static roster. Cars beyond the standalone-page limit open an anchored roster entry with a photograph preview. The original photograph/attribution link also works without JavaScript. The site describes coverage honestly; this snapshot is not a verified list of every car ever made.

The search dataset is fetched only after interaction or a search/deep-link request. It is 2,445,524 bytes uncompressed and 493,960 bytes in a local gzip calculation; this is not a measured production transfer size. Photographs load in batches of 24 with reserved dimensions and lazy loading. Failed external photos get an explicit unavailable state. The first gallery photograph is prioritised; the others use normal lazy loading. Featured Commons author/licence metadata is recorded in `data/photo_credits.json`; remaining inherited permissions still need review.

## Actual browser observations

| View | Width | Horizontal overflow | Main entry point |
| --- | --- | --- | --- |
| Homepage | 320 px | None | Search begins at 360 px |
| Homepage | 390 px | None | Search begins at 318 px |
| Homepage | 430 px | None | Checked |
| Homepage | 1280 px | None | Four-column photo grid |
| Buying brief | 320 px | None | Question begins at 492 px |
| Buying brief | 390 px | None | Question begins at 451 px |
| Buying brief | 430 px | None | Checked |

All 13 homepage photographs loaded in the browser. Search returned 308 Ferrari matches and 259 accent-insensitive Citroen matches. Show more expanded Ferrari results from 24 to 48. Reset restored all 15,888 entries. An explicit Toyota/1990s filter returned two entries. Empty queries with no matches showed a useful recovery message. A catalogue-only 250 Testarossa entry opened its roster and loaded its photograph. No console errors were observed on the collection search.

The brief uses four expandable sections and persistent phone navigation. Prompt buttons are 48 px tall; section links are 44 px tall. The budget initially exposes four fuel inputs; eleven additional ownership inputs remain optional. A fictional calculation using 12,000 miles, $3.50/gallon and 30/40 MPG returned $1,400/$1,050 annual fuel scenarios while refusing an ownership-cost winner with missing inputs. The test values were removed. Unknown version prompts ask for the year; a selected 2020 gasoline version produces gasoline guidance rather than a forced Hybrid answer.

## Automated checks

46 JavaScript and nine Python tests passed. Final HTML structure checks passed for 14,788 audited pages (the offline page is excluded); publication checks covered all 14,789 generated HTML pages. Every searchable row and directory row was matched to the stored deduplicated collection, and every catalogue destination/roster anchor was checked. All 2,979 baseline sitemap routes remain available. No unapproved ads, broken internal destinations or predictive buying ratings were found.

A regression check preserves individual production indexing gates and forces preview noindex. The former blanket nine-route restriction was removed; this does not clear held model pages for search or advertising. The preview requests neither ads nor analytics.

Screenshots: `rich-preview-desktop.png`, `rich-preview-phone.png`, `rich-brief-phone.png`.

## Limits and release work

These are simulated browser viewport checks. Physical iOS/Android devices, assistive-technology use, field Core Web Vitals, ten actual buyer sessions, mechanic review, completed checklist downloads and OS printing remain to be verified. Live AI remains disabled until securely configured and evaluated. Existing catalogue metadata is not independently reviewed ownership advice. AdSense eligibility and revenue cannot be established by layout checks.
