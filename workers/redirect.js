/**
 * redirect.js — the MotorJury Worker: host canonicalisation, the account API, and the
 * static site behind both.
 *
 * Everything under /api/ is handled here and forwarded to the HubDO database. Everything
 * else falls through to the generated pages. Host canonicalisation stays first, so the
 * workers.dev hostname and the www. host keep folding into the canonical domain instead of
 * splitting search authority three ways.
 *
 * SIGN-IN PROVIDERS. Email and password work with no configuration at all — that is
 * deliberate, because a login that waits on someone to register an OAuth client has not
 * shipped. Google and Apple light up the moment their secrets exist:
 *
 *   npx wrangler secret put GOOGLE_CLIENT_ID
 *   npx wrangler secret put GOOGLE_CLIENT_SECRET      (Google Cloud console -> Credentials)
 *   npx wrangler secret put APPLE_CLIENT_ID           (the Services ID, e.g. com.motorjury.web)
 *   npx wrangler secret put APPLE_TEAM_ID
 *   npx wrangler secret put APPLE_KEY_ID
 *   npx wrangler secret put APPLE_PRIVATE_KEY         (the .p8 contents)
 *
 * Redirect URIs to register: https://motorjury.com/api/auth/google/callback
 *                            https://motorjury.com/api/auth/apple/callback
 * /api/auth/providers reports which are live, and the sign-in page renders only those.
 */
export { HubDO } from "./hub.js";

// The model-canonicalisation 301 map. It used to be emitted into Cloudflare's _redirects
// file as splat rules, and its nightly growth crossed the platform's 100-dynamic-rule cap —
// which rejected every deploy and silently froze production. In code there is no cap: the
// same JSON the generator writes is bundled here and prefix-matched per request.
import MODEL_REDIRECTS from "../data/model_redirects.json";
import { inspectVin } from "./vin.mjs";

const REDIRECT_MAP = new Map(Object.entries(MODEL_REDIRECTS).filter(([a, b]) => a !== b));

/** /cars/{make}/{old-model}/anything -> /cars/{make}/{new-model}/anything, 301. */
function modelRedirect(url) {
  const m = /^(\/cars\/[^/]+\/[^/]+\/)/.exec(url.pathname);
  if (!m) return null;
  const target = REDIRECT_MAP.get(m[1]);
  if (!target) return null;
  const rest = url.pathname.slice(m[1].length);
  return url.origin + target + rest + url.search;
}

const SEC = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Cache-Control": "no-store",
};

const COOKIE = "mj_session";
const json = (o, status = 200, extra = {}) =>
  new Response(JSON.stringify(o), {
    status, headers: { "Content-Type": "application/json; charset=utf-8", ...SEC, ...extra },
  });

function cookie(req, name) {
  const raw = req.headers.get("Cookie") || "";
  for (const part of raw.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

function setCookie(token, days = 180) {
  return `${COOKIE}=${encodeURIComponent(token)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${days * 86400}`;
}
const clearCookie = `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;

function hub(env) {
  return env.HUB.get(env.HUB.idFromName("hub"));
}

async function call(env, op, payload = {}, query = "") {
  const stub = hub(env);
  const url = `https://hub/${op}${query ? "?" + query : ""}`;
  const res = await stub.fetch(new Request(url, {
    method: Object.keys(payload).length ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: Object.keys(payload).length ? JSON.stringify(payload) : undefined,
  }));
  return { ok: res.ok, data: await res.json() };
}

function providers(env) {
  return {
    email: true,
    google: Boolean(env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET),
    apple: Boolean(env.APPLE_CLIENT_ID && env.APPLE_TEAM_ID && env.APPLE_KEY_ID && env.APPLE_PRIVATE_KEY),
  };
}

/* ---------------------------------------------------------------- OAuth --- */

function b64urlToBytes(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
  const bin = atob(s + pad);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

/** Claims out of an ID token. The token came straight from the provider's own token
 *  endpoint over TLS in this same request, so the transport is the trust anchor; we read
 *  the claims rather than re-verifying a signature we just received first-hand. */
function idTokenClaims(idToken) {
  const parts = String(idToken || "").split(".");
  if (parts.length !== 3) throw new Error("malformed identity token");
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[1])));
}

function stateCookie(value) {
  return `mj_oauth=${value}; Path=/api/auth; HttpOnly; Secure; SameSite=Lax; Max-Age=600`;
}

async function appleClientSecret(env) {
  // Apple wants a short-lived ES256 JWT signed with the .p8 key instead of a static secret.
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "ES256", kid: env.APPLE_KEY_ID, typ: "JWT" };
  const claims = {
    iss: env.APPLE_TEAM_ID, iat: now, exp: now + 3000,
    aud: "https://appleid.apple.com", sub: env.APPLE_CLIENT_ID,
  };
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const signingInput = `${b64(header)}.${b64(claims)}`;
  const pem = String(env.APPLE_PRIVATE_KEY).replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const key = await crypto.subtle.importKey("pkcs8", b64urlToBytes(pem.replace(/\+/g, "-").replace(/\//g, "_")),
    { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" },
    key, new TextEncoder().encode(signingInput));
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${signingInput}.${sigB64}`;
}

async function oauthStart(kind, url, env) {
  const p = providers(env);
  if (!p[kind]) return Response.redirect(url.origin + "/login/?e=unconfigured", 302);
  const state = crypto.randomUUID();
  const next = url.searchParams.get("next") || "/account/";
  const redirect = `${url.origin}/api/auth/${kind}/callback`;
  let go;
  if (kind === "google") {
    go = "https://accounts.google.com/o/oauth2/v2/auth?" + new URLSearchParams({
      client_id: env.GOOGLE_CLIENT_ID, redirect_uri: redirect, response_type: "code",
      scope: "openid email profile", state, prompt: "select_account",
    });
  } else {
    go = "https://appleid.apple.com/auth/authorize?" + new URLSearchParams({
      client_id: env.APPLE_CLIENT_ID, redirect_uri: redirect, response_type: "code id_token",
      scope: "name email", state, response_mode: "form_post",
    });
  }
  return new Response(null, {
    status: 302,
    headers: { Location: go, "Set-Cookie": stateCookie(state + "|" + next), ...SEC },
  });
}

async function oauthCallback(kind, req, url, env) {
  const saved = (cookie(req, "mj_oauth") || "").split("|");
  const next = saved[1] || "/account/";
  let code, state, idToken, name = "";
  if (req.method === "POST") {
    const form = await req.formData();
    code = form.get("code"); state = form.get("state"); idToken = form.get("id_token");
    const user = form.get("user");
    if (user) {
      try {
        const u = JSON.parse(user);
        name = [u.name?.firstName, u.name?.lastName].filter(Boolean).join(" ");
      } catch (e) { /* Apple sends the name once, on first consent only */ }
    }
  } else {
    code = url.searchParams.get("code"); state = url.searchParams.get("state");
  }
  if (!state || state !== saved[0]) return Response.redirect(url.origin + "/login/?e=state", 302);

  const redirect = `${url.origin}/api/auth/${kind}/callback`;
  let claims;
  if (kind === "google") {
    const res = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code, client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET,
        redirect_uri: redirect, grant_type: "authorization_code",
      }),
    });
    const tok = await res.json();
    if (!tok.id_token) return Response.redirect(url.origin + "/login/?e=token", 302);
    claims = idTokenClaims(tok.id_token);
  } else {
    if (!idToken) {
      const res = await fetch("https://appleid.apple.com/auth/token", {
        method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          code, client_id: env.APPLE_CLIENT_ID, client_secret: await appleClientSecret(env),
          redirect_uri: redirect, grant_type: "authorization_code",
        }),
      });
      const tok = await res.json();
      if (!tok.id_token) return Response.redirect(url.origin + "/login/?e=token", 302);
      idToken = tok.id_token;
    }
    claims = idTokenClaims(idToken);
  }

  const { ok, data } = await call(env, "oauth", {
    email: claims.email, name: name || claims.name || "", sub: claims.sub, provider: kind,
  });
  if (!ok || !data.token) return Response.redirect(url.origin + "/login/?e=denied", 302);
  return new Response(null, {
    status: 302,
    headers: {
      Location: url.origin + (next.startsWith("/") ? next : "/account/"),
      "Set-Cookie": setCookie(data.token), ...SEC,
    },
  });
}

/* ------------------------------------------------------------------ API --- */

async function api(req, url, env) {
  const path = url.pathname.replace(/\/+$/, "");
  const token = cookie(req, COOKIE);
  const ip = req.headers.get("CF-Connecting-IP") || "";
  const body = req.method === "POST"
    ? await req.json().catch(() => ({}))
    : {};

  if (path === "/api/auth/providers") return json(providers(env));

  if (path === "/api/vin") {
    if (req.method !== "GET") return json({ error: "method not allowed" }, 405);
    try {
      const data = await inspectVin(url.searchParams.get("vin") || "");
      return json(data, 200, { "Cache-Control": "private, no-store" });
    } catch (e) {
      return json({ error: String(e && e.message || e) }, Number(e && e.status) || 502);
    }
  }

  if (path === "/api/auth/google") return oauthStart("google", url, env);
  if (path === "/api/auth/apple") return oauthStart("apple", url, env);
  if (path === "/api/auth/google/callback") return oauthCallback("google", req, url, env);
  if (path === "/api/auth/apple/callback") return oauthCallback("apple", req, url, env);

  if (path === "/api/auth/signup" || path === "/api/auth/login") {
    const op = path.endsWith("signup") ? "signup" : "login";
    const { ok, data } = await call(env, op, { ...body, ip });
    if (!ok) return json(data, 400);
    return json({ user: data.user }, 200, { "Set-Cookie": setCookie(data.token) });
  }

  if (path === "/api/auth/logout") {
    await call(env, "logout", { token: token || "" });
    return json({ ok: true }, 200, { "Set-Cookie": clearCookie });
  }

  if (path === "/api/auth/me") {
    const { data } = await call(env, "me", { token: token || "" });
    return json({ ...data, providers: providers(env) });
  }

  if (path === "/api/prefs") {
    const { ok, data } = await call(env, "prefs", { token, prefs: body.prefs || {} });
    return json(data, ok ? 200 : 401);
  }

  if (path === "/api/love") {
    if (req.method !== "POST") {
      const { data } = await call(env, "love-counts", {},
        new URLSearchParams({ items: url.searchParams.get("items") || "", token: token || "" }).toString());
      return json(data);
    }
    const { ok, data } = await call(env, "love", { ...body, token });
    return json(data, ok ? 200 : 400);
  }

  if (path === "/api/most-loved") {
    const { data } = await call(env, "most-loved", {},
      new URLSearchParams({ limit: url.searchParams.get("limit") || "24" }).toString());
    return json(data, 200, { "Cache-Control": "public, max-age=300" });
  }

  if (path === "/api/survey") {
    if (req.method === "POST") {
      const { ok, data } = await call(env, "survey", { ...body, token });
      return json(data, ok ? 200 : 401);
    }
    const { data } = await call(env, "survey-read", {},
      new URLSearchParams({ item: url.searchParams.get("item") || "", token: token || "" }).toString());
    return json(data);
  }

  if (path === "/api/subscribe") {
    const { ok, data } = await call(env, "subscribe", { ...body, ip });
    return json(data, ok ? 200 : 400);
  }

  if (path === "/api/stats") {
    const { data } = await call(env, "stats");
    return json(data, 200, { "Cache-Control": "public, max-age=600" });
  }

  return json({ error: "not found" }, 404);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);

    if (url.hostname.endsWith(".workers.dev") || url.hostname === "www.motorjury.com") {
      url.hostname = "motorjury.com";
      url.protocol = "https:";
      return Response.redirect(url.toString(), 301);
    }

    const moved = modelRedirect(url);
    if (moved) return Response.redirect(moved, 301);

    if (url.pathname.startsWith("/api/")) {
      try {
        return await api(req, url, env);
      } catch (e) {
        return json({ error: "Something went wrong on our side.", detail: String(e && e.message || e) }, 500);
      }
    }

    return env.ASSETS.fetch(req);
  },
};
