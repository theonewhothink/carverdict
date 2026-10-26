import test from "node:test";
import assert from "node:assert/strict";
import { makeRecovery, canonicalLocation, serveWithRecovery } from "./recover.mjs";
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

function assets(routes = {}, pages = []) {
  return { fetch: async req => {
    const path = new URL(req.url).pathname;
    if (path === "/assets/route-recovery.json") return Response.json(routes);
    return new Response(null, { status: pages.includes(path) ? 200 : 404 });
  }};
}
async function recover(path, binding, method = "GET") {
  const req = new Request("https://motorjury.com" + path, { method });
  return serveWithRecovery(req, new URL(req.url), binding, recoveryCandidates);
}

test("exact catalogue recovery preserves query and roster fragment", async () => {
  const a = assets({ "/library/byd/byd-atto-3/": "/library/byd-auto/#m-byd-atto-3" }, ["/library/byd-auto/"]);
  const res = await recover("/library/byd/byd-atto-3/?ref=search", a);
  assert.equal(res.status, 301);
  assert.equal(res.headers.get("Location"), "https://motorjury.com/library/byd-auto/?ref=search#m-byd-atto-3");
  assert.equal((await recover("/de/library/byd/byd-atto-3/", a)).status, 301);
});

test("unknown models, missing targets, files and writes retain their 404", async () => {
  const a = assets({ "/library/byd/missing/": "/library/byd-auto/#m-missing" });
  for (const p of ["/library/byd/missing/", "/library/byd/invented/", "/assets/missing.png"])
    assert.equal((await recover(p, a)).status, 404);
  assert.equal((await recover("/library/byd/missing/", a, "POST")).status, 404);
});

test("manifest cannot redirect externally or replace an existing page", async () => {
  const a = assets({ "/library/audi/s7/": "https://example.org/" }, ["/library/audi/existing/"]);
  assert.equal((await recover("/library/audi/s7/", a)).status, 404);
  assert.equal((await recover("/library/audi/existing/", a, "HEAD")).status, 200);
});

test("HTTP, www and worker hosts canonicalise in one hop with query intact", () => {
  for (const origin of ["http://motorjury.com", "https://www.motorjury.com", "https://carsite.example.workers.dev"])
    assert.equal(canonicalLocation(new URL(origin + "/discover/?q=f40")), "https://motorjury.com/discover/?q=f40");
  assert.equal(canonicalLocation(new URL("https://motorjury.com/discover/")), null);
  assert.equal(canonicalLocation(new URL("http://localhost:8787/")), null);
});
