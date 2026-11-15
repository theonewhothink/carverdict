import { test } from 'node:test';
import assert from 'node:assert/strict';
import { BAYS, agreement, cleanGarage, dailyPairs, drawPair, garageLink, park, parseGarage, seededRandom, shareText, swap, taste } from './jury-core.mjs';

const ids = Array.from({ length: 40 }, (_, i) => 'Q' + (i + 1));
const set = new Set(ids);

test('a garage holds ten known cars, once each', () => {
  assert.deepEqual(cleanGarage(['Q1', 'Q1', 'Q999', 7, 'Q2'], set), ['Q1', 'Q2']);
  assert.equal(cleanGarage(ids, set).length, BAYS);
  assert.deepEqual(cleanGarage('Q1', set), []);
});

test('a full garage never drops a car without a choice', () => {
  const full = ids.slice(0, BAYS);
  assert.equal(park(full, 'Q30').state, 'full');
  assert.deepEqual(park(full, 'Q30').garage, full);
  assert.equal(park(full, 'Q1').state, 'already');
  assert.deepEqual(park(['Q1'], 'Q2'), { garage: ['Q1', 'Q2'], state: 'parked' });
  assert.deepEqual(swap(full, 'Q1', 'Q30')[0], 'Q30');
  assert.deepEqual(swap(full, 'Q99', 'Q30'), full);
  assert.deepEqual(swap(full, 'Q1', 'Q2'), full);
});

test('every car is shown once before any repeats, and never against itself', () => {
  let deck = []; const seen = [];
  const random = seededRandom(3);
  for (let i = 0; i < ids.length / 2; i++) {
    const next = drawPair(deck, ids, random);
    assert.notEqual(next.pair[0], next.pair[1]);
    seen.push(...next.pair); deck = next.deck;
  }
  assert.equal(new Set(seen).size, ids.length);
  const odd = drawPair(['Q1'], ids, random);
  assert.equal(odd.pair[0], 'Q1'); assert.notEqual(odd.pair[1], 'Q1');
});

test('the daily round is identical for everyone and different tomorrow', () => {
  const today = dailyPairs(ids, 12);
  assert.deepEqual(today, dailyPairs([...ids].reverse(), 12));
  assert.equal(new Set(today.flat()).size, 20);
  assert.notDeepEqual(today, dailyPairs(ids, 13));
});

test('agreement is only called once a pairing has a real majority', () => {
  assert.deepEqual(agreement([0, 1, 0, 0], [[9, 1], [9, 1], [2, 1], [5, 5]]), [true, false, null, null]);
  assert.match(shareText(3, [true, false, null]), /Daily #3\nI sided with the world on 1\/2\n🟩🟥⬜\nhttps:\/\/motorjury\.com\/jury\/$/);
  assert.match(shareText(3, [null]), /among the first jurors/);
});

test('a shared garage link carries only known car numbers', () => {
  assert.equal(garageLink(['Q1', 'Q22']), '/jury/?g=1.22');
  assert.deepEqual(parseGarage('?g=1.22.999', set), ['Q1', 'Q22']);
  for (const bad of ['?g=1,2', '?g=<script>', '?g=', '?g=' + ids.map((x) => x.slice(1)).join('.'), '?x=1']) assert.deepEqual(parseGarage(bad, set), []);
});

test('the taste line reports only what the garage contains', () => {
  assert.equal(taste([{ b: 'Ferrari' }, { b: 'Ferrari' }, { b: 'Lotus' }]), '2 of 3 bays hold a Ferrari');
  assert.equal(taste([{ b: 'Ferrari' }, { b: 'Lotus' }]), '2 marques, no two alike');
  assert.equal(taste([]), '');
});

test('a quiz question has four different options including the unused answer', async () => {
  const { quizRound, nextStreak } = await import('./jury-core.mjs');
  const random = seededRandom(9);
  for (let i = 0; i < 20; i++) {
    const q = quizRound(ids, random, ['Q1', 'Q2']);
    assert.equal(new Set(q.options).size, 4);
    assert.ok(q.options.includes(q.answer));
    assert.ok(!['Q1', 'Q2'].includes(q.answer));
  }
  assert.deepEqual(nextStreak(null, 5), { last: 5, n: 1 });
  assert.deepEqual(nextStreak({ last: 5, n: 3 }, 6), { last: 6, n: 4 });
  assert.deepEqual(nextStreak({ last: 5, n: 3 }, 5), { last: 5, n: 3 });
  assert.deepEqual(nextStreak({ last: 5, n: 3 }, 8), { last: 8, n: 1 });
});
