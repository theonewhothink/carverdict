const form=document.querySelector('[data-header-search]');
if(form){
 const input=form.elements.q,list=form.querySelector('[role=listbox]'),status=form.querySelector('[role=status]');
 const normalize=value=>String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
 let promise,index,matches=[],active=-1,revision=0,timer;
 const load=()=>promise||(promise=fetch('/assets/header-search-index.json?v=__SEARCH_VERSION__').then(r=>{if(!r.ok)throw Error('Search unavailable');return r.json();}).then(data=>index=data).catch(e=>{promise=null;throw e;}));
 function close(){list.hidden=true;active=-1;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');}
 function choose(i){const row=matches[i];if(row)location.assign(row.u);}
 function highlight(){[...list.children].forEach((el,i)=>el.setAttribute('aria-selected',String(i===active)));if(active<0)input.removeAttribute('aria-activedescendant');else{const el=list.children[active];input.setAttribute('aria-activedescendant',el.id);el.scrollIntoView({block:'nearest'});}}
 input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',list.id);input.setAttribute('aria-expanded','false');
 async function update(){const request=++revision,q=normalize(input.value),tokens=q.split(' ');if(q.length<2){close();status.textContent='';return;}
  try{const data=await load();if(request!==revision||document.activeElement!==input)return;
   const brands=data.brands.filter(r=>normalize(r.n).includes(q)).sort((a,b)=>Number(normalize(b.n)===q)-Number(normalize(a.n)===q)||a.n.localeCompare(b.n)).slice(0,3).map(r=>({...r,brand:true}));
   const compact=q.replaceAll(' ','');const cars=data.cars.filter(r=>{const name=normalize(r.n+' '+r.b);return tokens.every(t=>name.includes(t))||name.replaceAll(' ','').includes(compact);}).sort((a,b)=>Number(normalize(b.n)===q)-Number(normalize(a.n)===q)||a.n.length-b.n.length||a.n.localeCompare(b.n)).slice(0,7-brands.length);
   matches=[...brands,...cars];active=-1;
   list.replaceChildren(...matches.map((r,i)=>{const el=document.createElement('button');el.type='button';el.id='header-result-'+i;el.setAttribute('role','option');el.setAttribute('aria-selected','false');el.tabIndex=-1;if(r.brand)el.dataset.searchBrand='';
    const title=document.createElement('b'),detail=document.createElement('span');title.textContent=r.n;detail.textContent=r.brand?'Explore the marque and its cars':r.b+' · Open car';el.append(title,detail);el.addEventListener('pointerdown',e=>e.preventDefault());el.addEventListener('click',()=>choose(i));return el;}));
   list.hidden=!matches.length;input.setAttribute('aria-expanded',String(!!matches.length));input.removeAttribute('aria-activedescendant');status.textContent=matches.length?matches.length+' suggestions. Use the arrow keys to choose.':'No suggestions. Press Search to explore the collection.';
  }catch{if(request===revision){close();status.textContent='Suggestions unavailable. Press Search to open the collection.';}}
 }
 input.addEventListener('input',()=>{++revision;clearTimeout(timer);if(normalize(input.value).length<2)close();else timer=setTimeout(update,130);});
 input.addEventListener('focus',update);input.addEventListener('blur',()=>{++revision;close();});
 input.addEventListener('keydown',e=>{if(e.key==='Escape'){++revision;close();return;}if(list.hidden)return;
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();active=active<0?(e.key==='ArrowDown'?0:matches.length-1):(active+(e.key==='ArrowDown'?1:-1)+matches.length)%matches.length;highlight();}
  if(e.key==='Enter'&&active>=0){e.preventDefault();choose(active);}
 });
 form.addEventListener('submit',async e=>{e.preventDefault();const q=normalize(input.value);if(!q){input.focus();return;}const fallback='/library/?'+new URLSearchParams({q:input.value.trim()});try{const data=index||await load();const brand=data.brands.find(r=>normalize(r.n)===q);location.assign(brand?brand.u:fallback);}catch{location.assign(fallback);}});
}
