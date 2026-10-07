import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {HubDO} from './hub.js';
import {accountWriteAllowed,boundedJson,localLink,preferences,ownerAnswer,PUBLIC_METHODS} from './public-controls.mjs';
function hub(){const db=new DatabaseSync(':memory:');return new HubDO({storage:{sql:{exec(q,...args){const s=db.prepare(q);const r=s.columns().length?s.all(...args):(s.run(...args),[]);return {toArray:()=>r};}}}});}
const answer={overall:4,reliability:3,running_cost:2,years_owned:0,would_buy_again:false,owned:true};
test('account writes reject missing, sibling and foreign origins',()=>{
 for(const origin of [null,'https://evil.example','https://www.motorjury.com']) assert.equal(accountWriteAllowed(new Request('https://motorjury.com/api/prefs',{method:'POST',headers:origin?{Origin:origin}:{}}),'https://motorjury.com'),false);
 assert.equal(accountWriteAllowed(new Request('https://motorjury.com/api/prefs',{method:'POST',headers:{Origin:'https://motorjury.com'}}),'https://motorjury.com'),true);
 assert.deepEqual(PUBLIC_METHODS['/api/auth/logout'],['POST']);
 assert.deepEqual(PUBLIC_METHODS['/api/auth/apple/callback'],['GET','POST']);
});
test('JSON is bounded even without Content-Length and must be an object',async()=>{
 for(const body of ['{','null','[]','"hello"']) await assert.rejects(boundedJson(new Request('https://motorjury.com',{method:'POST',body})));
 const r=new Request('https://motorjury.com',{method:'POST',body:JSON.stringify({name:'🙂'.repeat(100)})});await assert.rejects(boundedJson(r,100),e=>e.status===413);
 assert.deepEqual(await boundedJson(new Request('https://motorjury.com',{method:'POST',body:'{}'})),{});
});
test('saved links cannot execute code or navigate off site',()=>{
 for(const value of ['javascript:alert(1)','//evil.example','/\\evil.example','/\nevil',null,'https://evil.example']) assert.equal(localLink(value),'/');
 assert.equal(localLink('/cars/toyota/rav4/2019/?tab=photos#view'),'/cars/toyota/rav4/2019/?tab=photos#view');
});
test('preferences reject oversized, non-object and nested prototype payloads',()=>{
 for(const v of [[],null,'text',{x:'x'.repeat(100001)},JSON.parse('{"garage":{"__proto__":{}}}')]) assert.throws(()=>preferences(v));
 assert.deepEqual(preferences({garage:[{u:'/cars/toyota/rav4/'}]}),{garage:[{u:'/cars/toyota/rav4/'}]});
});
test('missing, fractional and non-finite owner answers never turn into ratings',()=>{
 for(const key of ['overall','reliability','running_cost','years_owned']) {
  for(const value of [undefined,'',null,true,NaN,Infinity,-1,1.5]) assert.throws(()=>ownerAnswer({...answer,[key]:value}));
 }
 assert.throws(()=>ownerAnswer({...answer,owned:false}));
 for(const v of [undefined,'false',0]) assert.throws(()=>ownerAnswer({...answer,would_buy_again:v}));
 assert.deepEqual(ownerAnswer(answer),{overall:4,reliability:3,running_cost:2,years_owned:0,would_buy_again:0});
 assert.equal(ownerAnswer({...answer,overall:'5'}).overall,5);
});
test('real account store preserves separate answers, syncs prefs, toggles love and revokes sessions',async()=>{
 const h=hub();const {token,user}=await h.dispatch('signup',{email:'test@example.invalid',password:'isolated-test-only',ip:'127.0.0.1'},{});
 assert.ok(user.id);assert.equal((await h.dispatch('me',{token},{})).user.id,user.id);
 await h.dispatch('prefs',{token,prefs:{garage:[{u:'/cars/toyota/rav4/2019/',t:'RAV4'}]}},{});
 assert.equal((await h.dispatch('me',{token},{})).user.prefs.garage.length,1);
 const item='toyota/rav4/2019';
 await assert.rejects(h.dispatch('survey',{token,item,overall:5},{}));
 assert.equal(h.one('SELECT COUNT(*) n FROM survey').n,0);
 await h.dispatch('survey',{token,item,...answer},{});
 const saved=await h.dispatch('survey-read',{}, {token,item});
 assert.equal(saved.mine.reliability,3);assert.equal(saved.mine.running_cost,2);assert.equal(saved.mine.would_buy_again,0);assert.equal(saved.rollup.n,1);
 await h.dispatch('survey',{token,item,...answer,overall:2},{});assert.equal(h.one('SELECT COUNT(*) n FROM survey').n,1);
 assert.equal((await h.dispatch('love',{token,item,name:'RAV4',url:'javascript:alert(1)'},{})).loved,true);
 assert.equal((await h.dispatch('most-loved',{},{})).items[0].url,'/');
 assert.equal((await h.dispatch('love',{token,item},{})).loved,false);
 await h.dispatch('logout',{token},{});assert.equal((await h.dispatch('me',{token},{})).user,null);
});
test('different reader sessions cannot read or write another account workspace',async()=>{
 const h=hub();
 const a=await h.dispatch('signup',{email:'one@example.invalid',password:'isolated-test-only',ip:'one'},{});
 const b=await h.dispatch('signup',{email:'two@example.invalid',password:'isolated-test-only',ip:'two'},{});
 await h.dispatch('prefs',{token:a.token,prefs:{garage:[{u:'/cars/toyota/rav4/2019/',t:'Private shortlist'}]}},{});
 assert.equal((await h.dispatch('me',{token:b.token},{})).user.prefs.garage,undefined);
 await assert.rejects(h.dispatch('prefs',{token:'invented-session',prefs:{garage:[]}},{}));
 assert.equal((await h.dispatch('me',{token:a.token},{})).user.prefs.garage.length,1);
 h.sql.exec('UPDATE sessions SET expires=0');
 assert.equal((await h.dispatch('me',{token:a.token},{})).user,null);
});
test('actual login store bounds attempts across different email addresses on one IP',async()=>{
 const h=hub();
 for(let i=0;i<40;i++) await assert.rejects(h.dispatch('login',{email:'missing'+i+'@example.invalid',password:'wrong',ip:'test-ip'},{}),/Email or password/);
 await assert.rejects(h.dispatch('login',{email:'next@example.invalid',password:'wrong',ip:'test-ip'},{}),/Too many attempts/);
 h.sql.exec('UPDATE rate SET window=-1');
 await assert.rejects(h.dispatch('login',{email:'next@example.invalid',password:'wrong',ip:'test-ip'},{}),/Email or password/);
});
test('legacy answers remain editable but cannot appear in attested aggregates',async()=>{
 const h=hub();const {token,user}=await h.dispatch('signup',{email:'legacy@example.invalid',password:'isolated-test-only',ip:'legacy'},{});
 h.sql.exec("INSERT INTO survey(user_id,item,overall,reliability,running_cost,would_buy_again,years_owned,comment,created) VALUES(?,?,?,?,?,?,?,?,?)",user.id,'legacy-car',5,5,5,1,0,'Unconfirmed legacy comment',Date.now());
 const before=await h.dispatch('survey-read',{}, {token,item:'legacy-car'});
 assert.equal(before.rollup.n,0);assert.equal(before.mine.overall,5);assert.deepEqual(before.comments,[]);
 await h.dispatch('survey',{token,item:'legacy-car',...answer},{});
 assert.equal((await h.dispatch('survey-read',{}, {token,item:'legacy-car'})).rollup.n,1);
 const count=h.one('SELECT COUNT(*) n FROM survey_rollup').n;
 await h.dispatch('survey-read',{}, {item:'invented-public-query'});
 assert.equal(h.one('SELECT COUNT(*) n FROM survey_rollup').n,count);
});
