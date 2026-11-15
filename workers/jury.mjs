// The car jury: anonymous pick-one-of-two verdicts, counted per car and per country.
// Stored: counters only. The visitor address is hashed for rate limiting and never kept
// beside a verdict. Car ids are accepted only from the reviewed, licensed jury list.
import CARS from '../data/jury_cars.json' with {type:'json'};

export const IDS = new Set(CARS.map((c) => c.id));
export const MAX_BATCH = 25;
export const DAILY_PICKS = 10;
const LAUNCH = Date.UTC(2026, 10, 15);

export function dayNumber(now = Date.now()) {
  return Math.floor((now - LAUNCH) / 864e5) + 1;
}

export function countryCode(value) {
  return typeof value === 'string' && /^[A-Z]{2}$/.test(value) && !['XX', 'T1'].includes(value) ? value : '';
}

export function cleanVotes(value) {
  if (!Array.isArray(value) || !value.length || value.length > MAX_BATCH) throw new Error('Send between 1 and 25 verdicts.');
  return value.map((pair) => {
    if (!Array.isArray(pair) || pair.length !== 2 || !IDS.has(pair[0]) || !IDS.has(pair[1]) || pair[0] === pair[1]) {
      throw new Error('Unknown car in verdict.');
    }
    return [pair[0], pair[1]];
  });
}

export function cleanDaily(body, today = dayNumber()) {
  const day = body?.day;
  // One day of slack either side: the visitor's clock and time zone are not ours.
  if (!Number.isInteger(day) || day < 1 || Math.abs(day - today) > 1) throw new Error('That daily round is closed.');
  const picks = body.picks;
  if (!Array.isArray(picks) || picks.length !== DAILY_PICKS || picks.some((p) => p !== 0 && p !== 1)) {
    throw new Error('Send all ten daily picks.');
  }
  return { day, picks };
}

/** Wilson lower bound: a car shown twice and picked twice must not outrank a proven favourite. */
export function score(wins, shows) {
  if (!shows) return 0;
  const z = 1.96, p = wins / shows;
  return (p + z * z / (2 * shows) - z * Math.sqrt((p * (1 - p) + z * z / (4 * shows)) / shows)) / (1 + z * z / shows);
}

export function rank(rows, limit = 50, minShows = 5) {
  return rows.filter((r) => IDS.has(r.id) && r.shows >= minShows && r.wins <= r.shows)
    .map((r) => ({ id: r.id, w: r.wins, s: r.shows, r: Math.round(score(r.wins, r.shows) * 1000) / 1000 }))
    .sort((a, b) => b.r - a.r || b.s - a.s || a.id.localeCompare(b.id)).slice(0, limit);
}

/** A garage link carries car numbers only; anything else is not a garage. */
export function sharedGarage(search) {
  const raw = new URLSearchParams(search).get('g') || '';
  if (!/^\d{1,12}(\.\d{1,12}){0,9}$/.test(raw)) return [];
  const byId = new Map(CARS.map((c) => [c.id, c]));
  return [...new Set(raw.split('.').map((n) => 'Q' + n))].filter((id) => byId.has(id)).map((id) => byId.get(id));
}

/** Jury-room threads belong to one car or to one recent daily round. */
export function cleanThread(value, today = dayNumber()) {
  if (typeof value === 'string' && IDS.has(value)) return value;
  const m = /^daily:(\d{1,6})$/.exec(typeof value === 'string' ? value : '');
  if (m && Number(m[1]) >= 1 && Number(m[1]) <= today + 1) return 'daily:' + Number(m[1]);
  throw new Error('Unknown jury room.');
}

/** Plain text only: no links, no markup, no control characters. */
export function cleanComment(value) {
  if (typeof value !== 'string') throw new Error('Write a comment first.');
  const text = value.replace(/[\u0000-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g, ' ').replace(/\s+/g, ' ').trim();
  if (text.length < 2 || text.length > 300) throw new Error('Keep it between 2 and 300 characters.');
  if (/https?:|www\.|[<>]|\b[\w-]+\.(com|net|org|io|ru|cn|co|info|xyz|top|shop|app|link|me)\b/i.test(text)) throw new Error('Links and markup are not allowed in the jury room.');
  return text;
}

/** Only a first name is shown in public. */
export function publicName(name) {
  const first = String(name || '').replace(/[^\p{L}\p{N} '-]/gu, '').trim().split(/\s+/)[0] || 'Juror';
  return first.slice(0, 24);
}

async function visitor(ip) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('jury|' + (ip || '?')));
  return 'j:' + [...new Uint8Array(bytes)].slice(0, 12).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function juryTables(sql) {
  sql.exec(`CREATE TABLE IF NOT EXISTS jury_counts(
    id TEXT, cc TEXT, wins INTEGER NOT NULL DEFAULT 0, shows INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(id, cc))`);
  sql.exec(`CREATE TABLE IF NOT EXISTS jury_talk(
    id INTEGER PRIMARY KEY AUTOINCREMENT, thread TEXT, user_id TEXT, name TEXT, body TEXT,
    created INTEGER, reports INTEGER NOT NULL DEFAULT 0)`);
  sql.exec(`CREATE INDEX IF NOT EXISTS idx_jury_talk_thread ON jury_talk(thread, id)`);
  sql.exec(`CREATE TABLE IF NOT EXISTS jury_talk_reports(comment_id INTEGER, reporter TEXT, PRIMARY KEY(comment_id, reporter))`);
  sql.exec(`CREATE TABLE IF NOT EXISTS jury_daily(
    day INTEGER, idx INTEGER, a INTEGER NOT NULL DEFAULT 0, b INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(day, idx))`);
}

export async function juryDispatch(hub, op, b, q) {
  const bump = (id, cc, win) => hub.sql.exec(`INSERT INTO jury_counts(id,cc,wins,shows) VALUES(?,?,?,1)
    ON CONFLICT(id,cc) DO UPDATE SET wins=wins+excluded.wins, shows=shows+1`, id, cc, win);
  switch (op) {
    case 'jury-votes': {
      const votes = cleanVotes(b.v);
      const who = await visitor(b.ip);
      // shortcut: per-address caps only; a distributed bot can still skew the ranking.
      // Upgrade to a signed per-session token or Turnstile when the ranking is cited.
      if (!hub.limit(who + ':h', 200, 3600) || !hub.limit(who + ':d', 1500, 86400)) {
        throw new Error('The jury needs a short recess. Try again later.');
      }
      const cc = countryCode(b.cc);
      for (const [winner, loser] of votes) {
        bump(winner, '', 1); bump(loser, '', 0);
        if (cc) { bump(winner, cc, 1); bump(loser, cc, 0); }
      }
      return { ok: true, counted: votes.length };
    }
    case 'jury-ranking': {
      const cc = countryCode(q.cc);
      const rows = hub.rows(`SELECT id, wins, shows FROM jury_counts WHERE cc=?`, cc);
      const total = rows.reduce((n, r) => n + r.wins, 0);
      return { cc, total, cars: rank(rows) };
    }
    case 'jury-stats': {
      const out = {};
      for (const r of hub.rows(`SELECT id, wins, shows FROM jury_counts WHERE cc=''`)) if (IDS.has(r.id)) out[r.id] = [r.wins, r.shows];
      return { cars: out };
    }
    case 'jury-talk-read': {
      const thread = cleanThread(q.thread);
      return { thread, comments: hub.rows(`SELECT id, name, body, created FROM jury_talk
        WHERE thread=? AND reports < 3 ORDER BY id DESC LIMIT 30`, thread) };
    }
    case 'jury-talk': {
      const user = await hub.userForToken(b.token);
      if (!user) throw new Error('Sign in to speak in the jury room.');
      const thread = cleanThread(b.thread), body = cleanComment(b.body);
      if (!hub.limit('jt:' + user.id + ':m', 5, 600) || !hub.limit('jt:' + user.id + ':d', 30, 86400)) {
        throw new Error('You are posting quickly. Try again in a few minutes.');
      }
      hub.sql.exec(`INSERT INTO jury_talk(thread,user_id,name,body,created) VALUES(?,?,?,?,?)`,
        thread, user.id, publicName(user.name), body, Date.now());
      return juryDispatch(hub, 'jury-talk-read', {}, { thread });
    }
    case 'jury-talk-report': {
      const id = Number(b.id);
      if (!Number.isInteger(id) || id < 1) throw new Error('Unknown comment.');
      const user = await hub.userForToken(b.token);
      const reporter = user ? 'u:' + user.id : await visitor(b.ip);
      if (!hub.limit(reporter + ':report', 20, 86400)) throw new Error('Too many reports today.');
      if (!hub.rows(`SELECT id FROM jury_talk WHERE id=?`, id).length) throw new Error('Unknown comment.');
      hub.sql.exec(`INSERT OR IGNORE INTO jury_talk_reports(comment_id,reporter) VALUES(?,?)`, id, reporter);
      // Three different reporters hide a comment until the publisher reviews it.
      hub.sql.exec(`UPDATE jury_talk SET reports=(SELECT COUNT(*) FROM jury_talk_reports WHERE comment_id=?) WHERE id=?`, id, id);
      return { ok: true };
    }
    case 'jury-daily': {
      const { day, picks } = cleanDaily(b);
      const who = await visitor(b.ip);
      if (!hub.limit(who + ':daily', 20, 86400)) throw new Error('Today’s round is already counted for this connection.');
      picks.forEach((p, idx) => hub.sql.exec(`INSERT INTO jury_daily(day,idx,a,b) VALUES(?,?,?,?)
        ON CONFLICT(day,idx) DO UPDATE SET a=a+excluded.a, b=b+excluded.b`, day, idx, p === 0 ? 1 : 0, p === 1 ? 1 : 0));
      // fall through to the read so the visitor sees the world's split at once
      return juryDispatch(hub, 'jury-daily-read', {}, { day: String(day) });
    }
    case 'jury-daily-read': {
      const day = Number(q.day);
      if (!Number.isInteger(day) || day < 1 || day > dayNumber() + 1) throw new Error('Unknown daily round.');
      const split = Array.from({ length: DAILY_PICKS }, () => [0, 0]);
      for (const r of hub.rows(`SELECT idx, a, b FROM jury_daily WHERE day=?`, day)) {
        if (r.idx >= 0 && r.idx < DAILY_PICKS) split[r.idx] = [r.a, r.b];
      }
      return { day, split };
    }
    default:
      throw new Error('unknown operation');
  }
}
