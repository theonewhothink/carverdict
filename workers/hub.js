/**
 * hub.js — MotorJury's account and engagement store.
 *
 * WHY A DURABLE OBJECT
 * --------------------
 * The site was static assets end to end, so everything it knew about a reader lived in that
 * reader's localStorage: ratings, garage, preferences. Clear the browser and the reader
 * stopped existing; open the site on a phone and none of it followed. Accounts fix that,
 * and accounts need a database.
 *
 * A Durable Object with the SQLite storage backend is the only database Cloudflare will
 * create for us with no console visit, no API token and no database id to paste into a
 * config file — the namespace is provisioned by the deploy itself. D1 or KV would each have
 * blocked this behind a credential only Mr. Adir can produce, and a feature that ships
 * "pending an account signup" has not shipped.
 *
 * One instance, named "hub", holds everything. At this site's traffic a single object is
 * comfortably inside a DO's throughput; sharding by user only becomes worth its complexity
 * when the love counters are hot enough to feel it, and the counter table is already the
 * shape that would shard.
 *
 * PRIVACY. Stored: email, a PBKDF2 hash of the password (never the password), a display
 * name, the reader's own likes/garage/preferences, and survey answers. Session tokens are
 * stored hashed, so a database dump cannot be replayed as a login. No tracking, no profile
 * sale, no third-party beacons.
 */

const PBKDF2_ITER = 210000;   // OWASP 2024 floor for PBKDF2-HMAC-SHA256
const SESSION_DAYS = 180;

const enc = new TextEncoder();

function hex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function randomHex(bytes = 32) {
  return hex(crypto.getRandomValues(new Uint8Array(bytes)));
}

async function sha256(s) {
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(s)));
}

async function hashPassword(password, salt) {
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: enc.encode(salt), iterations: PBKDF2_ITER },
    key, 256);
  return hex(bits);
}

/** Constant-time-ish comparison. Both sides are fixed-length hex here. */
function same(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export class HubDO {
  constructor(state) {
    this.sql = state.storage.sql;
    this.init();
  }

  init() {
    const s = this.sql;
    s.exec(`CREATE TABLE IF NOT EXISTS users(
      id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT,
      pw_hash TEXT, pw_salt TEXT, provider TEXT, provider_id TEXT,
      created INTEGER, last_seen INTEGER, prefs TEXT)`);
    s.exec(`CREATE TABLE IF NOT EXISTS sessions(
      token_hash TEXT PRIMARY KEY, user_id TEXT, created INTEGER, expires INTEGER)`);
    s.exec(`CREATE TABLE IF NOT EXISTS likes(
      user_id TEXT, item TEXT, name TEXT, url TEXT, created INTEGER,
      PRIMARY KEY(user_id, item))`);
    s.exec(`CREATE TABLE IF NOT EXISTS like_counts(item TEXT PRIMARY KEY, n INTEGER)`);
    s.exec(`CREATE TABLE IF NOT EXISTS survey(
      user_id TEXT, item TEXT, overall INTEGER, reliability INTEGER, running_cost INTEGER,
      would_buy_again INTEGER, years_owned INTEGER, comment TEXT, created INTEGER,
      PRIMARY KEY(user_id, item))`);
    s.exec(`CREATE TABLE IF NOT EXISTS survey_rollup(
      item TEXT PRIMARY KEY, n INTEGER, overall REAL, reliability REAL,
      running_cost REAL, again_pct REAL, updated INTEGER)`);
    s.exec(`CREATE TABLE IF NOT EXISTS subscribers(
      email TEXT PRIMARY KEY, created INTEGER, source TEXT)`);
    s.exec(`CREATE TABLE IF NOT EXISTS rate(k TEXT PRIMARY KEY, n INTEGER, window INTEGER)`);
    s.exec(`CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)`);
    s.exec(`CREATE INDEX IF NOT EXISTS idx_likes_item ON likes(item)`);
  }

  rows(q, ...a) { return this.sql.exec(q, ...a).toArray(); }
  one(q, ...a) { const r = this.rows(q, ...a); return r.length ? r[0] : null; }

  /** Fixed-window limiter. Cheap, in the same database, no extra binding. */
  limit(key, max, windowSec) {
    const now = Math.floor(Date.now() / 1000);
    const w = Math.floor(now / windowSec);
    const row = this.one(`SELECT n, window FROM rate WHERE k=?`, key);
    if (!row || row.window !== w) {
      this.sql.exec(`INSERT INTO rate(k,n,window) VALUES(?,1,?)
        ON CONFLICT(k) DO UPDATE SET n=1, window=excluded.window`, key, w);
      return true;
    }
    if (row.n >= max) return false;
    this.sql.exec(`UPDATE rate SET n=n+1 WHERE k=?`, key);
    return true;
  }

  async newSession(userId) {
    const token = randomHex(32);
    const now = Date.now();
    this.sql.exec(`INSERT INTO sessions(token_hash,user_id,created,expires) VALUES(?,?,?,?)`,
      await sha256(token), userId, now, now + SESSION_DAYS * 864e5);
    this.sql.exec(`DELETE FROM sessions WHERE expires < ?`, now);
    return token;
  }

  async userForToken(token) {
    if (!token) return null;
    const row = this.one(`SELECT user_id, expires FROM sessions WHERE token_hash=?`, await sha256(token));
    if (!row || row.expires < Date.now()) return null;
    const u = this.one(`SELECT * FROM users WHERE id=?`, row.user_id);
    if (u) this.sql.exec(`UPDATE users SET last_seen=? WHERE id=?`, Date.now(), u.id);
    return u;
  }

  publicUser(u) {
    if (!u) return null;
    return {
      id: u.id, email: u.email, name: u.name, provider: u.provider || "email",
      prefs: u.prefs ? JSON.parse(u.prefs) : {},
      likes: this.rows(`SELECT item, name, url, created FROM likes WHERE user_id=? ORDER BY created DESC`, u.id),
      ratings: this.rows(`SELECT item, overall, reliability, running_cost, would_buy_again,
                          years_owned, created FROM survey WHERE user_id=? ORDER BY created DESC`, u.id),
    };
  }

  recountLike(item) {
    const n = this.one(`SELECT COUNT(*) AS n FROM likes WHERE item=?`, item).n;
    this.sql.exec(`INSERT INTO like_counts(item,n) VALUES(?,?)
      ON CONFLICT(item) DO UPDATE SET n=excluded.n`, item, n);
    return n;
  }

  rollupSurvey(item) {
    const r = this.one(`SELECT COUNT(*) n, AVG(overall) o, AVG(reliability) rel,
      AVG(running_cost) rc, AVG(would_buy_again)*100 again FROM survey WHERE item=?`, item);
    this.sql.exec(`INSERT INTO survey_rollup(item,n,overall,reliability,running_cost,again_pct,updated)
      VALUES(?,?,?,?,?,?,?) ON CONFLICT(item) DO UPDATE SET n=excluded.n, overall=excluded.overall,
      reliability=excluded.reliability, running_cost=excluded.running_cost,
      again_pct=excluded.again_pct, updated=excluded.updated`,
      item, r.n, r.o, r.rel, r.rc, r.again, Date.now());
    return r;
  }

  async fetch(req) {
    const url = new URL(req.url);
    const op = url.pathname.slice(1);
    const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
    const q = Object.fromEntries(url.searchParams);
    try {
      const out = await this.dispatch(op, body, q);
      return Response.json(out);
    } catch (e) {
      return Response.json({ error: String(e && e.message || e) }, { status: 400 });
    }
  }

  async dispatch(op, b, q) {
    const now = Date.now();
    switch (op) {

      case "signup": {
        const email = String(b.email || "").trim().toLowerCase();
        const pw = String(b.password || "");
        if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(email)) throw new Error("That email address does not look right.");
        if (pw.length < 8) throw new Error("Use at least 8 characters.");
        if (!this.limit("signup:" + (b.ip || "?"), 8, 3600)) throw new Error("Too many attempts. Try again later.");
        if (this.one(`SELECT id FROM users WHERE email=?`, email)) throw new Error("That email already has an account. Sign in instead.");
        const salt = randomHex(16);
        const id = randomHex(12);
        this.sql.exec(`INSERT INTO users(id,email,name,pw_hash,pw_salt,provider,created,last_seen,prefs)
          VALUES(?,?,?,?,?,'email',?,?,?)`,
          id, email, String(b.name || "").slice(0, 60) || email.split("@")[0],
          await hashPassword(pw, salt), salt, now, now, JSON.stringify(b.prefs || {}));
        const token = await this.newSession(id);
        return { token, user: this.publicUser(this.one(`SELECT * FROM users WHERE id=?`, id)) };
      }

      case "login": {
        const email = String(b.email || "").trim().toLowerCase();
        if (!this.limit("login:" + email, 10, 900)) throw new Error("Too many attempts. Try again in a few minutes.");
        const u = this.one(`SELECT * FROM users WHERE email=?`, email);
        // Same message either way: a different one tells a stranger which emails exist here.
        const bad = new Error("Email or password is not right.");
        if (!u || !u.pw_hash) throw bad;
        if (!same(await hashPassword(String(b.password || ""), u.pw_salt), u.pw_hash)) throw bad;
        return { token: await this.newSession(u.id), user: this.publicUser(u) };
      }

      case "oauth": {
        // Google and Apple both land here once the Worker has verified the identity token.
        const email = String(b.email || "").trim().toLowerCase();
        const provider = String(b.provider || "oauth");
        if (!email) throw new Error("The sign-in provider returned no email address.");
        let u = this.one(`SELECT * FROM users WHERE email=?`, email);
        if (!u) {
          const id = randomHex(12);
          this.sql.exec(`INSERT INTO users(id,email,name,provider,provider_id,created,last_seen,prefs)
            VALUES(?,?,?,?,?,?,?,'{}')`, id, email, String(b.name || "").slice(0, 60) || email.split("@")[0],
            provider, String(b.sub || ""), now, now);
          u = this.one(`SELECT * FROM users WHERE id=?`, id);
        } else if (!u.provider_id) {
          this.sql.exec(`UPDATE users SET provider=?, provider_id=? WHERE id=?`, provider, String(b.sub || ""), u.id);
        }
        return { token: await this.newSession(u.id), user: this.publicUser(u) };
      }

      case "me": {
        const u = await this.userForToken(b.token || q.token);
        return { user: this.publicUser(u) };
      }

      case "logout": {
        const t = b.token || q.token;
        if (t) this.sql.exec(`DELETE FROM sessions WHERE token_hash=?`, await sha256(t));
        return { ok: true };
      }

      case "prefs": {
        const u = await this.userForToken(b.token);
        if (!u) throw new Error("Not signed in.");
        if (JSON.stringify(b.prefs || {}).length > 100000) throw new Error("Preferences are too large.");
        const merged = Object.assign(u.prefs ? JSON.parse(u.prefs) : {}, b.prefs || {});
        this.sql.exec(`UPDATE users SET prefs=? WHERE id=?`, JSON.stringify(merged), u.id);
        return { prefs: merged };
      }

      case "love": {
        // Toggling needs an account; reading a count never does.
        const item = String(b.item || "").slice(0, 160);
        if (!item) throw new Error("No car given.");
        const u = await this.userForToken(b.token);
        if (!u) return { count: this.one(`SELECT n FROM like_counts WHERE item=?`, item)?.n || 0, anonymous: true };
        const has = this.one(`SELECT item FROM likes WHERE user_id=? AND item=?`, u.id, item);
        if (has) this.sql.exec(`DELETE FROM likes WHERE user_id=? AND item=?`, u.id, item);
        else this.sql.exec(`INSERT INTO likes(user_id,item,name,url,created) VALUES(?,?,?,?,?)`,
          u.id, item, String(b.name || "").slice(0, 120), String(b.url || "").slice(0, 200), now);
        return { count: this.recountLike(item), loved: !has };
      }

      case "love-counts": {
        const items = String(q.items || "").split(",").filter(Boolean).slice(0, 60);
        const out = {};
        for (const it of items) out[it] = this.one(`SELECT n FROM like_counts WHERE item=?`, it)?.n || 0;
        let mine = [];
        const u = await this.userForToken(q.token);
        if (u) mine = this.rows(`SELECT item FROM likes WHERE user_id=?`, u.id).map((r) => r.item);
        return { counts: out, mine };
      }

      case "most-loved": {
        return { items: this.rows(
          `SELECT item, COUNT(*) n,
                  (SELECT name FROM likes n2 WHERE n2.item=likes.item ORDER BY created DESC LIMIT 1) name,
                  (SELECT url  FROM likes u2 WHERE u2.item=likes.item ORDER BY created DESC LIMIT 1) url
           FROM likes GROUP BY item HAVING COUNT(*) > 0 ORDER BY n DESC, item LIMIT ?`,
          Math.min(+q.limit || 24, 60)) };
      }

      case "survey": {
        const u = await this.userForToken(b.token);
        if (!u) throw new Error("Sign in to add your car — one response per owner, which is the only way the averages mean anything.");
        const item = String(b.item || "").slice(0, 160);
        if (!item) throw new Error("No car given.");
        const n = (x, lo, hi) => Math.max(lo, Math.min(hi, Math.round(+x || 0)));
        this.sql.exec(`INSERT INTO survey(user_id,item,overall,reliability,running_cost,
          would_buy_again,years_owned,comment,created) VALUES(?,?,?,?,?,?,?,?,?)
          ON CONFLICT(user_id,item) DO UPDATE SET overall=excluded.overall,
          reliability=excluded.reliability, running_cost=excluded.running_cost,
          would_buy_again=excluded.would_buy_again, years_owned=excluded.years_owned,
          comment=excluded.comment, created=excluded.created`,
          u.id, item, n(b.overall, 1, 5), n(b.reliability, 1, 5), n(b.running_cost, 1, 5),
          b.would_buy_again ? 1 : 0, n(b.years_owned, 0, 40),
          String(b.comment || "").slice(0, 900), now);
        return { rollup: this.rollupSurvey(item), saved: true };
      }

      case "survey-read": {
        const item = String(q.item || "");
        const r = this.one(`SELECT * FROM survey_rollup WHERE item=?`, item) || { n: 0 };
        let mine = null;
        const u = await this.userForToken(q.token);
        if (u) mine = this.one(`SELECT * FROM survey WHERE user_id=? AND item=?`, u.id, item);
        const comments = this.rows(
          `SELECT comment, years_owned, overall, created FROM survey
           WHERE item=? AND comment <> '' ORDER BY created DESC LIMIT 8`, item);
        return { rollup: r, mine, comments };
      }

      case "subscribe": {
        const email = String(b.email || "").trim().toLowerCase();
        if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(email)) throw new Error("That email address does not look right.");
        if (!this.limit("sub:" + (b.ip || "?"), 12, 3600)) throw new Error("Too many attempts.");
        this.sql.exec(`INSERT OR IGNORE INTO subscribers(email,created,source) VALUES(?,?,?)`,
          email, now, String(b.source || "").slice(0, 60));
        return { ok: true };
      }

      case "stats": {
        return {
          users: this.one(`SELECT COUNT(*) n FROM users`).n,
          likes: this.one(`SELECT COUNT(*) n FROM likes`).n,
          surveys: this.one(`SELECT COUNT(*) n FROM survey`).n,
          subscribers: this.one(`SELECT COUNT(*) n FROM subscribers`).n,
        };
      }

      default:
        throw new Error("unknown operation");
    }
  }
}
