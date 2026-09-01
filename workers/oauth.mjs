/** Pure OAuth helpers, separated so the two provider flows are unit-testable. */
export function b64urlToBytes(value) {
  let s = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
  const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
  const bin = atob(s + pad);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

export function idTokenClaims(idToken) {
  const parts = String(idToken || "").split(".");
  if (parts.length !== 3) throw new Error("malformed identity token");
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[1])));
}

export function validIdentityClaims(kind, claims, env, now = Math.floor(Date.now() / 1000)) {
  const issuer = kind === "google" ? ["https://accounts.google.com", "accounts.google.com"]
                                   : ["https://appleid.apple.com"];
  const audience = kind === "google" ? env.GOOGLE_CLIENT_ID : env.APPLE_CLIENT_ID;
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!issuer.includes(claims.iss) || !aud.includes(audience)) return false;
  if (!claims.sub || !claims.email || Number(claims.exp || 0) < now - 30) return false;
  if (kind === "google" && claims.email_verified !== true && claims.email_verified !== "true") return false;
  return true;
}

export function stateCookie(value) {
  // Apple returns with response_mode=form_post. SameSite=Lax would discard state on the
  // cross-site POST and make every Apple login fail before the token exchange. Encode the
  // return path as well so a crafted `next` value cannot alter cookie attributes.
  return `mj_oauth=${encodeURIComponent(value)}; Path=/api/auth; HttpOnly; Secure; SameSite=None; Max-Age=600`;
}

export function isJsonRequest(req) {
  return (req.headers.get("Content-Type") || "").toLowerCase().includes("application/json");
}

/* ------------------------------------------------------------------ Google GIS --- */

/* Google Identity Services ("Sign in with Google" button / One Tap) hands the browser a
   signed ID token and no authorization code, so the server needs no client secret — only
   the public client id — but it MUST verify the signature itself: the token arrives from
   the browser, not from Google's token endpoint. RS256 against Google's published JWKS,
   cached for an hour in the isolate. */
let _googleJwks = { keys: null, fetched: 0 };

async function googleJwks(fetchImpl = fetch) {
  if (_googleJwks.keys && Date.now() - _googleJwks.fetched < 3600e3) return _googleJwks.keys;
  const res = await fetchImpl("https://www.googleapis.com/oauth2/v3/certs", { cf: { cacheTtl: 3600 } });
  const body = await res.json();
  _googleJwks = { keys: body.keys || [], fetched: Date.now() };
  return _googleJwks.keys;
}

export async function verifyGoogleIdToken(idToken, clientId, fetchImpl = fetch, now = Math.floor(Date.now() / 1000)) {
  const parts = String(idToken || "").split(".");
  if (parts.length !== 3) throw new Error("malformed identity token");
  const header = JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[0])));
  if (header.alg !== "RS256") throw new Error("unexpected token algorithm");
  const keys = await googleJwks(fetchImpl);
  let jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk) {                                   // key rotation: refetch once
    _googleJwks = { keys: null, fetched: 0 };
    jwk = (await googleJwks(fetchImpl)).find((k) => k.kid === header.kid);
  }
  if (!jwk) throw new Error("unknown signing key");
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify({ name: "RSASSA-PKCS1-v1_5" }, key,
    b64urlToBytes(parts[2]), new TextEncoder().encode(parts[0] + "." + parts[1]));
  if (!ok) throw new Error("bad token signature");
  const claims = idTokenClaims(idToken);
  if (!validIdentityClaims("google", claims, { GOOGLE_CLIENT_ID: clientId }, now)) throw new Error("token claims rejected");
  return claims;
}
