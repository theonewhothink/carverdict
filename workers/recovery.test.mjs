import test from "node:test";
import assert from "node:assert/strict";
import { makeRecovery } from "./recover.mjs";
const recoveryCandidates = makeRecovery(new Map([["/cars/bmw/x5-xdrive35d/", "/cars/bmw/x5/"]]));

test("library marque slug drift", () => {
  const c = recoveryCandidates("/library/audi-ag/audi-s7/");
  assert.equal(c[0], "/library/audi/audi-s7/");
  assert.ok(c.includes("/library/audi/"));
  assert.ok(c.includes("/library/"));
  assert.equal(recoveryCandidates("/library/dongfeng-liuzhou-motor-company/dongfeng-forthing-u-tour-v9/")[0],
    "/library/dongfeng-liuzhou/dongfeng-forthing-u-tour-v9/");
});

test("problems on folded trim slugs", () => {
  const c = recoveryCandidates("/problems/bmw/x5-sdrive35i/2014/");
  assert.ok(c.includes("/problems/bmw/x5-sdrive35i/"));
  assert.ok(c.includes("/cars/bmw/x5-sdrive35i/2014/"));
  assert.ok(c.includes("/problems/"));
});

test("localised copies fall back to the English page", () => {
  const c = recoveryCandidates("/de/superlatives/");
  assert.equal(c[0], "/superlatives/");
  assert.ok(c.includes("/de/"));
  assert.ok(c.includes("/"));
});

test("compare pages fall back to the index", () => {
  const c = recoveryCandidates("/compare/nissan-altima-vs-bmw-x5-xdrive35d/");
  assert.equal(c[c.length - 1], "/compare/");
});

test("never redirects to itself", () => {
  for (const p of ["/library/", "/compare/", "/", "/de/"]) assert.ok(!recoveryCandidates(p).includes(p));
});

test("compare pages rewrite folded slugs first", () => {
  assert.equal(recoveryCandidates("/compare/nissan-altima-vs-bmw-x5-xdrive35d/")[0], "/compare/nissan-altima-vs-bmw-x5/");
});
