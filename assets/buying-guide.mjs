import {guidance,questionPayload,safeLink} from './buying-guide-core.mjs';
const panel=document.querySelector('[data-buying-guide]');
if(panel){
 const input=panel.querySelector('textarea'),form=panel.querySelector('form'),thread=panel.querySelector('[data-guide-thread]'),mode=panel.querySelector('[data-guide-mode]');
 const brief=document.querySelector('#brief-form');let enabled=false,busy=false,controller,history=[],generation=0;
 const context=()=>({year:brief?.elements.namedItem('year')?.value||'',powertrain:brief?.elements.namedItem('powertrain')?.value||'unknown'});
 function updateContext(){const c=context();panel.querySelector('[data-guide-context]').textContent=`${c.year||'Year not confirmed'} · ${c.powertrain==='unknown'?'Powertrain not confirmed':c.powertrain} · US RAV4`;}
 function message(role,title,text){const box=document.createElement('article');box.className=`guide-message ${role}`;const h=document.createElement('h3');h.textContent=title;const p=document.createElement('p');p.textContent=text;box.append(h,p);thread.append(box);return {box,p};}
 function renderLinks(box,links){const row=document.createElement('div');row.className='guide-links';for(const [label,value] of links){const url=safeLink(value,location.origin);if(!url)continue;const a=document.createElement('a');a.textContent=label;a.href=url;a.rel='noopener';row.append(a);}box.append(row);}
 function apply(next){if(!brief)return;for(const key of ['year','powertrain'])if(next[key])brief.elements.namedItem(key).value=next[key];brief.dispatchEvent(new Event('change',{bubbles:true}));updateContext();}
 function showGuidance(result){const {box}=message('guide',result.title,result.text);renderLinks(box,result.links);
  if(!result.blocked&&!result.next.unsupported&&!result.next.ambiguous&&result.next.year){
   const label=`Use ${result.next.year} ${result.next.powertrain==='unknown'?'RAV4':result.next.powertrain+' RAV4'}`;
   const a=document.createElement(brief?'button':'a');a.textContent=label;a.className='guide-apply';
   if(brief){a.type='button';a.addEventListener('click',()=>{apply(result.next);a.textContent='Added to your brief';});}
   else{const params=new URLSearchParams({year:result.next.year,powertrain:result.next.powertrain});a.href='/buying-brief/?'+params;}box.append(a);
  }
  const actions=document.createElement('div');actions.className='guide-links';for(const item of result.actions){const a=document.createElement('a');a.textContent=item==='budget'?'Open the budget':item==='year'?'Choose the year':'Prepare the checklist';a.href=brief?(item==='budget'?'#budget':item==='year'?'#identify':'#checklist'):'/buying-brief/';actions.append(a);}box.append(actions);
 }
 async function askAI(text,result,requestGeneration){
  const output=message('ai','AI answer · verify against the sources','Looking at the reviewed brief…');let answer='',done=false,error=false;
  const requestController=new AbortController();controller=requestController;const timeout=setTimeout(()=>requestController.abort(),35000);
  try{
   const payload=questionPayload(text,result.next,history);
   const response=await fetch('/api/genius',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:requestController.signal});
   if(!response.ok||!response.body)throw Error('unavailable');
   const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
   while(true){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true});let split;
    while((split=buffer.indexOf('\n\n'))>=0){const frame=buffer.slice(0,split);buffer=buffer.slice(split+2);const line=frame.split('\n').find(s=>s.startsWith('data: '));if(!line)continue;
     const event=JSON.parse(line.slice(6));if(event.t==='text'){answer+=event.d||'';if(answer.length>12000)throw Error('too long');output.p.textContent=answer;}if(event.t==='error')error=true;if(event.t==='done')done=true;
    }
   }
   if(requestGeneration!==generation)return;
   if(!done||error||!answer.trim())throw Error('incomplete');
   // Link rendering uses DOM text nodes and only official/same-site destinations.
   output.p.replaceChildren();const pattern=/\[([^\]]+)\]\(([^\s)]+)\)/g;let match,last=0;
   while((match=pattern.exec(answer))){output.p.append(document.createTextNode(answer.slice(last,match.index)));const url=safeLink(match[2],location.origin);if(url){const a=document.createElement('a');a.href=url;a.rel='noopener';a.textContent=match[1];output.p.append(a);}else output.p.append(document.createTextNode(match[1]));last=pattern.lastIndex;}output.p.append(document.createTextNode(answer.slice(last)));
   history=[...history,{role:'user',content:text},{role:'assistant',content:answer}].slice(-4);
   renderLinks(output.box,[['Inspect the research','/guides/toyota-rav4-years-to-avoid/']]);
  }catch{output.box.remove();if(requestGeneration!==generation)return;mode.textContent='AI could not finish. Showing the reviewed guide instead.';showGuidance(result);}
  finally{clearTimeout(timeout);if(controller===requestController)controller=null;}
 }
 async function submit(text){if(busy||!text.trim())return;const requestGeneration=generation;const result=guidance(text,context());message('reader','Your question',result.blocked?'Private details were withheld.':text.trim());input.value='';busy=true;panel.querySelector('[data-guide-send]').disabled=true;
  try{if(enabled&&!result.blocked&&!result.next.unsupported&&!result.next.ambiguous&&result.next.year)await askAI(text,result,requestGeneration);else showGuidance(result);}
  finally{if(requestGeneration===generation){busy=false;panel.querySelector('[data-guide-send]').disabled=false;}}
 }
 form.addEventListener('submit',e=>{e.preventDefault();submit(input.value.slice(0,600));});
 panel.querySelectorAll('[data-guide-prompt]').forEach(button=>button.addEventListener('click',()=>submit(button.dataset.guidePrompt)));
 panel.querySelector('[data-guide-clear]').addEventListener('click',()=>{generation++;controller?.abort();busy=false;panel.querySelector('[data-guide-send]').disabled=false;history=[];thread.replaceChildren();input.value='';mode.textContent=enabled?'AI available · questions go to our AI provider':'Guided mode · from reviewed material';});
 brief?.addEventListener('change',updateContext);updateContext();
 fetch('/api/genius/status').then(r=>r.ok?r.json():{enabled:false}).then(data=>{enabled=data.enabled===true;mode.textContent=enabled?'AI available · questions go to our AI provider':'Guided mode · AI is not enabled';}).catch(()=>{mode.textContent='Guided mode · AI is not enabled';});
}
