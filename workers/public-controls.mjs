// Public account writes use browser origin checks; provider callbacks have their own
// signed state / double-submit protection and must remain separate from this policy.
export const PUBLIC_METHODS = {
  '/api/auth/providers':['GET'], '/api/vin':['GET'],
  '/api/auth/signup':['POST'], '/api/auth/login':['POST'], '/api/auth/logout':['POST'],
  '/api/auth/me':['GET'], '/api/prefs':['POST'], '/api/love':['GET','POST'],
  '/api/most-loved':['GET'], '/api/survey':['GET','POST'], '/api/subscribe':['POST'],
  '/api/stats':['GET'], '/api/auth/google':['GET'], '/api/auth/apple':['GET'],
  '/api/auth/google/callback':['GET'], '/api/auth/apple/callback':['GET','POST'],
  '/api/auth/google/token':['POST'],
};
export function accountWriteAllowed(req, origin) {
  return req.headers.get('Origin') === origin &&
    !['cross-site','same-site'].includes(req.headers.get('Sec-Fetch-Site'));
}
export async function boundedJson(req, maxBytes=131072) {
  if (Number(req.headers.get('Content-Length')) > maxBytes) throw Object.assign(new Error('Request is too large.'),{status:413});
  const reader=req.body?.getReader(); const chunks=[]; let size=0;
  if (reader) {
    try { for (;;) {
      const {done,value}=await reader.read(); if(done) break;
      size+=value.byteLength;
      if(size>maxBytes) { await reader.cancel(); throw Object.assign(new Error('Request is too large.'),{status:413}); }
      chunks.push(value);
    }} finally {reader.releaseLock();}
  }
  const bytes=new Uint8Array(size); let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
  let value;
  try {value=JSON.parse(new TextDecoder().decode(bytes));}
  catch {throw Object.assign(new Error('Send a valid JSON object.'),{status:400});}
  if(!value || Array.isArray(value) || typeof value!=='object') throw Object.assign(new Error('Send a valid JSON object.'),{status:400});
  return value;
}
export function localLink(value) {
  if(typeof value!=='string' || !/^\/(?!\/)/.test(value) || /[\\\u0000-\u0020]/.test(value)) return '/';
  try {const u=new URL(value,'https://motorjury.com'); return u.origin==='https://motorjury.com' ? u.pathname+u.search+u.hash : '/';}
  catch{return '/';}
}
export function preferences(value={}) {
  if(!value || Array.isArray(value) || typeof value!=='object') throw new Error('Preferences must be an object.');
  const text=JSON.stringify(value);
  if(text.length>100000) throw new Error('Preferences are too large.');
  // Reject prototype keys at every level; JSON is otherwise reader-owned workspace data.
  JSON.parse(text,(key,v)=>{if(['__proto__','constructor','prototype'].includes(key)) throw new Error('Invalid preference key.'); return v;});
  return value;
}
export function ownerAnswer(b) {
  if (b.owned !== true) throw new Error("Confirm that you have owned this car before sharing an owner response.");
  const integer=(key,lo,hi)=>{
    const v=b[key]; const n=typeof v==='number' || (typeof v==='string' && /^\d+$/.test(v)) ? Number(v) : NaN;
    if(!Number.isInteger(n) || n<lo || n>hi) throw new Error(key==='years_owned' ? 'Enter whole years owned, from 0 to 40.' : 'Choose each rating from 1 to 5.');
    return n;
  };
  if(typeof b.would_buy_again!=='boolean') throw new Error('Answer whether you would buy it again.');
  return {overall:integer('overall',1,5),reliability:integer('reliability',1,5),running_cost:integer('running_cost',1,5),years_owned:integer('years_owned',0,40),would_buy_again:b.would_buy_again ? 1 : 0};
}
