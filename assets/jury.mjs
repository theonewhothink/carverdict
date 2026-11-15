// The car jury: pick one of two, fill ten bays, share the garage, see the world's verdict.
// Picks are anonymous. The garage lives in this browser; only verdict pairs reach the server.
import {BAYS,DAILY_PICKS,agreement,cleanGarage,dailyPairs,dayNumber,drawPair,garageLink,nextStreak,park,parseGarage,quizRound,shareText,swap,taste} from './jury-core.mjs';

const KEY='motorjury.jury.v1';
// Every visible string comes from the page's own language table; English is the fallback.
const I18N=(()=>{try{return JSON.parse(document.querySelector('[data-jury-i18n]').textContent);}catch{return {lang:'en',path:'/jury/',s:{}};}})();
const LANG=I18N.lang||'en',HOME=I18N.path||'/jury/';
function t(key,vars={}){const s=(I18N.s&&I18N.s[key])||key;return s.replace(/\{(\w+)\}/g,(_,k)=>k in vars?vars[k]:'{'+k+'}');}
const num=n=>Number(n).toLocaleString(LANG);
const TASTE={same:t('taste_same'),mixed:t('taste_mixed')};
// The ranking is published once it means something; until then the page shows the count toward it.
const PUBLISH_AT=1000;
const COUNTRY_CODES=['US','GB','DE','FR','IT','ES','PT','NL','PL','SE','IL','TR','AE','IN','JP','AU','CA','MX','BR'];
function countries(){let names;try{names=new Intl.DisplayNames([LANG],{type:'region'});}catch{names=null;}return [['',t('world')],...COUNTRY_CODES.map(c=>[c,names?names.of(c):c])];}
const $=(sel,root=document)=>root.querySelector(sel);
function node(tag,text,cls){const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;}
const tracked=new Set();
function track(task){if(!window.mjAnalyticsAllowed||typeof window.gtag!=='function'||tracked.has(task))return;tracked.add(task);window.gtag('event','jury_task_complete',{task_type:task});}

const arena=$('[data-jury]'),rankingHost=$('[data-jury-ranking]');
if(arena||rankingHost){
fetch('/assets/jury-data.json?v=__JURY_VERSION__').then(r=>{if(!r.ok)throw Error();return r.json();}).then(start).catch(()=>{const s=$('[data-jury-progress]')||$('[data-jury-ranking-status]');if(s)s.textContent=t('load_fail');});
}

function start(cars){
const byId=new Map(cars.map(c=>[c.id,c])),ids=cars.map(c=>c.id),idSet=new Set(ids);
const filePage=c=>'https://commons.wikimedia.org/wiki/File:'+encodeURIComponent(c.p.replace(/ /g,'_'));
function photo(c,eager){const frame=node('span','','jury-photo'),img=node('img');img.src=c.t;img.srcset=c.t.replace('/960px-','/330px-')+' 330w, '+c.t+' 960w';img.sizes='(max-width:700px) 92vw, 600px';img.alt=t('photo_alt',{car:c.n});img.width=960;img.height=600;img.decoding='async';img.referrerPolicy='no-referrer';if(eager)img.fetchPriority='high';else img.loading='lazy';img.addEventListener('error',()=>{frame.classList.add('photo-missing');frame.replaceChildren(node('span',t('photo_unavailable')));},{once:true});frame.append(img);return frame;}
function credit(c){const span=node('span');span.setAttribute('data-photo-attribution','');const file=node('a',t('photo_of',{car:c.n}));file.href=filePage(c);file.rel='noopener';const lic=node('a',c.l);lic.href=c.lu;lic.rel='noopener license';span.append(file,t('by',{author:c.a||t('author_unknown')}),lic);return span;}

if(rankingHost)ranking();
if(!arena)return;

let state={garage:[],daily:null,picks:0,streak:null,asked:false,best:0};let persistent=true;
try{const saved=JSON.parse(localStorage.getItem(KEY)||'{}');state.garage=cleanGarage(saved.garage,idSet);state.picks=Number.isInteger(saved.picks)&&saved.picks>0?saved.picks:0;const d=saved.daily;if(d&&Number.isInteger(d.day)&&Array.isArray(d.picks)&&d.picks.length<=DAILY_PICKS&&d.picks.every(p=>p===0||p===1))state.daily={day:d.day,picks:d.picks,sent:d.sent===true};const k=saved.streak;if(k&&Number.isInteger(k.last)&&Number.isInteger(k.n)&&k.n>0)state.streak={last:k.last,n:k.n};state.asked=saved.asked===true;state.best=Number.isInteger(saved.best)&&saved.best>=0&&saved.best<=10?saved.best:0;}catch{persistent=false;}
let me=null,synced='';
function save(){try{localStorage.setItem(KEY,JSON.stringify(state));persistent=true;}catch{persistent=false;}sync();}
// Signed in: the garage follows the account. A device with an empty garage adopts the saved one.
function sync(){if(!me)return;const now=state.garage.join('.');if(now===synced)return;synced=now;fetch('/api/prefs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefs:{juryGarage:state.garage}})}).catch(()=>{});}
function account(user){me=user||null;if(!me)return;const stored=cleanGarage(me.prefs&&me.prefs.juryGarage,idSet);if(!state.garage.length&&stored.length){state.garage=stored;synced=stored.join('.');save();if(typeof garage==='function')garage();}else sync();const bar=$('[data-jury-signin]');if(bar)bar.hidden=true;talk();}
document.addEventListener('cv:me',e=>account(e.detail));

const verdict=$('[data-jury-verdict]'),signin=$('[data-jury-signin]'),talkHost=$('[data-jury-talk]');let stats=null,thread=null,quiz=null;
fetch('/api/jury/stats').then(r=>r.ok?r.json():null).then(d=>{stats=d&&d.cars;}).catch(()=>{});
const pairHost=$('[data-jury-pair]'),progress=$('[data-jury-progress]'),credits=$('[data-jury-credits]'),result=$('[data-jury-result]'),skip=$('[data-jury-skip]'),status=$('[data-jury-status]'),swapHost=$('[data-jury-swap]'),bays=$('[data-jury-bays]');
let mode='free',deck=[],pair=null,busy=false,queue=[];
const today=dayNumber(),todays=dailyPairs(ids,today);
if(state.daily&&state.daily.day!==today)state.daily=null;

/* ---- verdicts reach the server in small batches; a failed batch is dropped, never retried in a loop ---- */
function flush(keepalive=false){if(!queue.length)return;const v=queue.splice(0,25);fetch('/api/jury/votes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({v}),keepalive}).catch(()=>{});}
addEventListener('pagehide',()=>flush(true));document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flush(true);});

function say(text){status.textContent=text;}
function show(){
  result.hidden=true;pairHost.hidden=false;skip.hidden=mode!=='free';pairHost.classList.toggle('quiz',mode==='quiz');
  if(mode==='quiz'){askQuiz();return;}
  if(mode==='daily'){const i=state.daily?state.daily.picks.length:0;if(i>=DAILY_PICKS){finishDaily();return;}pair=todays[i];progress.textContent=t('daily_progress',{i:i+1,n:DAILY_PICKS});}
  else{const next=drawPair(deck,ids);pair=next.pair;deck=next.deck;progress.textContent=state.picks?t('free_progress',{n:num(state.picks)}):t('free_first');}
  pairHost.replaceChildren();credits.replaceChildren(t('photos'));
  pair.forEach((id,side)=>{const c=byId.get(id),b=node('button','','jury-card');b.type='button';b.dataset.pick=String(side);b.setAttribute('aria-label',t('pick_aria',{car:c.n}));const label=node('span','','jury-name');label.append(node('small',c.b),node('b',c.n));b.append(photo(c,true),label);pairHost.append(b);if(side===0)pairHost.append(node('span',t('or_word'),'jury-or'));credits.append(credit(c),side===0?' · ':'');});
  busy=false;
}
function choose(side){
  if(busy||!pair)return;busy=true;
  const winner=pair[side],loser=pair[1-side],car=byId.get(winner);
  queue.push([winner,loser]);state.picks++;
  if(mode==='daily'){state.daily=state.daily||{day:today,picks:[]};state.daily.picks.push(side);}
  const parked=park(state.garage,winner);state.garage=parked.garage;save();
  if(parked.state==='parked'){say(t('parked',{car:car.n,i:state.garage.length,n:BAYS})+(persistent?'':t('no_storage')));swapHost.hidden=true;if(state.garage.length===BAYS){track('garage_full');say(t('full_nudge'));$('[data-jury-share]').classList.add('nudge');}}
  else if(parked.state==='full')offerSwap(car);
  else swapHost.hidden=true;
  garage();
  const seen=stats&&stats[winner],video=node('a',t('videos',{car:car.n}));video.href='https://www.youtube.com/results?search_query='+encodeURIComponent(car.n);video.rel='noopener';video.target='_blank';
  verdict.replaceChildren(seen&&seen[1]>=5?t('pick_rate',{car:car.n,p:Math.round(100*seen[0]/seen[1])}):t('recorded',{car:car.n}),video);
  if(!me&&!state.asked&&state.picks>=4&&window.CV&&Object.prototype.hasOwnProperty.call(window.CV,'me'))signin.hidden=false;
  thread=winner;if(talkHost.open)talk();else $('summary',talkHost).textContent=t('talk_car',{car:car.n});
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
  swapHost.hidden=false;swapHost.replaceChildren(node('p',t('swap_prompt',{car:car.n})));
  const list=node('div','','jury-swap-list');
  for(const id of state.garage){const b=node('button',byId.get(id).n,'secondary');b.type='button';b.addEventListener('click',()=>{state.garage=swap(state.garage,id,car.id);save();swapHost.hidden=true;say(t('swapped',{out:byId.get(id).n,car:car.n}));track('garage_swap');garage();});list.append(b);}
  const keep=node('button',t('keep'),'secondary');keep.type='button';keep.addEventListener('click',()=>{swapHost.hidden=true;});
  swapHost.append(list,keep);
}
function bay(c,removable){const li=node('li','','jury-bay');if(!c){li.classList.add('empty');li.append(node('span',t('empty_bay')));return li;}const a=node('a');a.href=c.u;a.append(photo(c,false),node('b',c.n));li.append(a);if(removable){const x=node('button',t('release'),'jury-release');x.type='button';x.setAttribute('aria-label',t('release_aria',{car:c.n}));x.addEventListener('click',()=>{state.garage=state.garage.filter(id=>id!==c.id);save();say(t('released',{car:c.n}));garage();});li.append(x);}return li;}
function garage(){
  const mine=state.garage.map(id=>byId.get(id));
  bays.replaceChildren(...Array.from({length:BAYS},(_,i)=>bay(mine[i],true)));
  $('[data-jury-count]').textContent=t('count',{n:mine.length,t:BAYS});
  $('[data-jury-taste]').textContent=mine.length>1?taste(mine,TASTE)+'.':t('garage_hint');
  const list=$('[data-jury-garage-credits]');list.replaceChildren(...mine.map(c=>{const li=node('li');li.append(credit(c));return li;}));
  for(const b of document.querySelectorAll('[data-jury-share],[data-jury-copy],[data-jury-empty]'))b.disabled=!mine.length;
}
$('[data-jury-empty]').addEventListener('click',()=>{if(!confirm(t('confirm_empty')))return;state.garage=[];save();garage();say(t('emptied'));});
async function copy(text,done){try{await navigator.clipboard.writeText(text);say(done);}catch{say(t('copy_this')+text);}}
$('[data-jury-copy]').addEventListener('click',()=>{copy(garageLink(state.garage,location.origin,HOME),t('link_copied'));track('garage_link');});
$('[data-jury-share]').addEventListener('click',async()=>{
  const link=garageLink(state.garage,location.origin,HOME),text=t('share_text');
  say(t('preparing'));
  let file=null;
  try{const blob=await card(state.garage.map(id=>byId.get(id)));file=new File([blob],'my-dream-garage.png',{type:'image/png'});}catch{/* The link still works when a photograph cannot be drawn. */}
  track('garage_share');
  try{
    if(file&&navigator.canShare&&navigator.canShare({files:[file]})){await navigator.share({files:[file],text:text+' '+link});say(t('shared'));return;}
    if(!file&&navigator.share){await navigator.share({text,url:link});say(t('shared'));return;}
  }catch(e){if(e&&e.name==='AbortError'){say('');return;}}
  if(file){const a=node('a');a.href=URL.createObjectURL(file);a.download=file.name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),4000);await copy(link,t('card_downloaded'));}
  else await copy(link,t('link_copied'));
});
function load(src){return new Promise((ok,fail)=>{const i=new Image();i.crossOrigin='anonymous';i.referrerPolicy='no-referrer';i.onload=()=>ok(i);i.onerror=fail;i.src=src;});}
async function card(mine){
  const W=1080,H=1350,canvas=node('canvas');canvas.width=W;canvas.height=H;const g=canvas.getContext('2d');
  g.fillStyle='#10201d';g.fillRect(0,0,W,H);g.fillStyle='#f5f3ed';g.textBaseline='alphabetic';
  g.font='800 62px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText(t('card_title'),40,92);
  g.font='500 28px system-ui,-apple-system,Segoe UI,sans-serif';g.fillStyle='#9fc4b8';g.fillText(mine.length>1?taste(mine,TASTE):t('card_sub'),40,136);
  const images=await Promise.all(mine.map(c=>load(c.t).catch(()=>null)));
  if(mine.length&&images.every(i=>!i))throw Error('no photographs');
  const cw=492,ch=200,gap=16,left=40,top=168;
  for(let i=0;i<BAYS;i++){
    const x=left+(i%2)*(cw+gap),y=top+Math.floor(i/2)*(ch+gap),c=mine[i],img=images[i];
    g.fillStyle='#1b322d';g.fillRect(x,y,cw,ch);
    if(!c){g.strokeStyle='#35544c';g.setLineDash([10,8]);g.strokeRect(x+1,y+1,cw-2,ch-2);g.setLineDash([]);g.fillStyle='#5f8377';g.font='500 24px system-ui,sans-serif';g.fillText(t('empty_bay'),x+24,y+ch/2+8);continue;}
    if(img){const s=Math.max(cw/img.naturalWidth,ch/img.naturalHeight),sw=cw/s,sh=ch/s;g.drawImage(img,(img.naturalWidth-sw)/2,(img.naturalHeight-sh)/2,sw,sh,x,y,cw,ch);}
    const shade=g.createLinearGradient(0,y+ch-96,0,y+ch);shade.addColorStop(0,'rgba(0,0,0,0)');shade.addColorStop(1,'rgba(0,0,0,.86)');g.fillStyle=shade;g.fillRect(x,y+ch-96,cw,96);
    g.fillStyle='#fff';g.font='700 27px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText(fit(g,c.n,cw-28),x+14,y+ch-30);
    g.fillStyle='#d5ded9';g.font='400 13px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText(fit(g,t('card_photo',{author:c.a||t('card_see'),licence:c.l}),cw-28),x+14,y+ch-11);
  }
  g.fillStyle='#f5f3ed';g.font='700 34px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText(t('card_cta',{path:HOME.replace(/\/$/,'')}),40,H-72);
  g.fillStyle='#9fc4b8';g.font='400 20px system-ui,-apple-system,Segoe UI,sans-serif';g.fillText(t('card_credit'),40,H-36);
  return new Promise((ok,fail)=>canvas.toBlob(b=>b?ok(b):fail(Error('blank')),'image/png'));
}
function fit(g,text,width){if(g.measureText(text).width<=width)return text;let t=text;while(t.length>4&&g.measureText(t+'…').width>width)t=t.slice(0,-1);return t+'…';}

/* ---- the daily round ---- */
async function finishDaily(){
  pairHost.hidden=true;skip.hidden=true;credits.replaceChildren();result.hidden=false;result.replaceChildren(node('p',t('counting')));
  progress.textContent=t('daily_done',{day:today});
  const picks=state.daily.picks;let split=null;
  try{
    const sent=state.daily.sent;const r=sent?await fetch('/api/jury/daily?day='+today):await fetch('/api/jury/daily',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({day:today,picks})});
    if(r.ok){split=(await r.json()).split;if(!sent){state.daily.sent=true;state.streak=nextStreak(state.streak,today);save();track('daily_done');}}
  }catch{/* The result still shows without the world's split. */}
  const marks=split?agreement(picks,split):picks.map(()=>null),known=marks.filter(m=>m!==null);
  result.replaceChildren(node('h3',known.length?t('sided',{a:known.filter(Boolean).length,b:known.length}):t('first_jurors')));
  if(state.streak&&state.streak.n>1)result.append(node('p',t('streak',{n:state.streak.n}),'jury-streak'));
  thread='daily:'+today;$('summary',talkHost).textContent=t('talk_daily');if(talkHost.open)talk();
  if(!known.length)result.append(node('p',t('too_few'),'note'));
  const list=node('ol','','jury-daily-list');
  todays.forEach((p,i)=>{const mine=byId.get(p[picks[i]]),other=byId.get(p[1-picks[i]]),li=node('li');const total=split?split[i][0]+split[i][1]:0;li.append(node('span',marks[i]===null?'⬜':marks[i]?'🟩':'🟥'),node('b',mine.n),t('over',{car:other.n})+(total>=5?t('agreed',{p:Math.round(100*split[i][picks[i]]/total)}):''));list.append(li);});
  const actions=node('div','','actions'),share=node('button',t('share_result')),back=node('button',t('back_free'),'secondary');share.type=back.type='button';
  const text=shareText(today,marks,location.origin,{title:t('daily_share_title'),sided:t('daily_share_sided'),first:t('daily_share_first')},HOME);
  share.addEventListener('click',async()=>{track('daily_share');try{if(navigator.share){await navigator.share({text});return;}}catch(e){if(e&&e.name==='AbortError')return;}copy(text,t('result_copied'));});
  back.addEventListener('click',()=>$('[data-jury-mode="free"]').click());
  actions.append(share,back);result.append(list,actions,node('p',t('new_ten'),'note'));
}

/* ---- name that car ---- */
function askQuiz(){
  if(!quiz)quiz={n:0,marks:[],used:[]};
  if(quiz.n>=10){endQuiz();return;}
  const q=quizRound(ids,Math.random,quiz.used),car=byId.get(q.answer);quiz.used.push(q.answer);quiz.answer=q.answer;
  progress.textContent=t('quiz_progress',{i:quiz.n+1,r:quiz.marks.filter(Boolean).length});
  verdict.replaceChildren();credits.replaceChildren(t('photo'),credit(car));
  const options=node('div','','jury-options');
  for(const id of q.options){const b=node('button',byId.get(id).n,'secondary');b.type='button';b.dataset.answer=id;options.append(b);}
  const frame=photo(car,true);frame.querySelector('img').alt=t('quiz_alt');pairHost.replaceChildren(frame,options);busy=false;
}
pairHost.addEventListener('click',e=>{const b=e.target.closest('[data-answer]');if(!b||busy||mode!=='quiz')return;busy=true;const right=b.dataset.answer===quiz.answer;quiz.marks.push(right);quiz.n++;b.classList.add(right?'right':'wrong');const good=pairHost.querySelector(`[data-answer="${quiz.answer}"]`);if(good)good.classList.add('right');say(right?t('correct'):t('it_was',{car:byId.get(quiz.answer).n}));setTimeout(()=>{if(mode==='quiz')askQuiz();},right?600:1400);});
function endQuiz(){
  const score=quiz.marks.filter(Boolean).length,grid=quiz.marks.map(m=>m?'🟩':'🟥').join('');quiz=null;
  if(score>state.best){state.best=score;save();}track('quiz_done');
  pairHost.hidden=true;credits.replaceChildren();result.hidden=false;progress.textContent=t('quiz_finished');
  const text=`${t('quiz_share_title')}\n${score}/10 ${grid}\n${location.origin}${HOME}`;
  const actions=node('div','','actions'),share=node('button',t('share_score')),again=node('button',t('play_again'),'secondary');share.type=again.type='button';
  share.addEventListener('click',async()=>{track('quiz_share');try{if(navigator.share){await navigator.share({text});return;}}catch(e){if(e&&e.name==='AbortError')return;}copy(text,t('score_copied'));});
  again.addEventListener('click',show);actions.append(share,again);
  result.replaceChildren(node('h3',t('score',{n:score})),node('p',grid),node('p',t('best',{n:state.best}),'note'),actions);
}

/* ---- sign-in ask, once, after the fourth pick ---- */
if(signin){$('[data-jury-later]',signin).addEventListener('click',()=>{signin.hidden=true;state.asked=true;save();});$('a',signin).addEventListener('click',()=>{state.asked=true;save();track('signin_click');});}

/* ---- the jury room: signed-in visitors talk about a car or the daily round ---- */
function talk(){
  if(!thread||!talkHost.open)return;
  const list=$('[data-jury-talk-list]',talkHost),form=$('form',talkHost),gate=$('[data-jury-talk-gate]',talkHost),note=$('[data-jury-talk-status]',talkHost);
  form.hidden=!me;gate.hidden=!!me;if(me)$('[data-jury-talk-as]',form).textContent=t('posts_as');
  const asked=thread;
  const draw=d=>{if(asked!==thread)return;list.replaceChildren(...d.comments.map(c=>{const li=node('li');const flag=node('button',t('report'),'jury-report');flag.type='button';flag.addEventListener('click',()=>{fetch('/api/jury/talk/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:c.id})}).then(()=>{flag.textContent=t('reported');flag.disabled=true;}).catch(()=>{});});li.append(node('b',c.name),' · ',node('time',new Date(c.created).toLocaleDateString(LANG)),node('p',c.body),flag);return li;}));note.textContent=d.comments.length?'':t('nobody');};
  fetch('/api/jury/talk?thread='+encodeURIComponent(thread)).then(r=>r.ok?r.json():Promise.reject()).then(draw).catch(()=>{note.textContent=t('talk_unavailable');});
  form.onsubmit=e=>{e.preventDefault();const box=$('textarea',form),body=box.value;if(!body.trim())return;fetch('/api/jury/talk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({thread,body})}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||t('post_failed'));box.value='';track('talk_post');draw(d);}).catch(err=>{note.textContent=err.message;});};
}
talkHost.addEventListener('toggle',talk);

/* ---- a garage someone shared ---- */
const shared=parseGarage(location.search,idSet),sharedHost=$('[data-jury-shared]');
if(shared.length&&sharedHost){sharedHost.hidden=false;const mineToo=shared.map(id=>byId.get(id));$('[data-jury-shared-grid]',sharedHost).replaceChildren(...mineToo.map(c=>bay(c,false)));$('[data-jury-shared-taste]',sharedHost).textContent=mineToo.length>1?taste(mineToo,TASTE)+'.':'';const list=node('p',t('photos'),'jury-credits');mineToo.forEach((c,i)=>list.append(credit(c),i<mineToo.length-1?' · ':''));sharedHost.append(list);track('shared_garage_view');}

/* ---- the world's verdict, top five ---- */
const top=$('[data-jury-top-list]');
if(top)fetch('/api/jury/ranking').then(r=>r.ok?r.json():Promise.reject()).then(d=>{const s=$('[data-jury-top-status]'),bar=$('[data-jury-top-bar]');if(d.total<PUBLISH_AT||d.cars.length<5){s.textContent=t('publish_wait',{at:num(PUBLISH_AT),n:num(d.total)});bar.hidden=false;bar.max=PUBLISH_AT;bar.value=d.total;return;}s.textContent=t('verdicts_so_far',{n:num(d.total)});top.replaceChildren(...d.cars.slice(0,5).filter(r=>byId.has(r.id)).map(r=>{const c=byId.get(r.id),li=node('li'),a=node('a',c.n);a.href=c.u;li.append(a,' · '+t('picked_pct',{p:Math.round(100*r.w/r.s),s:num(r.s)}));return li;}));}).catch(()=>{$('[data-jury-top-status]').textContent=t('ranking_unavailable');});

garage();show();if(window.CV&&Object.prototype.hasOwnProperty.call(window.CV,'me'))account(window.CV.me);

function ranking(){
  const list=$('[data-jury-ranking-list]'),s=$('[data-jury-ranking-status]'),select=$('[data-jury-country]');
  select.replaceChildren(...countries().map(([code,name])=>{const o=node('option',name);o.value=code;return o;}));
  function draw(){
    s.textContent=t('counting_short');
    fetch('/api/jury/ranking'+(select.value?'?cc='+select.value:'')).then(r=>r.ok?r.json():Promise.reject()).then(d=>{
      const where=select.value?t('from_where',{place:select.selectedOptions[0].textContent}):'',bar=$('[data-jury-ranking-bar]');
      if(!select.value&&d.total<PUBLISH_AT){s.textContent=t('publish_wait',{at:num(PUBLISH_AT),n:num(d.total)})+t('publish_wait_more');bar.hidden=false;bar.max=PUBLISH_AT;bar.value=d.total;list.replaceChildren();return;}
      bar.hidden=true;
      s.textContent=d.total?t('ranking_status',{where,n:num(d.total)}):t('no_verdicts',{where});
      list.replaceChildren(...d.cars.filter(r=>byId.has(r.id)).map(r=>{const c=byId.get(r.id),li=node('li','','jury-rank'),a=node('a');a.href=c.u;a.append(photo(c,false),node('b',c.n));li.append(a,node('span',t('picked_pct',{p:Math.round(100*r.w/r.s),s:num(r.s)})),credit(c));return li;}));
    }).catch(()=>{s.textContent=t('ranking_unavailable');});
  }
  select.addEventListener('change',draw);draw();
}
}
