import test from 'node:test';import assert from 'node:assert/strict';import http from 'node:http';
import {handleGenius} from './genius.mjs';
const assets={fetch:async request=>new Response(request.url.endsWith('.json')?'[]':'<html lang="en"><title>Reviewed RAV4 brief</title><main><p>Campaign 20V-064 requires dealer VIN applicability and remedy verification.</p></main></html>',{headers:{'Content-Type':request.url.endsWith('.json')?'application/json':'text/html'}})};
const request=(messages,extra={})=>new Request('http://localhost/api/genius',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'buying',buying_context:{year:'2020',powertrain:'hybrid',price:'DO NOT TRANSMIT'},messages,...extra})});
test('AI disabled, private questions and quota limits fail without a model call',async()=>{
 const url=new URL('http://localhost/api/genius');let quotaCalls=0;const quota=async()=>{quotaCalls++;return {ok:false,error:'Daily limit reached'};};
 const disabled=await handleGenius(request([{role:'user',content:'What should I ask?'}]),url,{ASSETS:assets},quota);
 assert.equal(disabled.status,503);assert.equal(quotaCalls,0);
 const privateInput=await handleGenius(request([{role:'user',content:'VIN 1HGCM82633A004352'}]),url,{ANTHROPIC_API_KEY:'test-fixture-only',ASSETS:assets},quota);
 assert.equal(privateInput.status,400);assert.equal(quotaCalls,0);
 const missing=await handleGenius(request([{role:'user',content:'What should I ask?'}]),url,{ANTHROPIC_API_KEY:'test-fixture-only',ASSETS:{fetch:async()=>new Response('',{status:404})}},quota);
 assert.equal(missing.status,404);assert.equal(quotaCalls,0);
 const capped=await handleGenius(request([{role:'user',content:'What should I ask?'}]),url,{ANTHROPIC_API_KEY:'test-fixture-only',ASSETS:assets},quota);
 assert.equal(capped.status,429);assert.match(await capped.text(),/Daily limit/);
});
test('actual SDK streaming transport receives bounded, grounded context without private form fields',async()=>{
 let observed;const server=http.createServer(async(req,res)=>{let body='';for await(const part of req)body+=part;observed=JSON.parse(body);res.writeHead(200,{'Content-Type':'text/event-stream'});
 const events=[{type:'message_start',message:{id:'msg_fixture',type:'message',role:'assistant',content:[],model:'claude-sonnet-5',stop_reason:null,stop_sequence:null,usage:{input_tokens:20,output_tokens:0}}},{type:'content_block_start',index:0,content_block:{type:'text',text:''}},{type:'content_block_delta',index:0,delta:{type:'text_delta',text:'Transport test fixture: verify applicability and remedy completion by VIN.'}},{type:'content_block_stop',index:0},{type:'message_delta',delta:{stop_reason:'end_turn',stop_sequence:null},usage:{output_tokens:15}},{type:'message_stop'}];
 for(const e of events)res.write(`event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`);res.end();});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const response=await handleGenius(request([{role:'user',content:'What should I ask?'}]),new URL('http://localhost/api/genius'),{ASSETS:assets,ANTHROPIC_API_KEY:'test-fixture-only',ANTHROPIC_BASE_URL:`http://127.0.0.1:${server.address().port}`},async()=>({ok:true}));
 const answer=await response.text();assert.match(answer,/Transport test fixture/);assert.match(answer,/"t":"done"/);assert.equal(observed.max_tokens,2048);assert.match(observed.system,/reviewed 2019–2020 US RAV4/);assert.match(observed.system,/Year: 2020/);assert.equal(JSON.stringify(observed).includes('DO NOT TRANSMIT'),false);assert.equal(observed.model,'claude-sonnet-5');
 }finally{await new Promise(resolve=>server.close(resolve));}
});
