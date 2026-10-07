import { SETUP_DIGEST } from './dashboard-config.mjs';
const enc=new TextEncoder();
const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
const random=()=>hex(crypto.getRandomValues(new Uint8Array(32)));
export const digest=async s=>hex(await crypto.subtle.digest('SHA-256',enc.encode(s)));
export function equal(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);return d===0;}
export async function passwordHash(password,salt){const key=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveBits']);return hex(await crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:enc.encode(salt),iterations:100000},key,256));}
const validDate=s=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(s||''))return false;try{return new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;}catch{return false;}};
export function validateTask(input){
 const statuses=['open','in_progress','blocked','verified','needs_review','retired'];
 if(!input||!/^[-A-Z0-9]{2,48}$/.test(input.id||''))throw Error('Invalid task ID.');
 if(!statuses.includes(input.status))throw Error('Choose a valid status.');
 const out={id:input.id,status:input.status,priority:Number(input.priority),title:String(input.title||'').trim().slice(0,180),area:String(input.area||'Operations').slice(0,40),owner:String(input.owner||'MotorJury team').trim().slice(0,80),next_action:String(input.next_action||'').trim().slice(0,2000),acceptance:String(input.acceptance||'').trim().slice(0,2000),evidence:String(input.evidence||'').trim().slice(0,2000),verified_at:String(input.verified_at||''),updated_at:new Date().toISOString()};
 if(!out.title||!out.acceptance||![0,1,2,3].includes(out.priority))throw Error('Add a title, acceptance check and priority.');
 if(out.status==='verified'&&(!out.evidence||!validDate(out.verified_at)||out.verified_at>new Date().toISOString().slice(0,10)))throw Error('A verified task needs dated evidence.');
 if(out.status!=='verified')out.verified_at='';
 return out;
}
export function validateMetric(input,ids){
 if(!input||!ids.includes(input.id))throw Error('Unknown metric.');
 const value=Number(input.value);
 if(input.value===''||input.value==null||!Number.isFinite(value)||Math.abs(value)>1e12)throw Error('Enter a finite measured value.');
 if(!['net_contribution','subscription_contribution'].includes(input.id)&&value<0)throw Error('This metric cannot be negative.');
 if(['return_rate','task_rate','ai_usefulness','invalid_traffic','subscription_churn','paid_conversion'].includes(input.id)&&value>100)throw Error('A percentage must be between 0 and 100.');
 if(!validDate(input.start)||!validDate(input.end)||input.start>input.end||input.end>new Date().toISOString().slice(0,10))throw Error('Use a valid completed reporting period.');
 const source=String(input.source||'').trim().slice(0,500),notes=String(input.notes||'').trim().slice(0,1500);
 if(!source)throw Error('Name the source report and scope.');
 return {id:input.id,value,start:input.start,end:input.end,source,notes,provenance:'Owner-entered report; not an automatic provider connection',recorded_at:new Date().toISOString()};
}
export async function dashboardDispatch(h,op,b,setupDigest=SETUP_DIGEST){
 const get=k=>{const row=h.one('SELECT v FROM dashboard_config WHERE k=?',k);return row?JSON.parse(row.v):null;};
 const put=(k,v)=>h.sql.exec('INSERT INTO dashboard_config(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',k,JSON.stringify(v));
 const now=Date.now();
 if(op==='dashboard-setup'){
  if(get('credentials'))return {error:'Dashboard already configured.',status:409};
  if(!b.token||!equal(await digest(String(b.token)),setupDigest))return {error:'Forbidden.',status:403};
  if(typeof b.password!=='string'||b.password.length<8||b.password.length>128)return {error:'Invalid password length.',status:400};
  const salt=random(),hash=await passwordHash(b.password,salt);
  // Recheck after asynchronous hashing: concurrent provisioning cannot replace credentials.
  if(get('credentials'))return {error:'Dashboard already configured.',status:409};
  put('credentials',{salt,hash,created_at:now});return {ok:true};
 }
 if(op==='dashboard-login'){
  const ip=await digest(String(b.ip||'?'));
  if(!h.limit('dash:login:'+ip,5,900)||!h.limit('dash:login:all',50,900))return {error:'Too many attempts. Try again in 15 minutes.',status:429};
  const c=get('credentials');
  if(!c)return {error:'Dashboard configuration is being completed.',status:503};
  if(typeof b.password!=='string'||b.password.length>128||!equal(await passwordHash(b.password,c.salt),c.hash))return {error:'Incorrect password.',status:401};
  h.sql.exec('DELETE FROM dashboard_sessions WHERE expires<?',now);
  const token=random();h.sql.exec('INSERT INTO dashboard_sessions(hash,expires) VALUES(?,?)',await digest(token),now+8*3600000);return {token};
 }
 if(!/^[a-f0-9]{64}$/.test(b.token||''))return {error:'Please sign in.',status:401};
 const tokenHash=await digest(b.token),session=h.one('SELECT expires FROM dashboard_sessions WHERE hash=?',tokenHash);
 if(!session||session.expires<=now)return {error:'Please sign in.',status:401};
 if(op==='dashboard-session')return {ok:true};
 if(op==='dashboard-logout'){h.sql.exec('DELETE FROM dashboard_sessions WHERE hash=?',tokenHash);return {ok:true};}
 if(op==='dashboard-state'){
  const period=Math.floor(now/1000/86400),counter=h.one('SELECT n,window FROM rate WHERE k=?','genius:all');
  return {tasks:get('tasks')||{},metrics:get('metrics')||{},history:get('history')||[],stats:{users:h.one('SELECT COUNT(*) n FROM users').n,likes:h.one('SELECT COUNT(*) n FROM likes').n,surveys:h.one('SELECT COUNT(*) n FROM survey').n,subscribers:h.one('SELECT COUNT(*) n FROM subscribers').n,ai_quota_used_today:counter?.window===period?counter.n:0}};
 }
 let change;
 if(op==='dashboard-task'){
  const t=validateTask(b.task),tasks=get('tasks')||{};change={kind:'task',id:t.id,before:tasks[t.id]||null,after:t,at:new Date(now).toISOString()};tasks[t.id]=t;put('tasks',tasks);
 }else if(op==='dashboard-metric'){
  const m=validateMetric(b.metric,b.metric_ids||[]),metrics=get('metrics')||{};change={kind:'metric',id:m.id,before:metrics[m.id]||null,after:m,at:new Date(now).toISOString()};metrics[m.id]=m;put('metrics',metrics);
 }else return {error:'Unknown dashboard operation.',status:404};
 const history=get('history')||[];history.unshift(change);put('history',history.slice(0,200));return {ok:true};
}
