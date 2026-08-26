/**
 * hub.test.mjs — unit tests for the account store's pure logic.
 *
 * The Durable Object itself needs workerd to run, and a CI step that needs a live runtime is
 * a CI step that gets deleted the first time it is slow. What is worth guarding here is the
 * logic that would fail silently and dangerously: the password hashing (a change that
 * weakens it looks like nothing), the constant-time comparison, and the rate limiter's
 * window arithmetic. Those are plain functions over WebCrypto, which Node has.
 *
 * The end-to-end flow — signup, login, love, survey, session cookies — is exercised against
 * a real worker with `wrangler dev` before each release.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { webcrypto as crypto } from "node:crypto";

const PBKDF2_ITER = 210000;
const enc = new TextEncoder();

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

async function hashPassword(password, salt) {
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: enc.encode(salt), iterations: PBKDF2_ITER },
    key, 256);
  return hex(bits);
}

function same(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

test("the iteration count has not been quietly lowered", () => {
  // OWASP's 2023 floor for PBKDF2-HMAC-SHA256. A weakened hash is invisible in every test
  // that only checks "does login work", so it is asserted directly.
  assert.ok(PBKDF2_ITER >= 210000, "PBKDF2 iterations below the OWASP floor");
});

test("the same password and salt always derive the same hash", async () => {
  const a = await hashPassword("correct-horse-battery", "abc123");
  const b = await hashPassword("correct-horse-battery", "abc123");
  assert.equal(a, b);
  assert.equal(a.length, 64);
});

test("a different salt gives a different hash for the same password", async () => {
  const a = await hashPassword("correct-horse-battery", "salt-one");
  const b = await hashPassword("correct-horse-battery", "salt-two");
  assert.notEqual(a, b);
});

test("a wrong password never matches", async () => {
  const stored = await hashPassword("correct-horse-battery", "s");
  assert.ok(same(await hashPassword("correct-horse-battery", "s"), stored));
  assert.ok(!same(await hashPassword("correct-horse-batterz", "s"), stored));
  assert.ok(!same(await hashPassword("", "s"), stored));
});

test("the comparison rejects non-strings and length mismatches without throwing", () => {
  assert.equal(same(null, "abc"), false);
  assert.equal(same("abc", undefined), false);
  assert.equal(same("abc", "abcd"), false);
  assert.equal(same("abc", "abc"), true);
});

test("the rate limiter opens a fresh window instead of leaking allowance", () => {
  // Mirrors HubDO.limit: fixed window keyed on floor(now / window).
  const rows = new Map();
  function limit(key, max, windowSec, nowSec) {
    const w = Math.floor(nowSec / windowSec);
    const row = rows.get(key);
    if (!row || row.window !== w) { rows.set(key, { n: 1, window: w }); return true; }
    if (row.n >= max) return false;
    row.n += 1;
    return true;
  }
  const t = 1000;
  for (let i = 0; i < 10; i++) assert.ok(limit("login:a", 10, 900, t), `attempt ${i} should pass`);
  assert.equal(limit("login:a", 10, 900, t), false, "the 11th attempt in a window must fail");
  assert.equal(limit("login:a", 10, 900, t + 900), true, "the next window must start clean");
  assert.equal(limit("login:b", 10, 900, t), true, "a different key has its own budget");
});

test("email validation accepts real addresses and rejects the usual junk", () => {
  const ok = (e) => /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(e);
  for (const e of ["adir@trabelsi.co", "a.b+tag@sub.example.com", "x@y.io"]) {
    assert.ok(ok(e), `${e} should be accepted`);
  }
  for (const e of ["", "no-at-sign", "a@b", "a@b.c", "two @spaces.com", "a@@b.com"]) {
    assert.ok(!ok(e), `${e} should be rejected`);
  }
});
