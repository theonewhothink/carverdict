import {test} from 'node:test';
import assert from 'node:assert/strict';
import {servingCI} from './dashboard-ci.mjs';
const sha='a'.repeat(40);
const run=(extra={})=>({name:'build-deploy',head_sha:sha,status:'completed',conclusion:'success',started_at:'2026-11-10T10:00:00Z',html_url:'https://github.com/theonewhothink/carverdict/actions/runs/1',...extra});
test('uses the exact serving commit and ignores a successful ingestion or other source',async()=>{
 let requested;const result=await servingCI(sha,async url=>{requested=url;return Response.json({check_runs:[run({name:'ingest'}),run({head_sha:'b'.repeat(40)})]});});
 assert.ok(requested.includes('/commits/'+sha+'/check-runs'));assert.equal(result.status,'not_run');
});
test('latest attempt for that source wins, including failure and unfinished checks',async()=>{
 for(const [state,wanted]of [[{status:'completed',conclusion:'failure'},'failure'],[{status:'in_progress',conclusion:null},'in_progress']]){
  const result=await servingCI(sha,async()=>Response.json({check_runs:[run(),run({...state,started_at:'2026-11-10T11:00:00Z'})]}));
  assert.equal(result.status,wanted);assert.equal(result.sha,sha);
 }
});
test('unavailable, malformed and unknown-source responses remain unverified',async()=>{
 for(const request of [async()=>new Response('',{status:403}),async()=>Response.json({}),async()=>{throw Error('network');}]){
  const result=await servingCI(sha,request);assert.equal(result.status,'unavailable');assert.ok(result.note);
 }
 let called=false;assert.equal((await servingCI('unknown',async()=>{called=true;})).status,'unavailable');assert.equal(called,false);
});
