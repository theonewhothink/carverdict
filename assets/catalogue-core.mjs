export function normalize(value='') {return String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();}
export function filterCars(rows,{query='',brand='',era='',photos=false,sort='featured'}={}) {
 const tokens=normalize(query).split(' ').filter(Boolean);
 const flat=normalize(query).replaceAll(' ','');
 const result=rows.filter(r=>{const text=normalize(r.n+' '+r.b);return (tokens.every(t=>text.includes(t))||text.replaceAll(' ','').includes(flat))&&(!brand||r.b===brand)&&(!photos||!!r.p)&&(!era||(r.y&&Math.floor(Number(r.y)/10)*10===Number(era)));});
 return result.sort((a,b)=>sort==='oldest'?(Number(a.y)||9999)-(Number(b.y)||9999)||a.n.localeCompare(b.n):sort==='name'?a.n.localeCompare(b.n):Number(!!b.p)-Number(!!a.p)||a.n.localeCompare(b.n));
}
export function modelLink(row){return row.u.startsWith('/library/')?row.u:'/library/';}

export function suggestCars(rows,query,limit=8){
 const q=normalize(query),compact=q.replace(/ /g,''),tokens=q.split(' ').filter(Boolean);
 if(q.length<2)return [];
 const scored=rows.map(r=>{const name=normalize(r.n),brand=normalize(r.b),flat=name.replace(/ /g,'');
  if(!tokens.every(t=>(name+' '+brand).includes(t))&&!flat.includes(compact))return null;
  const score=(name===q||flat===compact?100:0)+(name.startsWith(q)?30:0)+(brand.startsWith(q)?15:0)+(r.p?2:0)+(Number.isInteger(r.f)?Math.max(0,16-r.f):0);
  return {r,score};}).filter(Boolean).sort((a,b)=>b.score-a.score||a.r.n.length-b.r.n.length||a.r.n.localeCompare(b.r.n));
 const seen=new Set();return scored.filter(({r})=>{if(seen.has(r.u))return false;seen.add(r.u);return true;}).slice(0,limit).map(x=>x.r);
}
export function photoUrl(row){
 if(row.e==='unavailable'||!row.p)return '';
 if(row.it||row.t)return row.it||row.t;
 const file=encodeURIComponent(row.p.replace(/ /g,'_'));
 if(/^[a-f0-9]{2}$/.test(row.h||''))return `https://thumb.wikimedia.org/wikipedia/commons/thumb/${row.h[0]}/${row.h}/${file}/960px-${file}`;
 return 'https://commons.wikimedia.org/wiki/Special:FilePath/'+file+'?width=960';
}
