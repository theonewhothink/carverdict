// Pure rules of the car jury: a ten-bay garage, fair pairings and one shared daily round.
export const BAYS = 10;
export const DAILY_PICKS = 10;
const LAUNCH = Date.UTC(2026, 10, 15);

export function dayNumber(now = Date.now()) { return Math.floor((now - LAUNCH) / 864e5) + 1; }

export function cleanGarage(value, ids) {
  return Array.isArray(value) ? [...new Set(value.filter((id) => typeof id === 'string' && ids.has(id)))].slice(0, BAYS) : [];
}

/** Park a car. A full garage never loses a car silently: the caller must choose one to release. */
export function park(garage, id) {
  if (garage.includes(id)) return { garage, state: 'already' };
  if (garage.length >= BAYS) return { garage, state: 'full' };
  return { garage: [...garage, id], state: 'parked' };
}

export function swap(garage, out, id) {
  if (!garage.includes(out) || garage.includes(id)) return garage;
  return garage.map((x) => (x === out ? id : x));
}

export function seededRandom(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function shuffle(list, random = Math.random) {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Every car appears once before any car appears twice. */
export function drawPair(deck, ids, random = Math.random) {
  let cards = deck.length >= 2 ? deck : [...deck, ...shuffle(ids.filter((id) => !deck.includes(id)), random)];
  return { pair: [cards[0], cards[1]], deck: cards.slice(2) };
}

/** The same ten pairings for every visitor on a given day. */
export function dailyPairs(ids, day) {
  const order = shuffle([...ids].sort(), seededRandom(day * 7919 + 17));
  return Array.from({ length: DAILY_PICKS }, (_, i) => [order[i * 2], order[i * 2 + 1]]);
}

/** How many picks sided with the majority; null while a pairing has too few verdicts to call. */
export function agreement(picks, split, minimum = 5) {
  return picks.map((pick, i) => {
    const [a, b] = split[i] || [0, 0];
    if (a + b < minimum || a === b) return null;
    return (a > b ? 0 : 1) === pick;
  });
}

export function shareText(day, marks, origin = 'https://motorjury.com') {
  const known = marks.filter((m) => m !== null);
  const grid = marks.map((m) => (m === null ? '⬜' : m ? '🟩' : '🟥')).join('');
  const line = known.length ? `I sided with the world on ${known.filter(Boolean).length}/${known.length}` : 'I was among the first jurors today';
  return `MotorJury Daily #${day}\n${line}\n${grid}\n${origin}/jury/`;
}

export function garageLink(garage, origin = '') {
  return origin + '/jury/?g=' + garage.map((id) => id.slice(1)).join('.');
}

export function parseGarage(search, ids) {
  const raw = new URLSearchParams(search).get('g') || '';
  if (!/^\d{1,12}(\.\d{1,12}){0,9}$/.test(raw)) return [];
  return cleanGarage(raw.split('.').map((n) => 'Q' + n), ids);
}

export function taste(cars) {
  const count = new Map();
  for (const car of cars) count.set(car.b, (count.get(car.b) || 0) + 1);
  const [top] = [...count].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (!top) return '';
  return top[1] > 1 ? `${top[1]} of ${cars.length} bays hold a ${top[0]}` : `${count.size} marques, no two alike`;
}

/** One "name that car" question: the answer hidden among three other cars. */
export function quizRound(ids, random = Math.random, used = []) {
  const pool = shuffle(ids.filter((id) => !used.includes(id)), random);
  const answer = pool[0];
  const options = shuffle([answer, ...shuffle(ids.filter((id) => id !== answer), random).slice(0, 3)], random);
  return { answer, options };
}

/** A streak grows on consecutive days, survives a repeat of the same day and restarts after a gap. */
export function nextStreak(streak, day) {
  if (streak && streak.last === day) return streak;
  return { last: day, n: streak && streak.last === day - 1 ? streak.n + 1 : 1 };
}
