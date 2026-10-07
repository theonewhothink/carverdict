// Pure scenario arithmetic. It never reads business reports or creates a payment.
export function financialScenario(raw) {
 const keys=['free_users','paid_users','price','free_answers','paid_answers','answer_cost','support_cost','other_cost','fee_percent','fee_fixed','ad_views','rpm'];
 const input={};
 for(const k of keys){const v=raw[k];if(v===null||v===undefined||String(v).trim()==='')return {ok:false,error:'Complete every assumption. Enter 0 when you intentionally assume none.'};input[k]=Number(v);if(!Number.isFinite(input[k])||input[k]<0||input[k]>1e9)return {ok:false,error:'Use finite, non-negative assumptions.'};}
 if(input.fee_percent>100)return {ok:false,error:'Payment fee percentage must be between 0 and 100.'};
 const subscriptions=input.paid_users*input.price,advertising=input.ad_views/1000*input.rpm;
 const freeAI=input.free_users*input.free_answers*input.answer_cost,paidAI=input.paid_users*input.paid_answers*input.answer_cost;
 const fees=subscriptions*input.fee_percent/100+input.paid_users*input.fee_fixed,support=input.paid_users*input.support_cost;
 const totalRevenue=subscriptions+advertising,totalCosts=freeAI+paidAI+fees+support+input.other_cost,contribution=totalRevenue-totalCosts;
 const paidUnitMargin=input.price*(1-input.fee_percent/100)-input.fee_fixed-input.paid_answers*input.answer_cost-input.support_cost;
 const uncoveredFixed=Math.max(0,freeAI+input.other_cost-advertising);
 const breakEven=paidUnitMargin>0?Math.ceil(uncoveredFixed/paidUnitMargin):null;
 return {ok:true,input,subscriptions,advertising,freeAI,paidAI,fees,support,totalRevenue,totalCosts,contribution,paidUnitMargin,breakEven};
}
