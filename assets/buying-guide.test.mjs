import test from 'node:test';import assert from 'node:assert/strict';
import {guidance,interpret,questionPayload,safeLink} from './buying-guide-core.mjs';
test('unknown year, incompatible variants and multiple candidates do not get a guessed brief',()=>{
 assert.deepEqual(guidance('RAV4 Hybrid').actions,['year']);
 for(const q of ['2020 RAV4 Prime','2021 RAV4','RAV4 versus Honda CR-V','2020 RAV4 in Canada']) assert.equal(guidance(q).next.unsupported,true,q);
 assert.equal(interpret('2019 or 2020 RAV4').ambiguous,true);
 assert.equal(interpret('2020 RAV4 not hybrid').powertrain,'unknown');
 assert.match(guidance('write a birthday poem',{year:'2020'}).title,/Choose what/);
});
test('local safety guidance preserves VIN scope and powertrain distinctions',()=>{
 assert.match(guidance('Is my 2020 RAV4 safe?').text,/applicability and remedy completion/);
 const gas=guidance('What about refuelling?',{year:'2020',powertrain:'gasoline'});
 assert.match(gas.text,/not a blanket gasoline/);
 assert.ok(!gas.links.some(x=>x[1].includes('10190478')));
});
test('AI payload excludes budget and checklist and rejects private question patterns',()=>{
 const body=questionPayload('What should I ask?',{year:'2020',powertrain:'hybrid',price:'23000',vin:'PRIVATE',checks:[true]});
 assert.equal(JSON.stringify(body).includes('23000'),false);assert.equal(JSON.stringify(body).includes('PRIVATE'),false);
 for(const q of ['My VIN is 1HGCM82633A004352','email me at owner@example.com','My insurance is $2000','Call 212-555-1234']) assert.throws(()=>questionPayload(q,{}));
});
test('AI links cannot execute code or send readers to invented external sources',()=>{
 assert.equal(safeLink('javascript:alert(1)','https://motorjury.com'),null);
 assert.equal(safeLink('https://evil.test/story','https://motorjury.com'),null);
 assert.ok(safeLink('/buying-brief/','https://motorjury.com'));
 assert.ok(safeLink('https://www.nhtsa.gov/recalls','https://motorjury.com'));
});
