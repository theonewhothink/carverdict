import test from "node:test";
import assert from "node:assert/strict";
import { makeRecovery } from "./recover.mjs";
const recoveryCandidates = makeRecovery(new Map([["/cars/bmw/x5-xdrive35d/", "/cars/bmw/x5/"]]));

test("library marque slug drift", () => {
  const c = recoveryCandidates("/library/audi-ag/audi-s7/");
  assert.equal(c[0], "/library/audi/audi-s7/");
  assert.equal(recoveryCandidates("/library/dongfeng-liuzhou-motor-company/dongfeng-forthing-u-tour-v9/")[0],
    "/library/dongfeng-liuzhou/dongfeng-forthing-u-tour-v9/");
});

test("problems on folded trim slugs", () => {
  const c = recoveryCandidates("/problems/bmw/x5-sdrive35i/2014/");
  assert.ok(c.includes("/problems/bmw/x5-sdrive35i/"));
  assert.ok(c.includes("/cars/bmw/x5-sdrive35i/2014/"));
});

test("localised copies fall back to the English page", () => {
  const c = recoveryCandidates("/de/superlatives/");
  assert.equal(c[0], "/superlatives/");
});

test("compare pages rewrite folded slugs", () => {
  assert.equal(recoveryCandidates("/compare/nissan-altima-vs-bmw-x5-xdrive35d/")[0],
    "/compare/nissan-altima-vs-bmw-x5/");
});

test("never redirects to itself", () => {
  for (const p of ["/library/", "/compare/", "/", "/de/"]) assert.ok(!recoveryCandidates(p).includes(p));
});

// --- the soft-404 regression this file exists to prevent -----------------------------
// Every candidate list used to end at a section index, so an invented URL answered 200
// from its parent. An invented URL must produce no candidate that would resolve.

test("an invented nameplate offers no section fallback", () => {
  const c = recoveryCandidates("/cars/toyota/this-does-not-exist-xyz/");
  assert.deepEqual(c, []);
});

test("an invented model year recovers only onto its own nameplate", () => {
  const c = recoveryCandidates("/cars/toyota/rav4/1066/");
  assert.deepEqual(c, ["/cars/toyota/rav4/"]);
  assert.ok(!c.includes("/cars/toyota/"));
  assert.ok(!c.includes("/cars/"));
});

test("no candidate list ends at a section index", () => {
  const probes = ["/cars/toyota/nope/", "/cars/nope/nope/2011/", "/library/nope/nope-model/",
                  "/problems/nope/nope/", "/compare/nope-vs-nope/", "/library/nope/"];
  const sections = new Set(["/", "/cars/", "/library/", "/problems/", "/compare/", "/guides/"]);
  for (const p of probes)
    for (const c of recoveryCandidates(p))
      assert.ok(!sections.has(c), `${p} still falls back to ${c}`);
});

test("a real slug migration still recovers", () => {
  assert.ok(recoveryCandidates("/cars/bmw/x5-xdrive35d/2014/").includes("/cars/bmw/x5/2014/"));
  assert.ok(recoveryCandidates("/cars/bmw/x5-xdrive35d/").includes("/cars/bmw/x5/"));
});
