import {test} from 'node:test';import assert from 'node:assert/strict';
import {fuelPayback,costBreakdown} from './buying-explainers.mjs';
const fuel={miles:'12000',a:'30',b:'40',fuel:'3.5',premium:'2000'};
test('fuel-only payback uses consistent annual units and preserves the premium boundary',()=>{
 const r=fuelPayback(fuel);assert.equal(r.a,1400);assert.equal(r.b,1050);assert.equal(r.saving,350);assert.equal(r.years,2000/350);
 assert.equal(fuelPayback({...fuel,premium:'0'}).kind,'no_premium');
 assert.equal(fuelPayback({...fuel,premium:'-1000'}).kind,'no_premium');
 for(const extra of [{b:'30'},{b:'20'},{miles:'0'}])assert.equal(fuelPayback({...fuel,...extra}).kind,'no_payback');
 for(const extra of [{fuel:''},{a:'0'},{miles:'-1'},{premium:'oops'}])assert.equal(fuelPayback({...fuel,...extra}).kind,'incomplete');
});
const cash={price:'25000',resale:'10000',insurance:'1000',maintenance:'700',reserve:'500',mpg:'30',miles:'12000',fuel:'3.5',years:'5'};
test('cash breakdown reconciles exactly and does not convert missing inputs to zero',()=>{
 const r=costBreakdown(cash);assert.equal(r.total,33000);assert.equal(r.components.reduce((sum,x)=>sum+x[1],0),33000);
 assert.equal(costBreakdown({...cash,resale:''}).total,null);
 assert.equal(costBreakdown({...cash,years:'0'}).total,null);
 assert.equal(costBreakdown({...cash,resale:'30000'}).components[0][1],-5000);
 assert.equal(costBreakdown({...cash,price:'0',resale:'0',miles:'0',insurance:'0',maintenance:'0',reserve:'0'}).total,0);
});
