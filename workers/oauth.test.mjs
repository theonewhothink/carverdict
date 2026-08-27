import { test } from "node:test";
import assert from "node:assert/strict";
import { isJsonRequest, stateCookie, validIdentityClaims } from "./oauth.mjs";

const env = { GOOGLE_CLIENT_ID: "g-client", APPLE_CLIENT_ID: "a-client" };
const now = 2_000_000_000;

test("Apple state survives the form_post callback", () => {
  assert.match(stateCookie("abc"), /SameSite=None/);
  assert.match(stateCookie("abc"), /Secure/);
  assert.doesNotMatch(stateCookie("abc|/; SameSite=Strict"), /abc\|\/;/);
});

test("Apple's form body is not consumed by the JSON parser", () => {
  assert.equal(isJsonRequest(new Request("https://x", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "code=x",
  })), false);
  assert.equal(isJsonRequest(new Request("https://x", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  })), true);
});

test("identity claims must match provider, client, expiry and verified email", () => {
  const google = { iss: "https://accounts.google.com", aud: "g-client", sub: "1",
    email: "person@example.com", email_verified: true, exp: now + 300 };
  assert.equal(validIdentityClaims("google", google, env, now), true);
  assert.equal(validIdentityClaims("google", { ...google, aud: "other" }, env, now), false);
  assert.equal(validIdentityClaims("google", { ...google, exp: now - 100 }, env, now), false);
  assert.equal(validIdentityClaims("google", { ...google, email_verified: false }, env, now), false);
  const apple = { iss: "https://appleid.apple.com", aud: "a-client", sub: "2",
    email: "person@privaterelay.appleid.com", exp: now + 300 };
  assert.equal(validIdentityClaims("apple", apple, env, now), true);
});
