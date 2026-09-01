import test from "node:test";
import assert from "node:assert/strict";
import { verifyGoogleIdToken } from "./oauth.mjs";

const b64url = (buf) => Buffer.from(buf).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

test("verifyGoogleIdToken accepts a token signed by a published key and rejects a forged one", async () => {
  const pair = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  jwk.kid = "k1"; jwk.alg = "RS256"; jwk.use = "sig";
  const fetchImpl = async () => ({ json: async () => ({ keys: [jwk] }) });
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "RS256", kid: "k1", typ: "JWT" }));
  const claims = { iss: "https://accounts.google.com", aud: "cid.apps.googleusercontent.com", sub: "123",
    email: "a@b.com", email_verified: true, exp: now + 300, name: "A B" };
  const payload = b64url(JSON.stringify(claims));
  const sig = await crypto.subtle.sign({ name: "RSASSA-PKCS1-v1_5" }, pair.privateKey,
    new TextEncoder().encode(header + "." + payload));
  const token = header + "." + payload + "." + b64url(sig);
  const got = await verifyGoogleIdToken(token, "cid.apps.googleusercontent.com", fetchImpl, now);
  assert.equal(got.email, "a@b.com");
  await assert.rejects(verifyGoogleIdToken(token, "other-client", fetchImpl, now));
  const forged = header + "." + b64url(JSON.stringify({ ...claims, email: "x@y.com" })) + "." + b64url(sig);
  await assert.rejects(verifyGoogleIdToken(forged, "cid.apps.googleusercontent.com", fetchImpl, now));
});
