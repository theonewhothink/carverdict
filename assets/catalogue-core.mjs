export function normalize(value='') {return String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();}
export function filterCars(rows,{query='',brand='',era='',photos=false,sort='featured'}={}) {
 const tokens=normalize(query).split(' ').filter(Boolean);
 const result=rows.filter(r=>tokens.every(t=>normalize(r.n+' '+r.b).includes(t))&&(!brand||r.b===brand)&&(!photos||!!r.p)&&(!era||(r.y&&Math.floor(Number(r.y)/10)*10===Number(era))));
 return result.sort((a,b)=>sort==='oldest'?(Number(a.y)||9999)-(Number(b.y)||9999)||a.n.localeCompare(b.n):sort==='name'?a.n.localeCompare(b.n):Number(!!b.p)-Number(!!a.p)||a.n.localeCompare(b.n));
}
export function modelLink(row){return row.u.startsWith('/library/')?row.u:'/library/';}
