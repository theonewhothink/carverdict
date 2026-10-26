# Brand portal rollout — 26 October 2026

The canonical `/library/{brand}/` pages use the Porsche portal’s editorial canvas,
two-second multi-image hero, credited gallery/lightbox, open sections and searchable
model roster. Porsche keeps its bespoke article, eight-generation selector and six films.
All 1,096 catalogue marque and coachbuilder groups participate, preserving all 15,888
vehicle identities and existing fragment destinations. Library marque shortcuts now
open the corresponding portal; the full marque directory is visible without disclosure.

## Content and media scope

- Eleven additional marque features use the source lists and dates in
  `data/brand_portal_stories.json`. Other pages offer original, explicitly scoped
  exploration of their own catalogue records. They do not claim a fully researched
  corporate history or a road test.
- The gallery snapshot has 4,478 additional exact-file Commons attribution records,
  prepared through the public imageinfo API. Existing checked credits are retained.
  Selected gallery images require an author, licence, source URL and check date.
- The initial rollout displays 4,886 credited gallery selections across 929 portals,
  with up to 24 images per page. An archive with one documented image uses a still
  hero; one with none uses a deliberate typographic cover and its real model directory.
- Nine additional named-publisher films supplement Porsche’s six. Actual thumbnails
  are shown, and the YouTube privacy-enhanced player loads only on Play. Missing
  videos are omitted rather than represented by fabricated posters or reused IDs.
- The source snapshot remains separate from the build date. Recorded vehicle years
  are labelled as catalogue dates, not guaranteed introduction or production dates.

## Publication controls

This layout rollout preserves the existing non-Porsche indexing holds and advertising
policy. It does not bulk-index sparse archives or imply that every marque has had the
same depth of historical review as Porsche. It changes no canonical URL or recovery
route. The generated `assets/brand-portals.json` records per-portal coverage for QA.

## Verification

The normal full publication build and existing Porsche Chromium checks remain in place.
`tests/test_all_brand_portals.py` checks all marque rosters, exact destinations, source
metadata, unique IDs and preserved indexing holds. `scripts/qa_all_brand_portals.mjs`
exercises major, single-image and empty-image archives on phone and desktop, including
model filtering, gallery naming, video selection and JavaScript-free fallbacks.

`scripts/prepare_brand_media.py` is a manual maintenance command after catalogue
generation. It requests exact existing filenames, records unresolved metadata and
writes a reviewable snapshot into `verification/brand-media/`. It is not part of the
publication build and does not create a network dependency for future deployments.
