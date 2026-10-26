// Display models: task completion and source reports never imply traffic or revenue forecasts.
export function reportMeasure(data,id,now=Date.now()){
 const report=data.metric_values?.[id];
 if(!report||report.value===null||report.value===undefined||typeof report.value==='boolean'||String(report.value).trim()===''||!Number.isFinite(Number(report.value)))return null;
 const start=Date.parse(report.start+'T00:00:00Z'),end=Date.parse(report.end+'T00:00:00Z');
 if(!Number.isFinite(start)||!Number.isFinite(end)||start>end||end>now)return null;
 return {...report,value:Number(report.value),days:Math.round((end-start)/86400000)+1,ageDays:Math.floor((now-end)/86400000),stale:now-end>35*86400000};
}
export function growthSnapshot(data,now=Date.now()){
 const active=(data.tasks||[]).filter(t=>t.status!=='retired');
 const complete=t=>t.status==='verified'&&Boolean(t.evidence)&&/^\d{4}-\d{2}-\d{2}$/.test(t.verified_at||'')&&Date.parse(t.verified_at+'T00:00:00Z')<=now;
 const areas=[['Operations & data',[]],['Original editorial',[]],['Search & discovery',[]],['Collection & media',[]],['Experience & mobile',[]],['Grounded AI',[]],['Retention & distribution',[]],['Revenue & billing',[]]];
 for(const t of active){const index=t.area==='Revenue'||/^(ADS|SUB|BILLING|PAY)-/.test(t.id)?7:t.area==='SEO'?2:t.area==='Collection'?3:t.area==='Content'?1:t.area==='AI'?5:t.area==='Experience'?4:['Growth','Product'].includes(t.area)?6:0;areas[index][1].push(t);}
 const verified=active.filter(complete).length;
 const audience=reportMeasure(data,'ga4_users',now),monthly=audience&&audience.days>=28&&audience.days<=31&&audience.value>=0?audience:null;
 const probes=data.live?.probes||[],failures=probes.filter(p=>!p.ok).length;
 const ci=data.live?.ci?.status||'unavailable',releaseFailed=['failure','cancelled','timed_out','action_required'].includes(ci);
 return {target:1000000,total:active.length,verified,percent:active.length?Math.round(verified/active.length*100):null,
  blocked:active.filter(t=>t.status==='blocked').length,inProgress:active.filter(t=>t.status==='in_progress').length,
  pillars:areas.map(([name,tasks])=>({name,total:tasks.length,verified:tasks.filter(complete).length,percent:tasks.length?Math.round(tasks.filter(complete).length/tasks.length*100):null})),
  next:active.filter(t=>!complete(t)).sort((a,b)=>(a.execution?.rank??999)-(b.execution?.rank??999)||a.priority-b.priority||a.id.localeCompare(b.id)),
  audience:monthly,goalPercent:monthly?Math.min(100,monthly.value/1000000*100):null,
  failures,probes:probes.length,releaseFailed,ci,
  state:failures||releaseFailed?'DEGRADED — needs attention':!probes.length||ci!=='success'?'PARTIAL CHECKS — verification pending':!monthly||monthly.ageDays>7?'MEASUREMENT INCOMPLETE — audience baseline needed':'CHECKS PASS — review the growth plan'};
}
