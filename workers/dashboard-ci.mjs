// A nightly ingestion run or another commit cannot certify this deployed source.
export async function servingCI(sha, request=fetch) {
 const base={status:'unavailable',sha,url:'https://github.com/theonewhothink/carverdict/actions',checked_at:new Date().toISOString()};
 if(!/^[a-f0-9]{40}$/.test(sha||''))return {...base,note:'Serving source is unknown; no CI result can be matched.'};
 const endpoint='https://api.github.com/repos/theonewhothink/carverdict/commits/'+sha+'/check-runs?per_page=100';
 try{
  const response=await request(endpoint,{headers:{'User-Agent':'MotorJury-dashboard','Accept':'application/vnd.github+json'},signal:AbortSignal.timeout(5000)});
  if(!response.ok)return {...base,note:'GitHub returned HTTP '+response.status+'; CI is unverified.'};
  const data=await response.json();
  if(!Array.isArray(data.check_runs))return {...base,note:'GitHub returned no usable check list.'};
  const runs=data.check_runs.filter(r=>r.name==='build-deploy'&&r.head_sha===sha).sort((a,b)=>Date.parse(b.started_at||0)-Date.parse(a.started_at||0));
  const run=runs[0];
  if(!run)return {...base,status:'not_run',note:'No build-deploy check exists for this source. Nightly ingestion and hosting checks are separate.'};
  const url=typeof run.html_url==='string'&&run.html_url.startsWith('https://github.com/theonewhothink/carverdict/')?run.html_url:base.url;
  return {...base,status:run.status==='completed'?(run.conclusion||'unavailable'):run.status,url,created_at:run.started_at,note:'Exact serving commit; build-deploy check only.'};
 }catch{return {...base,note:'GitHub check lookup failed; no successful CI result is inferred.'};}
}
