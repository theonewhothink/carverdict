"""Public production evidence. Does not claim indexing, bot identity or field UX."""
import concurrent.futures,datetime,json,subprocess,tempfile,sys
from pathlib import Path
from urllib.parse import urlsplit,unquote,urljoin,quote
import xml.etree.ElementTree as ET
from audit_dashboard_seo import Head
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://motorjury.com'
def request(path,method='GET',headers=(),body=None):
 with tempfile.TemporaryDirectory() as d:
  hf=Path(d)/'headers';bf=Path(d)/'body'
  cmd=['curl','-sS','--max-time','30','--retry','1','-X',method,'-D',str(hf),'-o',str(bf),'-w','%{http_code}',ORIGIN+quote(path,safe='/%?=&:+')]
  for h in headers:cmd+=['-H',h]
  if body is not None:cmd+=['--data-binary',body]
  r=subprocess.run(cmd,capture_output=True,text=True)
  raw=hf.read_text() if hf.exists() else ''
  h={k.strip().lower():v.strip() for line in raw.splitlines() if ':' in line for k,v in [line.split(':',1)]}
  return int(r.stdout) if r.stdout.isdigit() else 0,h,bf.read_text(errors='replace') if bf.exists() else ''
def comparable_url(url):
 parts=urlsplit(url)
 return (parts.scheme,parts.netloc,unquote(parts.path),parts.query)
def sitemap_inventory(fetch=request,origin=ORIGIN):
 """Read same-origin sitemap indexes and XML URL sets, retaining every error."""
 pending=[origin+'/sitemap.xml'];visited=set();urls=set();documents=[];issues=[]
 while pending:
  url=pending.pop(0)
  if url in visited:continue
  if len(visited)>=30:issues.append('Sitemap document limit exceeded');break
  visited.add(url);parts=urlsplit(url)
  if (parts.scheme,parts.netloc)!=(urlsplit(origin).scheme,urlsplit(origin).netloc):
   issues.append('Off-origin sitemap was not fetched: '+url);continue
  status,_,text=fetch(parts.path+('?' + parts.query if parts.query else ''))
  documents.append({'url':url,'status':status})
  if status!=200:issues.append('Sitemap did not return HTTP 200: '+url);continue
  try:root=ET.fromstring(text)
  except ET.ParseError:issues.append('Malformed sitemap XML: '+url);continue
  kind=root.tag.rsplit('}',1)[-1]
  if kind not in ('sitemapindex','urlset'):issues.append('Unrecognised sitemap XML root: '+url);continue
  for entry in root:
   expected='sitemap' if kind=='sitemapindex' else 'url'
   if entry.tag.rsplit('}',1)[-1]!=expected:continue
   loc=next((child.text.strip() for child in entry if child.tag.rsplit('}',1)[-1]=='loc' and child.text),'')
   if not loc:issues.append('Missing sitemap location in '+url);continue
   if kind=='sitemapindex':pending.append(urljoin(url,loc))
   else:urls.add(loc)
 return {'urls':urls,'documents':documents,'issues':issues}
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
 sitemap=sitemap_inventory()
 published={comparable_url(u) for u in sitemap['urls']}
 expected={comparable_url(ORIGIN+r['path']) for r in inventory['pages']}
 missing=sorted(ORIGIN+r['path'] for r in inventory['pages'] if comparable_url(ORIGIN+r['path']) not in published)
 sitemap_check={'documents':sitemap['documents'],'urls':len(published),'missing_eligible_urls':missing,'unexpected_urls':sorted(u for u in sitemap['urls'] if comparable_url(u) not in expected),'issues':sitemap['issues'],'all_eligible_urls_present':not missing and not sitemap['issues']}
 failures=[r for r in pages+checks if r['issues']]
 if sitemap_check['unexpected_urls']:failures.append({'path':'/sitemap.xml','issues':['Live sitemap differs from release inventory; compare serving sources.']})
 if not sitemap_check['all_eligible_urls_present']:failures.append({'path':'/sitemap.xml','issues':['Eligible URL coverage incomplete']})
 report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Public HTTP delivery and release metadata only. No authenticated reader data, Google indexing, verified bot logs, field Core Web Vitals or AdSense approval are inferred.','pages':pages,'api_and_error_checks':checks,'sitemap':sitemap_check,'failures':failures}
 out=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/motorjury-live-release-audit.json');out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'pages':len(pages),'route_checks':len(checks),'failures':failures,'report':str(out)}));return bool(failures)
if __name__=='__main__':raise SystemExit(main())
