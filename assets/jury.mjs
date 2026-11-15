// The car jury: pick one of two, fill ten bays, share the garage, see the world's verdict.
// Picks are anonymous. The garage lives in this browser; only verdict pairs reach the server.
import {BAYS,DAILY_PICKS,agreement,cleanGarage,dailyPairs,dayNumber,drawPair,garageLink,park,parseGarage,shareText,swap,taste} from './jury-core.mjs';

const KEY='motorjury.jury.v1';
const COUNTRIES=[['','World'],['US','United States'],['GB','United Kingdom'],['DE','Germany'],['FR','France'],['IT','Italy'],['ES','Spain'],['PT','Portugal'],['NL','Netherlands'],['PL','Poland'],['SE','Sweden'],['IL','Israel'],['TR','Turkey'],['AE','United Arab Emirates'],['IN','India'],['JP','Japan'],['AU','Australia'],['CA','Canada'],['MX','Mexico'],['BR','Brazil']];
const $=(sel,root=document)=>root.querySelector(sel);
function node(tag,text,cls){const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;}
const tracked=new Set();
function track(task){if(!window.mjAnalyticsAllowed||typeof window.gtag!=='function'||tracked.has(task))return;tracked.add(task);window.gtag('event','jury_task_complete',{task_type:task});}

const arena=$('[data-jury]'),rankingHost=$('[data-jury-ranking]');
if(arena||rankingHost){
fetch('/assets/jury-data.json?v=__JURY_VERSION__').then(r=>{if(!r.ok)throw Error();return r.json();}).then(start).catch(()=>{const s=$('[data-jury-progress]')||$('[data-jury-ranking-status]');if(s)s.textContent='The jury could not load. Reload the page to try again.';});
}

function start(cars){
const byId=new Map(cars.map(c=>[c.id,c])),ids=cars.map(c=>c.id),idSet=new Set(ids);
const filePage=c=>'https://commons.wikimedia.org/wiki/File:'+encodeURIComponent(c.p.replace(/ /g,'_'));
function photo(c,eager){const frame=node('span','','jury-photo'),img=node('img');img.src=c.t;img.srcset=c.t.replace('/960px-','/330px-')+' 330w, '+c.t+' 960w';img.sizes='(max-width:700px) 92vw, 600px';img.alt=c.n+' · reference photograph';img.width=960;img.height=600;img.decoding='async';img.referrerPolicy='no-referrer';if(eager)img.fetchPriority='high';else img.loading='lazy';img.addEventListener('error',()=>{frame.classList.add('photo-missing');frame.replaceChildren(node('span','Photo unavailable'));},{once:true});frame.append(img);return frame;}
function credit(c){const span=node('span');span.setAttribute('data-photo-attribution','');const file=node('a',c.n+' photo');file.href=filePage(c);file.rel='noopener';const lic=node('a',c.l);lic.href=c.lu;lic.rel='noopener license';span.append(file,' by '+(c.a||'the author named on the file page')+', ',lic);return span;}

if(rankingHost)ranking();
if(!arena)return;

let state={garage:[],daily:null,picks:0};let persistent=true;
try{const saved=JSON.parse(localStorage.getItem(KEY)||'{}');state.garage=cleanGarage(saved.garage,idSet);state.picks=Number.isInteger(saved.picks)&&saved.picks>0?saved.picks:0;const d=saved.daily;if(d&&Number.isInteger(d.day)&&Array.isArray(d.picks)&&d.picks.length<=DAILY_PICKS&&d.picks.every(p=>p===0||p===1))state.daily={day:d.day,picks:d.picks,sent:d.sent===true};}catch{persistent=false;}
function save(){try{localStorage.setItem(KEY,JSON.stringify(state));persistent=true;}catch{persistent=false;}}

const pairHost=$('[data-jury-pair]'),progress=$('[data-jury-progress]'),credits=$('[data-jury-credits]'),result=$('[data-jury-result]'),skip=$('[data-jury-skip]'),status=$('[data-jury-status]'),swapHost=$('[data-jury-swap]'),bays=$('[data-jury-bays]');
let mode='free',deck=[],pair=null,busy=false,queue=[];
const today=dayNumber(),todays=dailyPairs(ids,today);
if(state.daily&&state.daily.day!==today)state.daily=null;

/* ---- verdicts reach the server in small batches; a failed batch is dropped, never retried in a loop ---- */
function flush(keepalive=false){if(!queue.length)return;const v=queue.splice(0,25);fetch('/api/jury/votes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({v}),keepalive}).catch(()=>{});}
addEventListener('pagehide',()=>flush(true));document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flush(true);});

function say(text){status.textContent=text;}
function show(){
  result.hidden=true;pairHost.hidden=false;skip.hidden=mode==='daily';
  if(mode==='daily'){const i=state.daily?state.daily.picks.length:0;if(i>=DAILY_PICKS){finishDaily();return;}pair=todays[i];progress.textContent=`Today’s ten · pick ${i+1} of ${DAILY_PICKS}. Same pairs for everyone today.`;}
  else{const next=drawPair(deck,ids);pair=next.pair;deck=next.deck;progress.textContent=state.picks?`${state.picks.toLocaleString()} verdict${state.picks===1?'':'s'} returned. Which would you rather have?`:'Which would you rather have?';}
  pairHost.replaceChildren();credits.replaceChildren('Photos: ');
  pair.forEach((id,side)=>{const c=byId.get(id),b=node('button','','jury-card');b.type='button';b.dataset.pick=String(side);b.setAttribute('aria-label','Pick the '+c.n);const label=node('span','','jury-name');label.append(node('small',c.b),node('b',c.n));b.append(photo(c,true),label);pairHost.append(b);if(side===0)pairHost.append(node('span','or','jury-or'));credits.append(credit(c),side===0?' · ':'');});
  busy=false;
}
function choose(side){
  if(busy||!pair)return;busy=true;
  const winner=pair[side],loser=pair[1-side],car=byId.get(winner);
  queue.push([winner,loser]);state.picks++;
  if(mode==='daily'){state.daily=state.daily||{day:today,picks:[]};state.daily.picks.push(side);}
  const parked=park(state.garage,winner);state.garage=parked.garage;save();
  if(parked.state==='parked'){say(`${car.n} parked in bay ${state.garage.length} of ${BAYS}.`+(persistent?'':' Browser storage is unavailable, so this garage lasts only for this visit.'));swapHost.hidden=true;if(state.garage.length===BAYS)track('garage_full');}
  else if(parked.state==='full')offerSwap(car);
  else swapHost.hidden=true;
  garage();
  if(state.picks===1)track('first_pick');if(state.picks===10)track('ten_picks');
  if(queue.length>=8)flush();
  const chosen=pairHost.querySelector(`[data-pick="${side}"]`);if(chosen)chosen.classList.add('picked');
  setTimeout(show,matchMedia('(prefers-reduced-motion: reduce)').matches?0:260);
}
pairHost.addEventListener('click',e=>{const b=e.target.closest('[data-pick]');if(b)choose(Number(b.dataset.pick));});
document.addEventListener('keydown',e=>{if(e.target.closest('input,textarea,select,[contenteditable]')||e.altKey||e.ctrlKey||e.metaKey||pairHost.hidden)return;if(e.key==='ArrowLeft'){e.preventDefault();choose(0);}if(e.key==='ArrowRight'){e.preventDefault();choose(1);}});
skip.addEventListener('click',()=>{if(mode==='free'&&!busy)show();});
document.querySelectorAll('[data-jury-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.juryMode;document.querySelectorAll('[data-jury-mode]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));show();}));

/* ---- the garage ---- */
function offerSwap(car){
  swapHost.hidden=false;swapHost.replaceChildren(node('p',`Your garage is full. To park the ${car.n}, choose a car to release:`));
  const list=node('div','','jury-swap-list');
  for(const id of state.garage){const b=node('button',byId.get(id).n,'secondary');b.type='button';b.addEventListener('click',()=>{state.garage=swap(state.garage,id,car.id);save();swapHost.hidden=true;say(`${byId.get(id).n} released. ${car.n} parked.`);track('garage_swap');garage();});list.append(b);}
  const keep=node('button','Keep my ten','secondary');keep.type='button';keep.addEventListener('click',()=>{swapHost.hidden=true;});
  swapHost.append(list,keep);
}
function bay(c,removable){const li=node('li','','jury-bay');if(!c){li.classList.add('empty');li.append(node('span','Empty bay'));return li;}const a=node('a');a.href=c.u;a.append(photo(c,false),node('b',c.n));li.append(a);if(removable){const x=node('button','Release','jury-release');x.type='button';x.setAttribute('aria-label','Release the '+c.n+' from your garage');x.addEventListener('click',()=>{state.garage=state.garage.filter(id=>id!==c.id);save();say(c.n+' released.');garage();});li.append(x);}return li;}
function garage(){
  const mine=state.garage.map(id=>byId.get(id));
  bays.replaceChildren(...Array.from({length:BAYS},(_,i)=>bay(mine[i],true)));
  $('[data-jury-count]').textContent=`${mine.length} of ${BAYS}`;
  $('[data-jury-taste]').textContent=mine.length>1?taste(mine)+'.':'Every car you pick is parked here until all ten bays are full.';
  const list=$('[data-jury-garage-credits]');list.replaceChildren(...mine.map(c=>{const li=node('li');li.append(credit(c));return li;}));
  for(const b of document.querySelectorAll('[data-jury-share],[data-jury-copy],[data-jury-empty]'))b.disabled=!mine.length;
}
$('[data-jury-empty]').addEventListener('click',()=>{if(!confirm('Release every car from this browser’s garage?'))return;state.garage=[];save();garage();say('Garage emptied.');});
async function copy(text,done){try{await navigator.clipboard.writeText(text);say(done);}catch{say('Copy this: '+text);}}
$('[data-jury-copy]').addEventListener('click',()=>{copy(garageLink(state.garage,location.origin),'Garage link copied.');track('garage_link');});
$('[data-jury-share]').addEventListener('click',async()=>{
  const link=garageLink(state.garage,location.origin),text='My ten-bay dream garage. Pick yours:';
  say('Preparing your garage card…');
  let file=null;
  try{const blob=await card(state.garage.map(id=>byId.get(id)));file=new File([blob],'my-dream-garage.png',{type:'image/png'});}catch{/* The link still works when a photograph cannot be drawn. */}
  track('garage_share');
  try{
    if(file&&navigator.canShare&&navigator.canShare({files:[file]})){await navigator.share({files:[file],text:text+' '+link});say('Shared.');return;}
    if(!file&&navigator.share){await navigator.share({text,url:link});say('Shared.');return;}
  }catch(e){if(e&&e.name==='AbortError'){say('');return;}}
  if(file){const a=node('a');a.href=URL.createObjectURL(file);a.download=file.name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),4000);await copy(link,'Garage card downloaded and link copied. Post them together.');}
  else await copy(link,'Garage link copied.');
});
function load(src){return new Promise((ok,fail)=>{const i=new Image();i.crossOrigin='anonymous';i.referrerPolicy='no-referrer';i.onload=()=>ok(i);i.onerror=fail;i.src=src;});}
async function card(mine){
  const W=1080,H=1350,canvas=node('canvas');canvas.width=W;canvas.height=H;const g=canvas.getContext('2d');
  g.fillStyle='#10201d';g.fillRect(0,0,W,H);g.fillStyle='#f5f3ed';g.textBaseline='alphabetic';
  g.font='800 62px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText('MY DREAM GARAGE',40,92);
  g.font='500 28px system-ui,-apple-system,Segoe UI,sans-serif';g.fillStyle='#9fc4b8';g.fillText(mine.length>1?taste(mine):'Ten bays. One verdict at a time.',40,136);
  const images=await Promise.all(mine.map(c=>load(c.t).catch(()=>null)));
  if(mine.length&&images.every(i=>!i))throw Error('no photographs');
  const cw=492,ch=200,gap=16,left=40,top=168;
  for(let i=0;i<BAYS;i++){
    const x=left+(i%2)*(cw+gap),y=top+Math.floor(i/2)*(ch+gap),c=mine[i],img=images[i];
    g.fillStyle='#1b322d';g.fillRect(x,y,cw,ch);
    if(!c){g.strokeStyle='#35544c';g.setLineDash([10,8]);g.strokeRect(x+1,y+1,cw-2,ch-2);g.setLineDash([]);g.fillStyle='#5f8377';g.font='500 24px system-ui,sans-serif';g.fillText('Empty bay',x+24,y+ch/2+8);continue;}
    if(img){const s=Math.max(cw/img.naturalWidth,ch/img.naturalHeight),sw=cw/s,sh=ch/s;g.drawImage(img,(img.naturalWidth-sw)/2,(img.naturalHeight-sh)/2,sw,sh,x,y,cw,ch);}
    const shade=g.createLinearGradient(0,y+ch-96,0,y+ch);shade.addColorStop(0,'rgba(0,0,0,0)');shade.addColorStop(1,'rgba(0,0,0,.86)');g.fillStyle=shade;g.fillRect(x,y+ch-96,cw,96);
    g.fillStyle='#fff';g.font='700 27px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText(fit(g,c.n,cw-28),x+14,y+ch-30);
    g.fillStyle='#d5ded9';g.font='400 13px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText(fit(g,'Photo: '+(c.a||'see Wikimedia Commons')+' · '+c.l,cw-28),x+14,y+ch-11);
  }
  g.fillStyle='#f5f3ed';g.font='700 34px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText('Pick yours at motorjury.com/jury',40,H-72);
  g.fillStyle='#9fc4b8';g.font='400 20px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText('Photographs from Wikimedia Commons, credited on each car.',40,H-36);
  return new Promise((ok,fail)=>canvas.toBlob(b=>b?ok(b):fail(Error('blank')),'image/png'));
}
function fit(g,text,width){if(g.measureText(text).width<=width)return text;let t=text;while(t.length>4&&g.measureText(t+'…').width>width)t=t.slice(0,-1);return t+'…';}

/* ---- the daily round ---- */
async function finishDaily(){
  pairHost.hidden=true;skip.hidden=true;credits.replaceChildren();result.hidden=false;result.replaceChildren(node('p','Counting the world’s verdicts…'));
  progress.textContent=`Today’s ten · round ${today} complete.`;
  const picks=state.daily.picks;let split=null;
  try{
    const sent=state.daily.sent;const r=sent?await fetch('/api/jury/daily?day='+today):await fetch('/api/jury/daily',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({day:today,picks})});
    if(r.ok){split=(await r.json()).split;if(!sent){state.daily.sent=true;save();track('daily_done');}}
  }catch{/* The result still shows without the world's split. */}
  const marks=split?agreement(picks,split):picks.map(()=>null),known=marks.filter(m=>m!==null);
  result.replaceChildren(node('h3',known.length?`You sided with the world on ${known.filter(Boolean).length} of ${known.length}.`:'You are among today’s first jurors.'));
  if(!known.length)result.append(node('p','Too few verdicts are in to call a majority. Come back later today to see how the world voted.','note'));
  const list=node('ol','','jury-daily-list');
  todays.forEach((p,i)=>{const mine=byId.get(p[picks[i]]),other=byId.get(p[1-picks[i]]),li=node('li');const total=split?split[i][0]+split[i][1]:0;li.append(node('span',marks[i]===null?'⬜':marks[i]?'🟩':'🟥'),node('b',mine.n),' over '+other.n+(total>=5?` · ${Math.round(100*split[i][picks[i]]/total)}% agreed`:''));list.append(li);});
  const actions=node('div','','actions'),share=node('button','Share my result'),back=node('button','Back to free play','secondary');share.type=back.type='button';
  const text=shareText(today,marks,location.origin);
  share.addEventListener('click',async()=>{track('daily_share');try{if(navigator.share){await navigator.share({text});return;}}catch(e){if(e&&e.name==='AbortError')return;}copy(text,'Result copied. Paste it anywhere.');});
  back.addEventListener('click',()=>$('[data-jury-mode="free"]').click());
  actions.append(share,back);result.append(list,actions,node('p','A new ten arrive at midnight, Coordinated Universal Time.','note'));
}

/* ---- a garage someone shared ---- */
const shared=parseGarage(location.search,idSet),sharedHost=$('[data-jury-shared]');
if(shared.length&&sharedHost){sharedHost.hidden=false;const mineToo=shared.map(id=>byId.get(id));$('[data-jury-shared-grid]',sharedHost).replaceChildren(...mineToo.map(c=>bay(c,false)));$('[data-jury-shared-taste]',sharedHost).textContent=mineToo.length>1?taste(mineToo)+'.':'';const list=node('p','Photos: ','jury-credits');mineToo.forEach((c,i)=>list.append(credit(c),i<mineToo.length-1?' · ':''));sharedHost.append(list);track('shared_garage_view');}

/* ---- the world's verdict, top five ---- */
const top=$('[data-jury-top-list]');
if(top)fetch('/api/jury/ranking').then(r=>r.ok?r.json():Promise.reject()).then(d=>{const s=$('[data-jury-top-status]');s.textContent=d.total?`${d.total.toLocaleString()} verdict${d.total===1?'':'s'} returned so far.`+(d.cars.length<5?' The ranking appears once enough cars have had a fair hearing.':''):'No verdicts yet. Yours can be the first.';if(d.cars.length>=5)top.replaceChildren(...d.cars.slice(0,5).filter(r=>byId.has(r.id)).map(r=>{const c=byId.get(r.id),li=node('li'),a=node('a',c.n);a.href=c.u;li.append(a,` · picked ${Math.round(100*r.w/r.s)}% of ${r.s.toLocaleString()} showings`);return li;}));}).catch(()=>{$('[data-jury-top-status]').textContent='The ranking is unavailable right now.';});

garage();show();

function ranking(){
  const list=$('[data-jury-ranking-list]'),s=$('[data-jury-ranking-status]'),select=$('[data-jury-country]');
  select.replaceChildren(...COUNTRIES.map(([code,name])=>{const o=node('option',name);o.value=code;return o;}));
  function draw(){
    s.textContent='Counting…';
    fetch('/api/jury/ranking'+(select.value?'?cc='+select.value:'')).then(r=>r.ok?r.json():Promise.reject()).then(d=>{
      const where=select.value?' from '+select.selectedOptions[0].textContent:'';
      s.textContent=d.total?`${d.total.toLocaleString()} verdict${d.total===1?'':'s'}${where} so far. A car is ranked after five showings; the order uses the cautious end of its win rate, so a small sample cannot jump the queue.`:`No verdicts${where} yet.`;
      list.replaceChildren(...d.cars.filter(r=>byId.has(r.id)).map(r=>{const c=byId.get(r.id),li=node('li','','jury-rank'),a=node('a');a.href=c.u;a.append(photo(c,false),node('b',c.n));li.append(a,node('span',`Picked ${Math.round(100*r.w/r.s)}% of ${r.s.toLocaleString()} showings`),credit(c));return li;}));
    }).catch(()=>{s.textContent='The ranking is unavailable right now. Try again shortly.';});
  }
  select.addEventListener('change',draw);draw();
}
}
