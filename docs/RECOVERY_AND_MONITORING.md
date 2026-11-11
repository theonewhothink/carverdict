# Release recovery and monitoring

This release does not change the Hub class, Durable Object binding, migration tag or account schema. Its code changes concern guide rendering, public build evidence and the dashboard's source-specific CI lookup.

## Current automated checks

- Dashboard CI requests the check list for the **serving commit**, then selects the `build-deploy` check. A nightly ingestion run or a check on another commit cannot certify delivery.
- A failed request, missing check or unfinished run stays unverified. The dashboard reports the lookup reason rather than inventing a green state.
- `site/release.json` is generated only after the existing publication and unit-test gates pass. It includes the source SHA, build time and preview flag. It contains no account data.
- The proposed read-only GitHub monitor checks five public routes and that published source every six hours and on manual dispatch. Its dated artifact is a sample, not continuous uptime or evidence that alerts reached a person.
- The workflow becomes active only after publication to the default branch. No scheduled run or alert delivery is claimed before then.

## Isolated recovery drill

Run:

```sh
node --test workers/recovery-drill.test.mjs
```

The drill uses the actual Hub class and a temporary on-disk Node SQLite database. It creates a fictional account, a saved car, a dashboard edit and a measured-zero fixture. It closes and reopens the database, makes a temporary edit after the snapshot, restores the closed-database copy, then verifies authentication, saved engagement, reports and edit history. The temporary edit must disappear after restoration.

This demonstrates the isolated storage/restart and snapshot path. Node SQLite is not Cloudflare workerd; it does not prove a production Durable Object point-in-time restore or a live Worker rollback.

## Hosting recovery procedure

1. Record the serving commit/version and the candidate known-good version in the authenticated hosting console. Retain the current version as the return target.
2. Compare `wrangler.toml`, `workers/hub.js`, `workers/dashboard-store.mjs` and any migrations between those versions. A code rollback does not reverse stored data.
3. Rehearse using a separate test Worker and test namespace. Never bind rehearsal code to the production Hub. Populate fictional records, record results and verify them after the rehearsal.
4. For an actual incident, use the identified compatible Cloudflare version and recheck the source marker, sampled public routes, sign-in and the private owner records. Preserve owner edits.
5. If stored data itself needs restoration, treat that as a separate recovery operation using a recorded backup/bookmark. A code deployment is not a database backup.

Cloudflare's [rollback documentation](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/rollbacks/) and [Durable Object lifecycle documentation](https://developers.cloudflare.com/durable-objects/reference/durable-objects-migrations/) were checked on 10 November 2026. Resource compatibility and lifecycle restrictions must be checked for the selected pair of versions. No production rollback or new binding was performed in this work.
