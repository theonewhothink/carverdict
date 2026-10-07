// Planning classifications are explicit judgments; they are not completion evidence.
const byId={
 'PLAN-01':[0,'now','Publish the control centre and verify ordered tasks, source labels and business plan in production.'],
 'SEC-01':[0,'now','Audit route headers, session boundaries and dependency changes.'],
 'SEO-02':[1,'now','Review each template and fix measured metadata/schema defects.'],
 'UX-03':[2,'now','Run keyboard, semantic and contrast checks; physical assistive technology remains separate.'],
 'DATA-03':[3,'now','Audit unit/currency labels and suppress outputs with missing evidence.'],
 'IA-01':[4,'now','Compare identity and redirect inventories; preserve all catalogue destinations.'],
 'PHOTO-03':[5,'now','Research licensed replacements and verify delivery and identity.'],
 'PHOTO-04':[6,'now','Audit image delivery and licensing records before changing the CDN.'],
 'CONTENT-03':[7,'now','Research demand-supported article briefs; preserve source/date and uncertainty.'],
 'CONTENT-06':[8,'now','Publish truthful editorial responsibility and correction steps.'],
 'AI-04':[9,'now','Implement feedback and usage instrumentation; provider billing reports still need access.'],
 'AI-03':[10,'now','Broaden sources only after model/version research and regression tests.'],
 'AUTH-02':[11,'now','Test isolated accounts and fix authentication/synchronisation defects.'],
 'OWNER-02':[12,'now','Verify real write/read journeys without inventing owner votes.'],
 'OPS-02':[13,'now','Document rollback, backups, recovery and sampled availability checks.'],
 'SEO-05':[14,'depends','Actual search query and traffic evidence must be connected first.'],
 'I18N-01':[15,'now','Audit existing translations and hreflang; withhold duplicate untranslated pages.'],
 'CONTENT-07':[16,'now','Audit inherited event content and remove unsupported current-news claims.'],
 'MONEY-01':[17,'access','Licensed regional price/insurance/depreciation sources and terms are needed.'],
 'PHOTO-02':[18,'now','Research matched licensed photos in batches; verify identity before publication.'],
 'UX-06':[19,'now','Improve measured design inconsistencies and contrast without losing photography.'],
 'UX-05':[20,'people','Physical-device download and OS-print confirmation cannot be inferred from a browser click.'],
 'UX-02':[21,'people','Safari, Firefox and physical-device evidence still needs the required devices.'],
 'UX-04':[22,'access','Search Console/CrUX field performance or an authorised real-user report is needed.'],
 'SEO-04':[23,'access','Verified Search Console access is required for actual query and index reports.'],
 'CONTENT-04':[24,'people','Ten real buyers must take part; no simulated participants count.'],
 'CONTENT-05':[25,'people','A qualified mechanic must independently review the relevant guide.'],
 'CONTENT-08':[26,'people','Owner voices, external media rights and permissions require real contributors.'],
 'OWNER-01':[27,'people','Survey plumbing can be tested now; genuine owner evidence needs participants.'],
 'AUTH-03':[28,'access','Apple developer credentials and authorised configuration are required.'],
 'EMAIL-01':[29,'access','A delivery provider and an opted-in test journey are required.'],
 'SOCIAL-01':[30,'access','Confirm brand account ownership and analytics access before publication claims.'],
 'LEGAL-01':[31,'access','AdSense consent configuration and live account evidence are required.'],
 'ADS-02':[32,'access','Google approval is an external decision; editorial evidence is prepared first.'],
 'ADS-03':[33,'access','Actual earnings and traffic reports are required.'],
 'ADS-04':[34,'depends','AdSense approval and consent verification must precede an ad experiment.'],
 'ADS-05':[35,'depends','Reader demand and partner terms must precede affiliate/paid rollout.'],
 'GROWTH-01':[36,'depends','Complete the primary buyer journey and measurement before optional features.']
};
const titleRules=[
 ['SEO: complete',0,'now','Complete the build audit, fix findings and validate in production.'],
 ['Editorial: write',1,'now','Draft and source-check useful original articles with a clear reader takeaway.'],
 ['Visual explanations:',2,'now','Build accessible, sourced diagrams on relevant pages; no invented comparisons.'],
 ['Editorial growth:',3,'now','Publish three source-checked guides first, then the remaining nine after review.'],
 ['Originality:',4,'now','Audit editorial provenance; keep required photo credits until lawful replacements exist.'],
 ['AI discovery:',5,'now','Audit robot/public-HTML delivery now; actual crawler logs and citations remain unverified.'],
 ['Directories:',6,'now','Research relevance/eligibility and prepare accurate profiles; submit only where eligible.'],
 ['Subscriptions: validate',7,'people','Prepare the offer test now; demand and willingness to pay need real users.'],
 ['Subscriptions: define',8,'now','Design the tier prototype and test a buying pass separately from recurring membership.'],
 ['Paid chat:',9,'depends','Per-account metering can be prototyped; quotas and activation depend on measured cost/value.'],
 ['Subscriptions: implement',10,'depends','Merchant identity, countries, offer validation and billing account must be decided first.'],
 ['Subscription launch:',11,'depends','Validated value, payment QA, support and margin evidence precede charging.'],
 ['Search engines:',12,'access','Use verified official properties; the currently inactive connector does not establish console access.'],
 ['Daily indexing:',13,'access','Actual Search Console access and quota are required; inspection is not an indexing request.'],
 ['Social: register',14,'people','Adir completes final account verification and terms acceptance. Preparation can proceed now.'],
 ['Social operations:',15,'depends','Prepare a calendar now; publishing and moderation require launched authorised accounts.']
];
export const executionLabels={now:'Execute now',access:'Account or data access',people:'Human participation',depends:'Prerequisite first',assessment:'Assess next',done:'Verified / retired'};
export function executionFor(t){
 if(['verified','retired'].includes(t.status))return {mode:'done',phase:'F · Keep evidence current',weight:10000,reason:'Existing completion status is preserved; no new completion is inferred.'};
 let entry=byId[t.id];if(!entry){const r=titleRules.find(r=>t.title.startsWith(r[0]));if(r)entry=r.slice(1);}
 if(!entry)entry=[90,t.status==='blocked'?'access':'assessment','Review this task and its acceptance checks before assigning execution.'];
 const [order,mode,reason]=entry;
 const phase=mode==='now'?(order<7?'A · Protect, publish and explain':'B · Improve the core journey'):mode==='access'?'C · Connect real sources':mode==='people'?'D · Validate with people':mode==='depends'?'E · Expand and monetise':'B · Assess scope';
 return {mode,phase,weight:({now:0,assessment:1000,access:2000,people:3000,depends:4000}[mode]??1000)+order*10+Number(t.priority||0),reason};
}
export function prioritiseTasks(tasks){return tasks.map(t=>({...t,execution:executionFor(t)})).sort((a,b)=>a.execution.weight-b.execution.weight||a.priority-b.priority||a.id.localeCompare(b.id)).map((t,i)=>({...t,execution:{...t.execution,rank:i+1,label:executionLabels[t.execution.mode]}}));}
