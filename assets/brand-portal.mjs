const root=document.querySelector('[data-brand-portal]');
if(root){
 // Automatic motion stays optional; the picture, destination and credit change together.
 const hero=root.querySelector('[data-hero-carousel]');
 if(hero){
  const slides=[...hero.querySelectorAll('[data-hero-slide]')],credits=[...hero.querySelectorAll('[data-hero-credit]')],toggle=hero.querySelector('[data-hero-toggle]'),motion=matchMedia('(prefers-reduced-motion: reduce)');
  let index=0,timer=null,paused=motion.matches,inView=true,focused=false;
  slides.slice(1).forEach(slide=>{const img=slide.querySelector('img');img.loading='eager';img.fetchPriority='low';});
  function show(next){const img=slides[next].querySelector('img');if(!img.complete||!img.naturalWidth)return;index=next;slides.forEach((slide,i)=>{slide.hidden=i!==index;credits[i].hidden=i!==index;});hero.querySelector('[data-hero-label]').textContent=slides[index].dataset.heroName;hero.querySelector('[data-hero-count]').textContent=(index+1)+' / '+slides.length;}
  function schedule(){clearInterval(timer);timer=null;toggle.textContent=paused?'Play':'Pause';toggle.setAttribute('aria-label',(paused?'Play':'Pause')+' hero slideshow');if(!paused&&!document.hidden&&inView&&!focused)timer=setInterval(()=>show((index+1)%slides.length),Number(hero.dataset.heroInterval));}
  hero.querySelector('.bp-hero-controls').hidden=false;
  toggle.addEventListener('click',()=>{paused=!paused;schedule();});
  hero.querySelector('[data-hero-previous]').addEventListener('click',()=>show((index+slides.length-1)%slides.length));hero.querySelector('[data-hero-next]').addEventListener('click',()=>show((index+1)%slides.length));
  hero.addEventListener('focusin',()=>{focused=true;schedule();});hero.addEventListener('focusout',e=>{focused=hero.contains(e.relatedTarget);schedule();});
  document.addEventListener('visibilitychange',schedule);motion.addEventListener('change',e=>{paused=e.matches;schedule();});
  if('IntersectionObserver' in window)new IntersectionObserver(entries=>{inView=entries[0].isIntersecting;schedule();},{threshold:0}).observe(hero);
  schedule();
 }
 // The whole editorial feature, all image credits and every model link exist in HTML.
 const tabs=[...root.querySelectorAll('[data-generation]')],panels=[...root.querySelectorAll('.bp-generation')];
 function generation(index){tabs.forEach((tab,i)=>{tab.setAttribute('aria-selected',String(i===index));tab.tabIndex=i===index?0:-1;panels[i].hidden=i!==index;});}
 if(tabs.length&&tabs.length===panels.length){
 root.querySelector('.bp-generation-tabs').hidden=false;
 panels.forEach((panel,i)=>{panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tabs[i].id);});
 generation(0);
 tabs.forEach((tab,i)=>{tab.addEventListener('click',()=>generation(i));tab.addEventListener('keydown',e=>{let target;if(e.key==='ArrowRight')target=(i+1)%tabs.length;if(e.key==='ArrowLeft')target=(i-1+tabs.length)%tabs.length;if(e.key==='Home')target=0;if(e.key==='End')target=tabs.length-1;if(target!==undefined){e.preventDefault();generation(target);tabs[target].focus();}});});
 }

 const filters=[...root.querySelectorAll('[data-photo-filter]')],items=[...root.querySelectorAll('[data-photo-group]')];
 const filterBar=root.querySelector('.bp-gallery-filters');if(filterBar)filterBar.hidden=false;
 filters.forEach(button=>button.addEventListener('click',()=>{const group=button.dataset.photoFilter;filters.forEach(el=>el.setAttribute('aria-pressed',String(el===button)));items.forEach(el=>el.hidden=group!=='All'&&el.dataset.photoGroup!==group);const count=items.filter(el=>!el.hidden).length;root.querySelector('[data-gallery-status]').textContent=count+' photographs · '+(group==='All'?'all collections':group);}));

 // Native dialog provides modal focus containment and Escape support.
 if(items.length&&typeof HTMLDialogElement!=='undefined'&&typeof HTMLDialogElement.prototype.showModal==='function'){
  const data=JSON.parse(document.getElementById('bp-photo-data').textContent),dialog=document.createElement('dialog');dialog.className='bp-lightbox';dialog.setAttribute('aria-label',(root.dataset.brandName||'Porsche')+' photograph viewer');
  const bar=document.createElement('div');bar.className='bp-lightbox-bar';const counter=document.createElement('span'),controls=document.createElement('div');controls.className='bp-lightbox-controls';
  const makeButton=(text,label)=>{const button=document.createElement('button');button.type='button';button.textContent=text;button.setAttribute('aria-label',label);return button;};
  const previous=makeButton('←','Previous photograph'),next=makeButton('→','Next photograph'),close=makeButton('Close ×','Close photograph viewer');controls.append(previous,next,close);bar.append(counter,controls);
  const figure=document.createElement('figure'),image=document.createElement('img'),caption=document.createElement('figcaption'),status=document.createElement('p');status.className='bp-lightbox-status';status.setAttribute('role','status');image.referrerPolicy='no-referrer';figure.append(image,caption);dialog.append(bar,figure,status);root.append(dialog);let current=0,lastTrigger;
  function show(index){current=index;const photo=data[index];counter.textContent=(index+1)+' / '+data.length+' · '+photo.name;image.alt=photo.name;status.textContent='';image.src=photo.large;caption.replaceChildren(...[...items[index].querySelector('figcaption').children].map(el=>el.cloneNode(true)));const link=document.createElement('a');link.href=photo.url;link.textContent='Open this car →';link.style.display='inline-block';link.style.marginTop='12px';caption.append(link);}
  function move(delta){const visible=items.map((el,i)=>el.hidden?-1:i).filter(i=>i>=0),position=visible.indexOf(current);show(visible[(position+delta+visible.length)%visible.length]);}
  image.addEventListener('error',()=>{status.textContent='The larger photograph is unavailable. The credited source link below remains available.';});
  root.querySelectorAll('[data-photo-open]').forEach(button=>{button.hidden=false;button.addEventListener('click',()=>{lastTrigger=button;show(Number(button.dataset.photoOpen));dialog.showModal();close.focus();});});
  previous.addEventListener('click',()=>move(-1));next.addEventListener('click',()=>move(1));close.addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>lastTrigger?.focus());
  dialog.addEventListener('keydown',e=>{if(e.key==='ArrowRight'){e.preventDefault();move(1);}if(e.key==='ArrowLeft'){e.preventDefault();move(-1);}});
  dialog.addEventListener('click',e=>{if(e.target===dialog){const rect=dialog.getBoundingClientRect();if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)dialog.close();}});
 }

 // Real video thumbnails load first; the privacy-enhanced player waits for Play.
 root.querySelectorAll('[data-video]').forEach(button=>{button.hidden=false;button.addEventListener('click',()=>{const id=button.dataset.video;if(!/^[A-Za-z0-9_-]{11}$/.test(id))return;const slot=button.closest('[data-video-slot]'),iframe=document.createElement('iframe');iframe.src='https://www.youtube-nocookie.com/embed/'+id+'?autoplay=1&rel=0';iframe.title=button.getAttribute('aria-label').replace(/^Play /,'');iframe.allow='accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; fullscreen';iframe.allowFullscreen=true;iframe.referrerPolicy='strict-origin-when-cross-origin';slot.replaceChildren(iframe);iframe.focus();});});

 const form=root.querySelector('[data-portal-model-form]'),rows=[...root.querySelectorAll('[data-model-name]')],more=root.querySelector('[data-more-models]'),modelStatus=root.querySelector('[data-model-status]');
 const normalize=value=>String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();let expanded=root.hasAttribute('data-full-directory');
 function directory(){const q=normalize(form.elements.q.value),tokens=q.split(' ').filter(Boolean);let matched=0,shown=0;rows.forEach(row=>{const text=normalize(row.dataset.modelName),match=tokens.every(t=>text.includes(t));if(match)matched++;row.hidden=!match||(!q&&!expanded&&shown>=18);if(!row.hidden)shown++;});modelStatus.textContent=matched+' matching catalogue entries · showing '+shown;more.hidden=!!q||expanded||matched<=shown;root.querySelector('[data-no-models]').hidden=matched>0;}
 function revealFragment(){if(!location.hash.startsWith('#m-'))return;const id=decodeURIComponent(location.hash.slice(1)),target=rows.find(row=>row.id===id);if(!target)return;expanded=true;form.elements.q.value='';directory();requestAnimationFrame(()=>target.scrollIntoView({block:'center'}));}
 form.addEventListener('submit',e=>{e.preventDefault();directory();});form.elements.q.addEventListener('input',directory);more.addEventListener('click',()=>{expanded=true;directory();});directory();revealFragment();addEventListener('hashchange',revealFragment);
 // Keep attribution visible if a third-party image disappears.
 root.querySelectorAll('.bp-photo img,.bp-hero img').forEach(img=>{const fail=()=>{img.hidden=true;const note=document.createElement('span');note.className='bp-image-unavailable';note.textContent='Photograph unavailable — source and credits below';img.parentElement.append(note);};if(img.complete&&!img.naturalWidth)fail();else img.addEventListener('error',fail,{once:true});});
}
