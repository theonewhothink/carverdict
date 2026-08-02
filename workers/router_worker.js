/**
 * router_worker.js — Carsite Cloudflare Worker (Phase 5).
 * Duties: /api/calc/*, /api/subscribe (D1 + Resend double opt-in), IndexNow trigger,
 * security headers. Static pages are served by Cloudflare Pages; this worker is bound
 * on /api/* and /_ops/* routes.
 *
 * Bindings required (wrangler.toml): DB (D1), env vars RESEND_API_KEY, INDEXNOW_KEY, SITE_ORIGIN.
 */

const SEC_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
};

const json = (obj, status = 200, extra = {}) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...SEC_HEADERS, ...extra },
  });

// ---- calculators (mirror of the static calculator, served as API for tools/licensing) ----
const MAINT_BAND = [
  [0, 2, 450, 900], [3, 5, 700, 1300], [6, 8, 950, 1700],
  [9, 12, 1200, 2200], [13, 30, 1500, 2800],
];
const CURRENT_YEAR = 2026;

function bandFor(age) {
  for (const [a0, a1, lo, hi] of MAINT_BAND) if (age >= a0 && age <= a1) return [lo, hi];
  return [1500, 2800];
}

function calcTrueCost({ year, annual_fuel_cost = 1900, keep_years = 5 }) {
  const age0 = Math.max(0, CURRENT_YEAR - year);
  let lo = 0, hi = 0;
  for (let k = 0; k < keep_years; k++) {
    const [ml, mh] = bandFor(age0 + k);
    lo += annual_fuel_cost + ml;
    hi += annual_fuel_cost + mh;
  }
  return {
    keep_years,
    total_low: lo, total_high: hi,
    annual_low: Math.round(lo / keep_years), annual_high: Math.round(hi / keep_years),
    note: "Estimates: EPA annual fuel cost + age-indexed industry maintenance bands. See /methodology/.",
  };
}

function calcRepairOrSell({ vehicle_value, repair_cost, annual_repair_trend = 0.15 }) {
  const ratio = repair_cost / Math.max(1, vehicle_value);
  const verdict = ratio > 0.5 ? "SELL" : ratio > 0.25 ? "BORDERLINE" : "REPAIR";
  return {
    ratio: +ratio.toFixed(2), verdict,
    next_year_repair_estimate: Math.round(repair_cost * (1 + annual_repair_trend)),
    note: "Rule-of-thumb thresholds (50% sell / 25% borderline); repair trend from CarMD index. Estimate.",
  };
}

function calcEvVsGas({ miles_per_year = 12000, gas_price = 3.5, mpg = 28, kwh_price = 0.16, kwh_per_100mi = 30 }) {
  const gas = (miles_per_year / mpg) * gas_price;
  const ev = (miles_per_year / 100) * kwh_per_100mi * kwh_price;
  return {
    gas_annual_fuel: Math.round(gas), ev_annual_energy: Math.round(ev),
    ev_saves: Math.round(gas - ev),
    note: "Fuel/energy only; excludes purchase price, insurance, battery risk. Estimate.",
  };
}

// ---- subscribe: double opt-in via Resend, store in D1 ----
async function subscribe(req, env) {
  const { email } = await req.json().catch(() => ({}));
  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return json({ error: "invalid email" }, 400);
  const token = crypto.randomUUID();
  await env.DB.prepare(
    "INSERT INTO subscribers(email, token, confirmed, created) VALUES(?1, ?2, 0, datetime('now')) " +
    "ON CONFLICT(email) DO UPDATE SET token = ?2"
  ).bind(email, token).run();
  const confirmUrl = `${env.SITE_ORIGIN}/api/subscribe/confirm?token=${token}`;
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: `CarVerdict <newsletter@${new URL(env.SITE_ORIGIN).hostname}>`,
      to: email,
      subject: "Confirm your CarVerdict subscription",
      text: `Confirm your subscription (double opt-in): ${confirmUrl}\nIf you didn't request this, ignore this email.`,
    }),
  });
  return json({ ok: true, message: "confirmation email sent" });
}

async function confirmSubscribe(url, env) {
  const token = url.searchParams.get("token");
  const r = await env.DB.prepare("UPDATE subscribers SET confirmed=1 WHERE token=?1").bind(token).run();
  const ok = r.meta.changes > 0;
  return new Response(ok ? "Subscription confirmed. Welcome." : "Invalid or expired token.", {
    status: ok ? 200 : 400, headers: { "Content-Type": "text/plain", ...SEC_HEADERS },
  });
}

// ---- IndexNow: POST changed URLs (called by CI after deploy) ----
async function indexNow(req, env) {
  const { urls } = await req.json().catch(() => ({ urls: [] }));
  if (!urls?.length) return json({ error: "no urls" }, 400);
  const host = new URL(env.SITE_ORIGIN).hostname;
  const r = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ host, key: env.INDEXNOW_KEY, keyLocation: `${env.SITE_ORIGIN}/${env.INDEXNOW_KEY}.txt`, urlList: urls.slice(0, 10000) }),
  });
  return json({ ok: r.ok, status: r.status, submitted: Math.min(urls.length, 10000) });
}

export { calcTrueCost, calcRepairOrSell, calcEvVsGas, bandFor };

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;
    try {
      if (p === "/api/calc/true-cost" && req.method === "POST") return json(calcTrueCost(await req.json()));
      if (p === "/api/calc/repair-or-sell" && req.method === "POST") return json(calcRepairOrSell(await req.json()));
      if (p === "/api/calc/ev-vs-gas" && req.method === "POST") return json(calcEvVsGas(await req.json()));
      if (p === "/api/subscribe" && req.method === "POST") return subscribe(req, env);
      if (p === "/api/subscribe/confirm") return confirmSubscribe(url, env);
      if (p === "/_ops/indexnow" && req.method === "POST") {
        // protect with a shared secret header set in CI
        if (req.headers.get("x-ops-key") !== env.OPS_KEY) return json({ error: "forbidden" }, 403);
        return indexNow(req, env);
      }
      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: "internal", detail: String(e) }, 500);
    }
  },
};
