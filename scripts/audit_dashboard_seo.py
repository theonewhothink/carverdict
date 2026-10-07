"""A reproducible build inventory, never a claim of Google indexing or crawler visits."""
import datetime,json,os,collections,re
from html.parser import HTMLParser
from pathlib import Path
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent.parent
class Head(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.title='';self.in_title=False;self.description='';self.robots='';self.canonical='';self.h1=0;self.og=set();self.ld=[];self.in_ld=False;self.buffer='';self.images=0;self.alt_missing=0;self.lang=''
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='html':self.lang=a.get('lang','')
  if t=='title':self.in_title=True
  if t=='h1':self.h1+=1
  if t=='meta':
   n=a.get('name','').lower();p=a.get('property','')
   if n=='description':self.description=a.get('content','')
   if n=='robots':self.robots=a.get('content','').lower()
   if p.startswith('og:') and a.get('content'):self.og.add(p)
  if t=='link' and a.get('rel')=='canonical':self.canonical=a.get('href','')
  if t=='script' and a.get('type')=='application/ld+json':self.in_ld=True;self.buffer=''
  if t=='img':self.images+=1;self.alt_missing+=int('alt' not in a)
 def handle_endtag(self,t):
  if t=='title':self.in_title=False
  if t=='script' and self.in_ld:self.ld.append(self.buffer);self.in_ld=False
 def handle_data(self,d):
  if self.in_title:self.title+=d
  if self.in_ld:self.buffer+=d

def audit(site=ROOT/'site',origin=None):
 origin=(origin or os.environ.get('SITE_ORIGIN','https://motorjury.com')).rstrip('/')
 sitemap=set();xml_failures=[]
 for f in site.glob('sitemap*.xml'):
  try:
   root=ET.fromstring(f.read_text());sitemap.update(n.text for u in root if u.tag.endswith('url') for n in u if n.tag.endswith('loc') and n.text)
  except ET.ParseError:xml_failures.append(f.name)
 pages=[];issues=[];total=0;held=0;error_pages=0;titles=collections.defaultdict(list);descs=collections.defaultdict(list)
 for f in sorted(site.rglob('*.html')):
  total+=1
  if f.relative_to(site).as_posix()=='404.html':error_pages+=1;continue
  path='/'+f.relative_to(site).as_posix().removesuffix('index.html');text=f.read_text()
  if re.search(r'<meta\b[^>]*name=[\"\']robots[\"\'][^>]*content=[\"\'][^\"\']*noindex',text[:16000],re.I):held+=1;continue
  h=Head();h.feed(text)
  if 'noindex' in h.robots:held+=1;continue
  flags=[]
  if h.canonical!=origin+path:flags.append('Canonical differs from generated route')
  if not h.title.strip():flags.append('Missing title')
  if not h.description.strip():flags.append('Missing description')
  if h.h1!=1:flags.append('Expected exactly one main heading')
  if not {'og:title','og:description','og:url','og:image'}<=h.og:flags.append('Incomplete social preview metadata')
  if origin+path not in sitemap:flags.append('Not present in generated sitemap')
  if h.alt_missing:flags.append('Image missing alt attribute')
  schema_types=[]
  for s in h.ld:
   try:
    value=json.loads(s);values=value if isinstance(value,list) else value.get('@graph',[value]) if isinstance(value,dict) else []
    for obj in values:
     typ=obj.get('@type',[]) if isinstance(obj,dict) else []
     schema_types.extend(typ if isinstance(typ,list) else [typ])
   except (ValueError,AttributeError):flags.append('Malformed structured data')
  if not h.ld:flags.append('No structured data; assess relevance')
  titles[h.title.strip()].append(path);descs[h.description.strip()].append(path)
  row={'path':path,'canonical':h.canonical,'title':h.title.strip(),'description':h.description.strip(),'language':h.lang,'schema_types':schema_types,'issues':flags,'status':'needs_review' if flags else 'technical_checks_pass','indexing':'Not verified','submitted':'Not recorded'};pages.append(row)
  if flags:issues.append({'path':path,'issues':flags})
 duplicate_titles=[p for title,p in titles.items() if title and len(p)>1];duplicate_descriptions=[p for desc,p in descs.items() if desc and len(p)>1]
 rb=RobotFileParser();raw=(site/'robots.txt').read_text() if (site/'robots.txt').exists() else '';rb.parse(raw.splitlines())
 bots=[('Google','Googlebot'),('Bing / Copilot','bingbot'),('ChatGPT search','OAI-SearchBot'),('Claude search','Claude-SearchBot'),('Perplexity','PerplexityBot')]
 engines=[{'name':name,'agent':agent,'robots_home_allowed':rb.can_fetch(agent,origin+'/') if raw else None,'waf_delivery':'Not independently verified','crawl_visits':'Not connected','index_or_citations':'Not connected','ownership_or_submission':'Not verified'} for name,agent in bots]
 queue=sorted(pages,key=lambda r:(not r['path'].startswith('/guides/'),r['path']))
 return {'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'preview_isolated':os.environ.get('MOTORJURY_PREVIEW')=='1','scope':'Generated files in this build. Not an index report, live WAF test or verified crawler log.','summary':{'html_pages':total,'indexable_candidates':len(pages),'noindex_pages':held,'excluded_error_pages':error_pages,'sitemap_urls':len(sitemap),'pages_needing_review':len(issues),'duplicate_title_groups':len(duplicate_titles),'duplicate_description_groups':len(duplicate_descriptions)},'issues':issues,'duplicate_titles':duplicate_titles,'duplicate_descriptions':duplicate_descriptions,'xml_errors':xml_failures,'pages':pages,'engines':engines,'indexing_queue':queue[:10],'remaining_checks':['Validate relevant schema with official tools and confirm that markup matches visible content.','Verify console ownership, sitemap acceptance, indexed counts and URL inspection evidence.','Check CDN/WAF access against official crawler addresses; record actual verified visits.','Measure mobile field performance; asset HEAD timings are not Core Web Vitals.','Verify translations, photo identity/licensing, editorial expertise and reader outcomes.']}
if __name__=='__main__':
 result=audit();(ROOT/'workers/dashboard-seo.json').write_text(json.dumps(result,ensure_ascii=False)+'\n');print('Dashboard SEO inventory:',result['summary'])
