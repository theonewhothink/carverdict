import {filterCars,modelLink,suggestCars,photoUrl} from './catalogue-core.mjs';
let cataloguePromise;
function readCatalogue(){return cataloguePromise||(cataloguePromise=fetch('/assets/catalogue-data.json?v=__CATALOGUE_VERSION__').then(r=>{if(!r.ok)throw Error('Unavailable');return r.json();}).catch(e=>{cataloguePromise=null;throw e;}));}
const app=document.querySelector('[data-catalogue]');
if(app){
 const form=app.querySelector('[data-catalogue-form]'),grid=app.querySelector('[data-catalogue-grid]'),status=app.querySelector('[data-catalogue-status]'),more=app.querySelector('[data-catalogue-more]');
 let rows,pending,shown=24,timer,revision=0;
 const read=()=>({query:form.elements.q.value,brand:form.elements.brand.value,era:form.elements.era.value,photos:form.elements.photos.checked,sort:form.elements.sort.value});
 function photo(r){const frame=document.createElement('div');frame.className='collection-photo';if(r.p&&r.e!=='unavailable'){const img=document.createElement('img');img.src=photoUrl(r);img.alt=r.n+' · catalogue photograph';img.width=480;img.height=300;img.loading='lazy';img.decoding='async';img.referrerPolicy='no-referrer';img.addEventListener('error',()=>{img.remove();frame.textContent='Photo unavailable';frame.classList.add('photo-missing');},{once:true});frame.append(img);}else{frame.classList.add('photo-missing');frame.textContent=r.e==='unavailable'?'Photo reference unavailable':'Photo not yet catalogued';}return frame;}
 function card(r){const article=document.createElement('article');article.className='collection-card';const link=document.createElement('a');link.href=modelLink(r);link.append(photo(r));const body=document.createElement('div');body.className='collection-card-body';const brand=document.createElement('span');brand.className='collection-brand';brand.textContent=r.b;const h=document.createElement('h3');h.textContent=r.n;body.append(brand,h);link.append(body);article.append(link);const credit=document.createElement('a');credit.className='collection-credit';credit.href=r.p?'https://commons.wikimedia.org/wiki/File:'+encodeURIComponent((r.i||r.p).replace(/ /g,'_')):r.u;credit.textContent=r.p?'Photo & attribution ↗':'Open the catalogue entry →';credit.rel='noopener';article.append(credit);const save=document.createElement('button');save.type='button';save.className='save-car';save.dataset.saveCar=r.u;save.dataset.carName=r.n;save.textContent='Save car +';save.setAttribute('aria-pressed','false');article.append(save);return article;}
 async function load(){if(rows)return rows;if(!pending)pending=readCatalogue().then(data=>rows=data).catch(e=>{pending=null;throw e;});return pending;}
 async function render(reset=true){const request=++revision;if(reset)shown=24;status.textContent='Searching the collection…';grid.setAttribute('aria-busy','true');try{const data=await load();if(request!==revision)return;const options=read(),matches=filterCars(data,options);grid.replaceChildren(...matches.slice(0,shown).map(card));status.textContent=matches.length?`${matches.length.toLocaleString()} matching entries · showing ${Math.min(shown,matches.length)}`:'No matching entries. Try a shorter name or remove a filter.';more.hidden=shown>=matches.length;const params=new URLSearchParams();for(const key of ['query','brand','era','sort'])if(options[key])params.set(key==='query'?'q':key,options[key]);if(options.photos)params.set('photos','1');history.replaceState(null,'',location.pathname+(params.size?'?'+params:''));}catch{if(request!==revision)return;status.textContent='Search could not load. The complete A–Z directory and marque lists still work.';}finally{if(request===revision)grid.removeAttribute('aria-busy');}}
 form.addEventListener('submit',e=>{e.preventDefault();clearTimeout(timer);render();});
 form.elements.q.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>render(),200);});
 for(const name of ['brand','era','photos','sort'])form.elements[name].addEventListener('change',()=>render());
 app.querySelector('[data-catalogue-reset]').addEventListener('click',()=>{form.reset();if(app.dataset.catalogueBrand)form.elements.brand.value=app.dataset.catalogueBrand;render();});
 more.addEventListener('click',()=>{shown+=24;render(false);});
 app.querySelectorAll('[data-marque]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();form.elements.brand.value=a.dataset.marque;render();}));
 if(app.dataset.catalogueBrand)form.elements.brand.value=app.dataset.catalogueBrand;
 const params=new URLSearchParams(location.search);for(const name of ['q','brand','era','sort'])if(params.has(name))form.elements[name].value=params.get(name);form.elements.photos.checked=params.get('photos')==='1';
 if(params.size)render();
 async function showRosterPhoto(){
  if(!location.hash.startsWith('#m-'))return;
  const target=document.getElementById(location.hash.slice(1));if(!target)return;
  const details=target.closest('details');if(details)details.open=true;
  try{const data=await load(),row=data.find(r=>r.u===location.pathname+location.hash);if(!row)return;
   app.closest('main').querySelectorAll('[data-roster-preview]').forEach(n=>n.remove());
   const preview=card(row);preview.dataset.rosterPreview='';target.prepend(preview);target.scrollIntoView({block:'start'});
  }catch{/* The static roster and original photograph link remain available. */}
 }
 if(location.hash)showRosterPhoto();
 addEventListener('hashchange',showRosterPhoto);
}
document.querySelectorAll('[data-collection-entry]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();location.href='/library/?'+new URLSearchParams({q:form.elements.q.value});}));

for(const input of document.querySelectorAll('[data-collection-entry] input[name=q], [data-catalogue-form] input[name=q]')){
 const wrapper=document.createElement('div');wrapper.className='search-combobox';input.before(wrapper);wrapper.append(input);
 const list=document.createElement('div');list.className='search-suggestions';list.id=input.id+'-suggestions';list.setAttribute('role','listbox');list.hidden=true;wrapper.append(list);
 input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',list.id);input.setAttribute('aria-expanded','false');
 let matches=[],active=-1,request=0;
 function close(){list.hidden=true;active=-1;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');}
 function highlight(){[...list.children].forEach((n,i)=>n.setAttribute('aria-selected',String(i===active)));if(active>=0)input.setAttribute('aria-activedescendant',list.children[active].id);else input.removeAttribute('aria-activedescendant');}
 async function update(){const current=++request;if(input.value.trim().length<2){close();return;}try{
  const rows=await readCatalogue();if(current!==request)return;matches=suggestCars(rows,input.value);active=-1;
  list.replaceChildren(...matches.map((r,i)=>{const option=document.createElement('button');option.type='button';option.id=list.id+'-'+i;option.setAttribute('role','option');option.setAttribute('aria-selected','false');option.tabIndex=-1;
   const title=document.createElement('b');title.textContent=r.n;const detail=document.createElement('span');detail.textContent=r.b+' · Open car';option.append(title,detail);
   option.addEventListener('pointerdown',e=>e.preventDefault());option.addEventListener('click',()=>{location.href=modelLink(r);});return option;}));
  list.hidden=!matches.length;input.setAttribute('aria-expanded',String(!!matches.length));input.removeAttribute('aria-activedescendant');
 }catch{close();}}
 input.addEventListener('input',update);input.addEventListener('focus',update);
 input.addEventListener('keydown',e=>{if(e.key==='Escape'){++request;close();return;}if(list.hidden)return;
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();active=active<0?(e.key==='ArrowDown'?0:matches.length-1):(active+(e.key==='ArrowDown'?1:-1)+matches.length)%matches.length;highlight();}
  if(e.key==='Enter'&&active>=0){e.preventDefault();e.stopImmediatePropagation();location.href=modelLink(matches[active]);}
 });input.addEventListener('blur',()=>{++request;close();});
}
if(location.hash.startsWith('#m-')){const target=document.getElementById(location.hash.slice(1));if(target){const details=target.closest('details');if(details)details.open=true;target.scrollIntoView({block:'center'});}}

// Keep failed external photographs readable without leaving broken image icons.
for(const img of document.querySelectorAll('.collection-photo img')){
 const unavailable=()=>{const frame=img.closest('.collection-photo');img.remove();frame.textContent='Photo unavailable';frame.classList.add('photo-missing');};
 if(img.complete&&!img.naturalWidth)unavailable();else img.addEventListener('error',unavailable,{once:true});
}
