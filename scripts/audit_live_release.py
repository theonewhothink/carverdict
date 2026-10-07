"""Public production evidence. Does not claim indexing, bot identity or field UX."""
import concurrent.futures,datetime,json,subprocess,tempfile,sys
from pathlib import Path
from audit_dashboard_seo import Head
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://motorjury.com'
def request(path,method='GET',headers=(),body=None):
 with tempfile.TemporaryDirectory() as d:
  hf=Path(d)/'headers';bf=Path(d)/'body'
  cmd=['curl','-sS','--max-time','30','--retry','1','-X',method,'-D',str(hf),'-o',str(bf),'-w','%{http_code}',ORIGIN+path]
  for h in headers:cmd+=['-H',h]
  if body is not None:cmd+=['--data-binary',body]
  r=subprocess.run(cmd,capture_output=True,text=True)
  raw=hf.read_text() if hf.exists() else ''
  h={k.strip().lower():v.strip() for line in raw.splitlines() if ':' in line for k,v in [line.split(':',1)]}
  return int(r.stdout) if r.stdout.isdigit() else 0,h,bf.read_text(errors='replace') if bf.exists() else ''
def page(row):
 path=row['path'];status,headers,text=request(path);h=Head();h.feed(text);issues=[]
 if status!=200:issues.append('Expected HTTP 200')
 if h.canonical!=ORIGIN+path:issues.append('Canonical mismatch')
 if 'noindex' in h.robots or 'noindex' in headers.get('x-robots-tag',''):issues.append('Unexpected noindex on eligible page')
 if h.title.strip()!=row['title']:issues.append('Title differs from release inventory')
 for name in ('strict-transport-security','content-security-policy','x-content-type-options','permissions-policy'):
  if not headers.get(name):issues.append('Missing '+name)
 return {'path':path,'status':status,'issues':issues}
def main():
 inventory=json.loads((ROOT/'workers/dashboard-seo.json').read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:pages=list(pool.map(page,inventory['pages']))
 checks=[]
 cases=[('/api/auth/logout','GET',(),None,405),('/api/prefs','GET',(),None,405),('/api/love','DELETE',(),None,405),('/api/subscribe','POST',('Origin: https://foreign.example','Content-Type: application/json'),'{}',403),('/api/prefs','POST',('Origin: https://motorjury.com','Content-Type: application/json'),'{',400),('/api/prefs','POST',('Origin: https://motorjury.com','Content-Type: text/plain'),'{}',415),('/api/auth/me','GET',('Cookie: mj_session=%ZZ',),None,200),('/api/auth/me','GET',(),None,200),('/dashboard','GET',(),None,200),('/api/dashboard/data','GET',(),None,401),('/cars/toyota/no-such-car-release-check/','GET',(),None,404)]
 for path,method,headers,body,expected in cases:
  status,h,_=request(path,method,headers,body)
  private=path.startswith('/api/') or path=='/dashboard'
  issues=[]
  if status!=expected:issues.append('Expected HTTP '+str(expected))
  if private and 'no-store' not in h.get('cache-control',''):issues.append('Private route lacks no-store')
  checks.append({'path':path,'method':method,'status':status,'issues':issues})
 status,_,sitemap=request('/sitemap.xml')
 sitemap_check={'status':status,'all_eligible_urls_present':status==200 and all(ORIGIN+r['path'] in sitemap for r in inventory['pages'])}
 failures=[r for r in pages+checks if r['issues']]
 if not sitemap_check['all_eligible_urls_present']:failures.append({'path':'/sitemap.xml','issues':['Eligible URL coverage incomplete']})
 report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Public HTTP delivery and release metadata only. No authenticated reader data, Google indexing, verified bot logs, field Core Web Vitals or AdSense approval are inferred.','pages':pages,'api_and_error_checks':checks,'sitemap':sitemap_check,'failures':failures}
 out=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/motorjury-live-release-audit.json');out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'pages':len(pages),'route_checks':len(checks),'failures':failures,'report':str(out)}));return bool(failures)
if __name__=='__main__':raise SystemExit(main())
