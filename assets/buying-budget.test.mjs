import { test } from 'node:test';
import assert from 'node:assert/strict';
import { number, fuelCost, ownership, compare } from './buying-budget.mjs';
test('missing inputs cannot produce a free repair or a cost winner', () => {
  assert.equal(number(''),null); assert.equal(number(null),null);
  assert.equal(number('NaN'),null); assert.equal(number(-1),null);
  assert.equal(fuelCost(12000,0,3.5),null);
  const r=compare({mpg:30},{mpg:40},{miles:12000,fuel:3.5,years:5});
  assert.equal(r.left.annualFuel,1400); assert.equal(r.right.annualFuel,1050);
  assert.equal(r.difference,null); assert.ok(r.left.missing.includes('reserve'));
});
test('purchase, resale and recurring costs are counted once', () => {
  const a={price:20000,mpg:30,insurance:1200,maintenance:600,reserve:500,resale:10000};
  const b={...a,price:23000,mpg:40,resale:12000};
  const r=compare(a,b,{miles:12000,fuel:3.5,years:5});
  assert.equal(r.left.total,28500); assert.equal(r.right.total,27750);
  assert.equal(r.difference,-750);
  assert.equal(ownership({...a,reserve:0},{miles:0,fuel:3.5,years:1}).annualFuel,0);
});
