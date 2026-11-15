import { test } from 'node:test';
import assert from 'node:assert/strict';
import { IDS, cleanVotes, cleanDaily, countryCode, dayNumber, juryDispatch, rank, score } from './jury.mjs';

const [A, B, C] = [...IDS];
function fakeHub({ allow = true, rows = [] } = {}) {
  const writes = [];
  return { writes, limit: () => allow, rows: () => rows, sql: { exec: (q, ...args) => writes.push(args) } };
}

test('verdicts accept only two different cars from the reviewed list', () => {
  assert.deepEqual(cleanVotes([[A, B]]), [[A, B]]);
  for (const bad of [null, [], [[A, A]], [[A, 'Q0']], [[A]], [[A, B, C]], ['x'], Array(26).fill([A, B]), [[A, "'; DROP TABLE users;--"]]]) {
    assert.throws(() => cleanVotes(bad));
  }
});

test('a rejected batch writes nothing', async () => {
  const hub = fakeHub();
  await assert.rejects(juryDispatch(hub, 'jury-votes', { v: [[A, B], [A, 'Q0']], ip: '1.2.3.4' }, {}));
  assert.equal(hub.writes.length, 0);
  const limited = fakeHub({ allow: false });
  await assert.rejects(juryDispatch(limited, 'jury-votes', { v: [[A, B]], ip: '1.2.3.4' }, {}));
  assert.equal(limited.writes.length, 0);
});

test('one verdict counts a win and a showing, worldwide and per country', async () => {
  const hub = fakeHub();
  assert.deepEqual(await juryDispatch(hub, 'jury-votes', { v: [[A, B]], ip: '1.2.3.4', cc: 'PT' }, {}), { ok: true, counted: 1 });
  assert.deepEqual(hub.writes, [[A, '', 1], [B, '', 0], [A, 'PT', 1], [B, 'PT', 0]]);
  const anonymous = fakeHub();
  await juryDispatch(anonymous, 'jury-votes', { v: [[A, B]], ip: '1.2.3.4', cc: '<script>' }, {});
  assert.equal(anonymous.writes.length, 2);
});

test('country codes are two capital letters and never a placeholder', () => {
  assert.equal(countryCode('PT'), 'PT');
  for (const bad of ['pt', 'XX', 'T1', 'PRT', '', null, 7]) assert.equal(countryCode(bad), '');
});

test('ranking rewards proven favourites over tiny samples and hides unknown cars', () => {
  assert.ok(score(80, 100) > score(2, 2));
  assert.equal(score(0, 0), 0);
  const ranked = rank([{ id: A, wins: 80, shows: 100 }, { id: B, wins: 5, shows: 5 }, { id: C, wins: 4, shows: 4 },
    { id: 'Q0', wins: 99, shows: 99 }, { id: B + 'x', wins: 9, shows: 9 }]);
  assert.deepEqual(ranked.map((r) => r.id), [A, B]);
});

test('daily picks must be ten binary answers for a current round', () => {
  const picks = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1];
  assert.deepEqual(cleanDaily({ day: 5, picks }, 5), { day: 5, picks });
  assert.deepEqual(cleanDaily({ day: 4, picks }, 5).day, 4);
  for (const bad of [{ day: 3, picks }, { day: 7, picks }, { day: 0, picks }, { day: 5.5, picks }, { day: 5, picks: picks.slice(1) },
    { day: 5, picks: [...picks.slice(1), 2] }, { day: '5', picks }, {}]) assert.throws(() => cleanDaily(bad, 5));
});

test('a daily round stores one tally per pick and returns the split', async () => {
  const today = dayNumber();
  const hub = fakeHub({ rows: [{ idx: 0, a: 3, b: 1 }, { idx: 99, a: 9, b: 9 }] });
  const out = await juryDispatch(hub, 'jury-daily', { day: today, picks: [1, 0, 0, 0, 0, 0, 0, 0, 0, 0], ip: '1.2.3.4' }, {});
  assert.equal(hub.writes.length, 10);
  assert.deepEqual(hub.writes[0], [today, 0, 0, 1]);
  assert.deepEqual(out.split[0], [3, 1]);
  assert.equal(out.split.length, 10);
});

test('the first day is launch day', () => {
  assert.equal(dayNumber(Date.UTC(2026, 10, 15, 12)), 1);
  assert.equal(dayNumber(Date.UTC(2026, 10, 16, 0, 0, 1)), 2);
});

test('the browser and the Worker agree on the daily round number', async () => {
  const client = await import('../assets/jury-core.mjs');
  for (const now of [Date.UTC(2026, 10, 15), Date.UTC(2027, 1, 1, 23, 59)]) assert.equal(client.dayNumber(now), dayNumber(now));
  assert.equal(client.DAILY_PICKS, 10);
});

test('a jury-room comment is plain text without links, markup or hidden characters', async () => {
  const { cleanComment, cleanThread, publicName, sharedGarage } = await import('./jury.mjs');
  assert.equal(cleanComment('  The F40,\n easily.  '), 'The F40, easily.');
  for (const bad of ['', 'x', 'a'.repeat(301), 'see http://x.y', 'visit www.spam.example', 'cheap-cars.com now', '<b>hi</b>', 7, null]) assert.throws(() => cleanComment(bad));
  assert.equal(cleanComment('right‮evil'), 'right evil');
  assert.equal(cleanThread(A), A);
  assert.equal(cleanThread('daily:3', 3), 'daily:3');
  for (const bad of ['Q0', 'daily:0', 'daily:9', 'daily:x', '', null, 'x'.repeat(50)]) assert.throws(() => cleanThread(bad, 3));
  assert.equal(publicName('Jane Doe'), 'Jane');
  assert.equal(publicName('<script>'), 'script');
  assert.equal(publicName(''), 'Juror');
  assert.deepEqual(sharedGarage('?g=' + A.slice(1) + '.' + B.slice(1) + '.0').map((c) => c.id), [A, B]);
  assert.deepEqual(sharedGarage('?g=<script>'), []);
});

test('only a signed-in visitor can speak, and a rejected comment is not stored', async () => {
  const hub = { ...fakeHub(), userForToken: async (t) => (t === 'ok' ? { id: 'u1', name: 'Jane Doe' } : null) };
  await assert.rejects(juryDispatch(hub, 'jury-talk', { token: '', thread: A, body: 'Hello there' }, {}), /Sign in/);
  await assert.rejects(juryDispatch(hub, 'jury-talk', { token: 'ok', thread: A, body: 'http://spam' }, {}));
  await assert.rejects(juryDispatch(hub, 'jury-talk', { token: 'ok', thread: 'Q0', body: 'Hello there' }, {}));
  assert.equal(hub.writes.length, 0);
  await juryDispatch(hub, 'jury-talk', { token: 'ok', thread: A, body: 'Hello there' }, {});
  assert.deepEqual(hub.writes[0].slice(0, 4), [A, 'u1', 'Jane', 'Hello there']);
});
