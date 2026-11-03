import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {compiledDashboard} from '../scripts/dashboard_browser_bundle.mjs';
import {MODEL_CLIENT} from './dashboard-client-models.mjs';
import {reportMeasure,growthSnapshot} from './dashboard-growth.mjs';
import {GROWTH_CLIENT} from './dashboard-views.mjs';
const now=Date.parse('2026-11-03T12:00:00Z');
const fixture={tasks:[{id:'A',area:'Content',status:'verified',evidence:'Test fixture',verified_at:'2026-11-01'},{id:'B',area:'SEO',status:'open'}],live:{probes:[{ok:true}],ci:{status:'success'}},metric_values:{ga4_users:{value:333,start:'2026-10-01',end:'2026-10-30'}}};
test('generated browser models stay in sync with their canonical shared functions',()=>{
 assert.equal(MODEL_CLIENT,[reportMeasure,growthSnapshot].map(fn=>fn.toString()).join('\n'));
});
for(const minify of [false,true]) test('compiled dashboard executes growth models without Worker helper globals; minify='+minify,async()=>{
 const {CLIENT}=await compiledDashboard({minify});
 const boundary=CLIENT.app.indexOf(GROWTH_CLIENT);
 assert.ok(boundary>0,'Shared models must precede the real view code');
 const prefix=CLIENT.app.slice(0,boundary);
 const result=vm.runInNewContext(prefix+'\ngrowthSnapshot(data,now)',{data:fixture,now});
 assert.equal(result.verified,1);assert.equal(result.total,2);assert.equal(result.percent,50);
 assert.equal(result.audience.value,333);assert.equal(result.pillars.length,8);
 assert.equal(result.state,'CHECKS PASS — review the growth plan');
 assert.doesNotThrow(()=>new vm.Script(CLIENT.app));
});
