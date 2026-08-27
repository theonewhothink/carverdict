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
