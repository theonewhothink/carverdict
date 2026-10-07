import BASELINE from './dashboard-data.json' with {type:'json'};
import { HTML, LOGIN, CSS, CLIENT } from './dashboard-ui.mjs';
import { prioritiseTasks } from './dashboard-control.mjs';
import { geniusEnabled } from './genius.mjs';
const COOKIE='__Host-mj_dashboard';
const headers={'Cache-Control':'private, no-store','X-Robots-Tag':'noindex, nofollow, noarchive','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"};
const reply=(body,status=200,extra={})=>new Response(typeof body==='string'?body:JSON.stringify(body),{status,headers:{...headers,'Content-Type':typeof body==='string'?'text/html; charset=utf-8':'application/json; charset=utf-8',...extra}});
const sessionCookie=token=>`${COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800`;
function token(req){const match=(req.headers.get('Cookie')||'').match(/(?:^|;\s*)__Host-mj_dashboard=([a-f0-9]{64})(?:;|$)/);return match?.[1]||'';}
async function call(env,op,payload){const h=env.HUB.get(env.HUB.idFromName('hub'));const r=await h.fetch(new Request('https://hub/'+op,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));const out=await r.json();if(!r.ok)return {error:out.error||'Dashboard storage is unavailable.',status:r.status};return out;}
let healthCache=null;
export async function health(env,origin){
 if(healthCache&&Date.now()-healthCache.time<60000)return healthCache.data;
 const paths=['/','/library/','/cars/','/buying-brief/','/ask/','/guides/','/privacy/','/terms/','/sitemap.xml','/robots.txt','/ads.txt','/favicon.ico'];
 const probes=await Promise.all(paths.map(async path=>{const start=Date.now();try{const r=await env.ASSETS.fetch(new Request(origin+path,{method:'HEAD'}));return {path,status:r.status,ok:r.status===200,ms:Date.now()-start};}catch{return {path,status:null,ok:false,ms:null};}}));
 let ci={status:'unavailable',url:'https://github.com/theonewhothink/carverdict/actions',checked_at:new Date().toISOString()};
 try{const r=await fetch('https://api.github.com/repos/theonewhothink/carverdict/actions/runs?per_page=1&branch=main',{headers:{'User-Agent':'MotorJury-dashboard','Accept':'application/vnd.github+json'},signal:AbortSignal.timeout(5000)});if(r.ok){const d=await r.json(),run=d.workflow_runs?.[0];if(run)ci={status:run.conclusion||run.status,sha:run.head_sha,url:run.html_url,created_at:run.created_at,checked_at:new Date().toISOString()};}}catch{/* Absence is not green. */}
 const data={checked_at:new Date().toISOString(),probes,ci,ai_enabled:geniusEnabled(env),ai_daily_cap:Number(env.GENIUS_DAILY_CAP)||20,providers:{email:true,google:Boolean(env.GOOGLE_CLIENT_ID),apple:Boolean(env.APPLE_CLIENT_ID&&env.APPLE_TEAM_ID&&env.APPLE_KEY_ID&&env.APPLE_PRIVATE_KEY)}};
 healthCache={time:Date.now(),data};return data;
}
export async function handleDashboard(req,url,env){
 const path=url.pathname.replace(/\/$/,'');
 if(!path.startsWith('/api/dashboard')&&!path.startsWith('/dashboard'))return null;
 const api=path.startsWith('/api/dashboard');
 if(!['GET','HEAD','POST'].includes(req.method))return reply({error:'Method not allowed.'},405,{'Allow':'GET, HEAD, POST'});
 const post=req.method==='POST';let body={};
 if(post){
  if(req.headers.get('Origin')!==url.origin)return reply({error:'Forbidden origin.'},403);
  if(!(req.headers.get('Content-Type')||'').includes('application/json'))return reply({error:'Expected JSON.'},415);
  if(Number(req.headers.get('Content-Length')||0)>20000)return reply({error:'Request too large.'},413);
  const raw=await req.text();if(raw.length>20000)return reply({error:'Request too large.'},413);
  try{body=JSON.parse(raw);}catch{return reply({error:'Invalid JSON.'},400);}
 }
 if(path==='/api/dashboard/login'||path==='/api/dashboard/setup'){
  if(!post)return reply({error:'Use POST.'},405);
  const op=path.endsWith('/setup')?'dashboard-setup':'dashboard-login';
  const out=await call(env,op,{password:body.password,token:body.token,ip:req.headers.get('CF-Connecting-IP')||'?'});
  if(out.error)return reply({error:out.error},out.status||400);
  return reply({ok:true},200,out.token?{'Set-Cookie':sessionCookie(out.token)}:{});
 }
 // The generic login shell and its CSS contain no project data and need no session.
 if(path==='/dashboard/style.css')return reply(CSS,200,{'Content-Type':'text/css; charset=utf-8'});
 if(path==='/dashboard/login.js')return reply(CLIENT.login,200,{'Content-Type':'application/javascript; charset=utf-8'});
 const auth=await call(env,'dashboard-session',{token:token(req)});
 if(!auth.ok){if(!api&&(path==='/dashboard'||path==='/dashboard/app.js'))return path==='/dashboard'?reply(LOGIN,200):reply({error:'Please sign in.'},401);return reply({error:auth.error||'Please sign in.'},auth.status||401);}
 if(path==='/dashboard'){if(post)return reply({error:'Use GET.'},405);return reply(HTML);}
 if(path==='/dashboard/app.js')return reply(CLIENT.app,200,{'Content-Type':'application/javascript; charset=utf-8'});
 if(path==='/api/dashboard/logout'){
  if(!post)return reply({error:'Use POST.'},405);await call(env,'dashboard-logout',{token:token(req)});return reply({ok:true},200,{'Set-Cookie':`${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`});
 }
 if(path==='/api/dashboard/data'){
  if(post)return reply({error:'Use GET.'},405);
  const state=await call(env,'dashboard-state',{token:token(req)});if(state.error)return reply({error:state.error},state.status||503);
  const overrides=state.tasks||{};const tasks=BASELINE.tasks.map(t=>({...t,...overrides[t.id]}));for(const [id,t]of Object.entries(overrides))if(!BASELINE.tasks.some(x=>x.id===id))tasks.push({...t,source:'Owner-added task'});
  return reply({...BASELINE,tasks:prioritiseTasks(tasks),metric_values:state.metrics,history:state.history,stats:state.stats,live:await health(env,url.origin),served_at:new Date().toISOString()});
 }
 if(path==='/api/dashboard/tasks'||path==='/api/dashboard/metrics'){
  if(!post)return reply({error:'Use POST.'},405);
  if(!await call(env,'dashboard-session',{token:token(req)}).then(x=>x.ok))return reply({error:'Please sign in.'},401);
  const out=await call(env,path.endsWith('/tasks')?'dashboard-task':'dashboard-metric',{token:token(req),task:body.task,metric:body.metric,metric_ids:BASELINE.metrics.map(m=>m.id)});
  return reply(out.error?{error:out.error}:{ok:true},out.status||200);
 }
 return reply({error:'Not found.'},404);
}
