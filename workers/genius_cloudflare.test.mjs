import test from 'node:test';
import assert from 'node:assert/strict';
import {cloudflareChat,reviewedContext,CLOUDFLARE_MODEL} from './genius_cloudflare.mjs';
const index={pages:[
 {url:'/library/ferrari/ferrari-f40/',title:'Ferrari F40',text:'F40 · original 1987. Ferrari describes turbo power and composite reinforcement.'},
 {url:'/library/lamborghini/lamborghini-miura/',title:'Lamborghini Miura',text:'Miura · 1966. The engine is a transverse V12 behind the cabin.'},
 {url:'/guides/before-a-used-car-viewing/',title:'Before a used-car viewing',text:'Ask the seller for service records and book an independent inspection.'},
 {url:'/library/',title:'Car collection',text:'Ferrari F40 Honda Civic: this is a directory, not reviewed model facts.'}
],catalogue:[
 {n:'Ferrari F40',b:'Ferrari',u:'/library/ferrari/ferrari-f40/'},
 {n:'Lamborghini Miura',b:'Lamborghini',u:'/library/lamborghini/lamborghini-miura/'},
 {n:'Honda Civic',b:'Honda',u:'/library/honda/honda-civic/'}
]};
const req=new Request('https://motorjury.com/api/genius',{method:'POST'});
const ask=question=>({messages:[{role:'user',content:question}]});
async function run(body,{chunks=['data: {"response":"The F40 uses a different engine brief."}\n\n','data: [DONE]\n\n'],quota={ok:true},error=false}={}){
 let invoked=0,prompt,quotaCalls=0;const tasks=[];
 const env={AI:{run:async(model,options)=>{invoked++;assert.equal(model,CLOUDFLARE_MODEL);prompt=options.messages;if(error)throw Error('Unavailable');return new ReadableStream({start(c){chunks.forEach(s=>c.enqueue(new TextEncoder().encode(s)));c.close();}});}}};
 const response=await cloudflareChat(req,new URL(req.url),env,async()=>{quotaCalls++;return quota;},index,body,{waitUntil:p=>tasks.push(p)});
 const output=await response.text();await Promise.all(tasks);
 const events=output.trim().split('\n\n').map(s=>JSON.parse(s.replace(/^data: */,'')));
 return {response,events,invoked,prompt,quotaCalls};
}
test('retrieval separates model identities from reviewed evidence',()=>{
 const r=reviewedContext(index,'Is a 2018 Honda Civic reliable?',null);
 assert.equal(r.cars[0].name,'Honda Civic');assert.equal(r.pages.length,0);
 const supported=reviewedContext(index,'Why are the F40 and Miura different?',null);
 assert.deepEqual(new Set(supported.pages.map(p=>p.title)),new Set(['Ferrari F40','Lamborghini Miura']));
});
test('pinned reviewed page supports follow-up without broad directory facts',()=>{
 assert.equal(reviewedContext(index,'Explain this','/library/ferrari/ferrari-f40/').pages[0].title,'Ferrari F40');
 assert.equal(reviewedContext(index,'Explain this','/library/').pages.length,0);
});
test('streams chunk boundaries, CRLF, final unterminated event and source links',async()=>{
 const r=await run(ask('Explain the F40'),{chunks:['data: {"res','ponse":"First "}\r','\n\r\n','data: {"response":"second."}']});
 assert.equal(r.response.status,200);assert.equal(r.invoked,1);assert.equal(r.events.at(-1).t,'done');
 const text=r.events.filter(e=>e.t==='text').map(e=>e.d).join('');
 assert.match(text,/First second./);assert.match(text,/\[Ferrari F40\]\(\/library\/ferrari\/ferrari-f40\/\)/);
 assert.match(r.prompt[0].content,/Never fill gaps from your own knowledge/);
});
test('unknown topic gives honest coverage fallback without a model request',async()=>{
 const r=await run(ask('Tell me about interstellar navigation'));
 assert.equal(r.invoked,0);assert.equal(r.quotaCalls,0);assert.match(r.events[0].d,/do not have reviewed material/);
});
test('private details blocked before provider and quota',async()=>{
 const r=await run(ask('My VIN is 1HGCM82633A004352. Is this F40 safe?'));
 assert.equal(r.response.status,400);assert.equal(r.invoked,0);assert.equal(r.quotaCalls,0);
});
test('quota and provider failures are explicit',async()=>{
 const limited=await run(ask('Explain the F40'),{quota:{ok:false,error:'Limit reached'}});
 assert.equal(limited.response.status,429);assert.equal(limited.invoked,0);
 const failed=await run(ask('Explain the F40'),{error:true});
 assert.equal(failed.response.status,503);assert.equal(failed.events[0].t,'error');
});
test('empty or failed provider stream never masquerades as a completed answer',async()=>{
 for(const chunks of [[],['data: {"response":"Partial"}\n\n','data: {"error":"failed"}\n\n']]){
  const r=await run(ask('Explain the F40'),{chunks});
  assert.equal(r.events.at(-2).t,'error');assert.equal(r.events.at(-1).t,'done');
 }
});
test('last two user turns provide context for follow-up questions',async()=>{
 const r=await run({messages:[{role:'user',content:'Tell me about the F40'},{role:'assistant',content:'Its design brief is interesting.'},{role:'user',content:'And the engine?'}]});
 assert.equal(r.invoked,1);assert.match(r.prompt[0].content,/Ferrari F40/);
});
test('buying context accepts only the pilot scope and omits other form fields',async()=>{
 const invalid=await run({...ask('Explain the F40'),mode:'buying',buying_context:{year:'2024',powertrain:'hybrid'}});
 assert.equal(invalid.response.status,400);assert.equal(invalid.invoked,0);
 const valid=await run({...ask('Explain the F40'),mode:'buying',buying_context:{year:'2020',powertrain:'hybrid',price:'PRIVATE_VALUE'}});
 assert.match(valid.prompt[0].content,/2020 US Toyota RAV4, powertrain: hybrid/);
 assert.equal(JSON.stringify(valid.prompt).includes('PRIVATE_VALUE'),false);
});
test('unreviewed catalogue identity cannot trigger invented ownership facts',async()=>{
 const r=await run(ask('Is a 2018 Honda Civic reliable?'));
 assert.equal(r.invoked,0);assert.equal(r.quotaCalls,0);
 assert.match(r.events[0].d,/\[Honda Civic\]/);assert.match(r.events[0].d,/do not have a reviewed model story/);
});
test('reviewed aggregate records retain exact year and omit predictive fields',()=>{
 const fixture={...index,cars:[{make:'LEXUS',model:'RX 350',year:2020,url:'/cars/lexus/rx-350/2020/',complaints:80,recalls:3,score:99,verdict:'BUY',scope:'US aggregate records; not VIN applicability'}]};
 const found=reviewedContext(fixture,'What recalls are recorded for a 2020 RX350?',null);
 assert.equal(found.records.length,1);assert.equal(found.records[0].recall_campaigns,3);
 assert.equal('score' in found.records[0],false);assert.equal('verdict' in found.records[0],false);
 assert.equal(reviewedContext(fixture,'What recalls are recorded for a 2024 RX350?',null).records.length,0);
});
test('changing topics does not inherit the previous car as evidence',async()=>{
 const r=await run({messages:[{role:'user',content:'Tell me about the F40'},{role:'assistant',content:'Here is the story.'},{role:'user',content:'Is the 2018 Honda Civic reliable?'}],page:'/library/ferrari/ferrari-f40/'});
 assert.equal(r.invoked,0);assert.match(r.events[0].d,/Honda Civic/);
});
test('an invalid provider response fails quickly instead of leaving chat hanging',async()=>{
 const r=await cloudflareChat(req,new URL(req.url),{AI:{run:async()=>({unexpected:true})}},async()=>({ok:true}),index,ask('Explain the F40'));
 assert.equal(r.status,503);assert.match(await r.text(),/unreadable answer/);
});

test('another Honda page and short catalogue names cannot contaminate Civic retrieval',()=>{
 const fixture={...index,pages:[...index.pages,{url:'/library/honda/honda-nsx/',title:'Honda NSX',text:'Honda NSX first-generation design.'}],catalogue:[...index.catalogue,{n:'Honda NSX',b:'Honda',u:'/library/honda/honda-nsx/'},{n:'Lexus IS',b:'Lexus',u:'/library/lexus/lexus-is/'},{n:'Arrows A20',b:'Arrows',u:'/library/arrows/arrows-a20/'}]};
 const r=reviewedContext(fixture,'Is a 2018 Honda Civic reliable?',null);
 assert.deepEqual(r.cars.map(c=>c.name),['Honda Civic']);assert.equal(r.pages.length,0);
});
test('compact model matching respects word boundaries rather than adjacent words',()=>{
 const fixture={...index,cars:[{make:'Lexus',model:'RX 350',year:2020,url:'/cars/lexus/rx-350/2020/',complaints:53,recalls:1,scope:'US aggregate'}],catalogue:[{n:'Lexus RX',b:'Lexus',u:'/library/lexus/lexus-rx/'},{n:'Cadillac SRX',b:'Cadillac',u:'/library/cadillac/cadillac-srx/'},{n:'Farmall 350',b:'Farmall',u:'/library/farmall/farmall-350/'},{n:'Aston Martin 2020',b:'Aston Martin',u:'/library/aston-martin/2020/'}]};
 const r=reviewedContext(fixture,'What do the 2020 Lexus RX 350 records show?',null);
 assert.deepEqual(r.cars.map(c=>c.name),['Lexus RX']);assert.equal(r.records.length,1);assert.equal(r.pages.length,0);
 assert.equal(reviewedContext(fixture,'Records for a 2020 RX350',null).records.length,1);
 assert.equal(reviewedContext(fixture,'Ask the doctor x350 about records',null).records.length,0);
});
