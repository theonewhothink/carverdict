import {number,fuelCost,ownership} from './buying-budget.mjs';
export function fuelPayback(input){
 const a=fuelCost(input.miles,input.a,input.fuel),b=fuelCost(input.miles,input.b,input.fuel),premium=number(input.premium,-2000000,2000000);
 if(a===null||b===null||premium===null)return {kind:'incomplete'};
 const saving=a-b;
 return {a,b,saving,premium,years:premium>0&&saving>0?premium/saving:null,kind:premium<=0?'no_premium':saving<=0?'no_payback':'payback'};
}
export function costBreakdown(input){
 const result=ownership({price:input.price,resale:input.resale,insurance:input.insurance,maintenance:input.maintenance,reserve:input.reserve,mpg:input.mpg},{miles:input.miles,fuel:input.fuel,years:input.years});
 if(result.total===null)return {...result,components:[]};
 const years=Number(input.years);
 return {...result,components:[['Purchase less resale',Number(input.price)-Number(input.resale)],['Fuel',result.annualFuel*years],['Insurance',Number(input.insurance)*years],['Maintenance and recurring fees',Number(input.maintenance)*years],['Assumed repair spending',Number(input.reserve)*years]]};
}
if(typeof document!=='undefined')for(const root of document.querySelectorAll('[data-guide-calculator]')){
 const form=root.querySelector('form'),output=root.querySelector('[data-guide-result]');
 const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n);
 function paragraph(text){const p=document.createElement('p');p.textContent=text;output.append(p);}
 function chart(rows,caption){
  const table=document.createElement('table'),cap=document.createElement('caption');cap.textContent=caption;table.append(cap);
  const head=document.createElement('tr');for(const text of ['Component','USD across stated period','Relative amount']){const th=document.createElement('th');th.scope='col';th.textContent=text;head.append(th);}const thead=document.createElement('thead');thead.append(head);table.append(thead);
  const tbody=document.createElement('tbody'),maximum=Math.max(1,...rows.map(r=>r[1])),bars=rows.every(r=>r[1]>=0);
  for(const [label,value]of rows){const tr=document.createElement('tr'),name=document.createElement('th'),amount=document.createElement('td'),bar=document.createElement('td');name.scope='row';name.textContent=label;amount.textContent=money(value);
   if(bars){const meter=document.createElement('meter');meter.min=0;meter.max=maximum;meter.value=value;meter.setAttribute('aria-label',label+': '+money(value));bar.append(meter);}else bar.textContent='See signed amount';
   tr.append(name,amount,bar);tbody.append(tr);
  }table.append(tbody);const wrap=document.createElement('div');wrap.className='table-wrap';wrap.append(table);output.append(wrap);
 }
 form.addEventListener('submit',event=>{
  event.preventDefault();output.replaceChildren();const input=Object.fromEntries(new FormData(form));
  if(root.dataset.guideCalculator==='cost'){
   const result=costBreakdown(input);
   if(result.total===null){paragraph('Complete every input. Missing or invalid assumptions remain unknown.');return;}
   paragraph(money(result.total)+' modeled cash cost across '+input.years+' years; '+money(result.total/(Number(input.years)*12))+' per month when divided evenly.');
   chart(result.components,'Your entered scenario, across the holding period. Bars share the largest-component scale.');
   paragraph('Future resale and repair spending are assumptions. A reserve is counted only as assumed spending. Financing and any costs you have not included remain outside this model.');
  }else{
   const result=fuelPayback(input);if(result.kind==='incomplete'){paragraph('Complete every input using miles, US MPG and dollars per US gallon.');return;}
   chart([['Candidate A annual fuel',result.a],['Candidate B annual fuel',result.b]],'Your annual fuel scenarios in USD. Bars share the largest-component scale.');
   paragraph('Candidate B annual fuel saving: '+money(result.saving)+'.');
   paragraph(result.kind==='no_premium'?'There is no positive upfront premium to recover. This does not establish the lower total ownership cost.':result.kind==='no_payback'?'There is no fuel-only payback for a positive premium under these inputs.':'Fuel-only premium recovery: about '+result.years.toFixed(2)+' years. Other ownership costs and changing assumptions can alter the decision.');
  }
 });
}
