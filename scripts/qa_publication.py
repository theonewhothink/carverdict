"""Check final files, not the promises made by individual templates."""
import json
import html
import re
from collections import Counter
import sys
from html.parser import HTMLParser
from pathlib import Path
from publication_policy import ROOT, verify

class ReaderReferences(HTMLParser):
    def __init__(self):
        super().__init__();self.hidden=0;self.text=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if tag=='a':self.links.append(dict(attrs).get('href',''))
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,text):
        if not self.hidden:self.text.append(text)

def verify_reader_references(text,url):
    if url.strip('/').split('/')[-1:] == ['terms']:return
    parser=ReaderReferences();parser.feed(text)
    if re.search(r'\bwikipedia\b',' '.join(parser.text),re.I) or any(re.search(r'https?://[^/]*wikipedia\.org(?:/|$)',link,re.I) for link in parser.links):
        raise ValueError('Retired encyclopedia text or link: '+url)


def verify_collection(site):
    from catalogue_experience import rows
    expected,_=rows()
    again,_=rows()
    if expected!=again:raise ValueError('Catalogue generation mutates its own input')
    additions=json.loads((ROOT/'data/photo_additions.json').read_text())
    credits=json.loads((ROOT/'data/photo_credits.json').read_text())
    for entry in additions.values():
        credit=credits.get(entry['filename'],{})
        if not all(credit.get(k) for k in ('author','licence','licence_url','thumb','checked_at')):raise ValueError('Recovered photograph lacks checked attribution')
    actual=json.loads((site/'assets/catalogue-data.json').read_text())
    if actual != expected:raise ValueError('Search omitted or changed catalogue records')
    coverage=json.loads((site/'assets/catalogue-coverage.json').read_text())
    directory=[]
    for page in (site/'all-cars').rglob('index.html'):
        content=page.read_text()
        block=re.search(r'<ol class="car-directory"[^>]*>(.*?)</ol>',content,re.S)
        if not block:raise ValueError('Directory page has no accessible roster')
        directory.extend((html.unescape(n),html.unescape(b)) for n,b in re.findall(r'<b>(.*?)</b><span>(.*?)</span>',block.group(1),re.S))
    if Counter(directory)!=Counter((r['n'],r['b']) for r in expected):
        raise ValueError('Static A-Z directory omitted or duplicated entries')
    anchors={}
    for row in actual:
        url,_,fragment=row['u'].partition('#');path=site/url.strip('/')/'index.html'
        if not path.exists():raise ValueError('Catalogue destination missing: '+row['u'])
        if fragment:
            if path not in anchors:anchors[path]=set(re.findall(r'id="([^"]+)"',path.read_text()))
            if fragment not in anchors[path]:raise ValueError('Catalogue roster anchor missing: '+row['u'])
    if coverage['distinct_entries']!=len(actual) or coverage['photo_references']!=sum(bool(r['p']) for r in actual):raise ValueError('Coverage totals do not match available records')
    from collection_stories import PROFILES
    for name,profile in PROFILES.items():
        row=next(r for r in actual if r['n']==name)
        content=(site/row['u'].strip('/')/'index.html').read_text()
        if 'data-reviewed-profile' not in content or html.escape(profile['photo']) not in content:
            raise ValueError('Missing profile or photo-generation scope: '+name)
        if any(html.escape(url,quote=True) not in content for _,url,_ in profile['sources']):
            raise ValueError('Profile lost a primary source: '+name)
    model_pages=[p for p in (site/'library').glob('*/*/index.html')]
    if len(model_pages)!=6500:raise ValueError('Standalone model coverage changed')
    for p in model_pages:
        content=p.read_text()
        if 'data-save-car=' not in content or 'data-love=' not in content or 'data-survey=' not in content:
            raise ValueError('Model lost saving or community controls: '+str(p))
        if 'Assembled by' in content or 'Wikipedia (CC BY-SA)' in content:
            raise ValueError('Retired encyclopedia byline returned: '+str(p))
    assistant=json.loads((site/'assets/genius-pages.json').read_text())
    for name in PROFILES:
        row=next(r for r in actual if r['n']==name)
        page=next((p for p in assistant if p['url']==row['u']),None)
        if not page or PROFILES[name]['scope'] not in page.get('text','') or PROFILES[name]['sources'][0][1] not in page.get('text',''):
            raise ValueError('Assistant reference lost version scope or sources: '+name)
    print(f'STORY QA: six sourced profiles; all {len(model_pages)} model pages retain saving and community controls')
    print(f"COLLECTION QA: all {len(actual):,} entries and {coverage['photo_references']:,} photo references retained; every static directory row and destination verified")


def main():
    site=ROOT/'site';verify(site);verify_collection(site)
    pages=list(site.rglob('*.html'));dead=set()
    for f in pages:
        text=f.read_text()
        url='/'+f.relative_to(site).as_posix().removesuffix('index.html')
        verify_reader_references(text,url)
        if 'data-buying-product' in text and text.count('src="/assets/genius.js')!=1:raise ValueError('Modern page lost or duplicated its chat: '+url)
        for match in re.finditer(r'''(?:href|src)=["'](/[^"'#?]*)''',text):
            url=match.group(1)
            if url.startswith(('/api','/cdn-cgi')):continue
            if not (site/url.lstrip('/')).exists() and not (site/url.lstrip('/')/'index.html').exists():dead.add(url)
    if dead: raise ValueError('Broken links or assets: '+', '.join(sorted(dead)[:20]))
    legacy = json.loads((ROOT/'data'/'legacy_routes.json').read_text())['routes']
    missing = [url for url in legacy if not (site/url.strip('/')/'index.html').exists()]
    if missing: raise ValueError('Published routes lost: '+', '.join(missing[:20]))
    ratings=json.loads((site/'assets'/'genius-cars.json').read_text())
    if any(r.get('score') is not None or r.get('verdict') in ('BUY','CAUTION','AVOID') for r in ratings):
        raise ValueError('Assistant index contains suspended predictive ratings')
    if sum(1 for f in site.rglob('*') if f.is_file())>19800:raise ValueError('Static-asset cap exceeded')
    paragraphs=[]
    for f in (site/'guides').glob('*/index.html'):
        text=f.read_text()
        if 'data-editorial-hold' in text:continue
        article=re.search(r'<article\b[^>]*>(.*?)</article>',text,re.S)
        if article:
            paragraphs.extend(re.sub(r'<[^>]+>','',x).strip() for x in re.findall(r'<p\b[^>]*>(.*?)</p>',article.group(1),re.S) if len(re.sub(r'<[^>]+>','',x).strip())>120)
    repeated=Counter(paragraphs)
    duplicate_share=sum(1 for p in paragraphs if repeated[p]>1)/max(1,len(paragraphs))
    if duplicate_share>=0.15:raise ValueError('Reviewed editorial duplicate-paragraph budget exceeded')
    print(f'EDITORIAL QA: {len(paragraphs)} substantive paragraphs, {duplicate_share:.1%} repeated; held utility pages excluded')
    print(f'PUBLICATION QA: {len(pages)} pages; no unapproved ads, broken destinations or predictive ratings')
    print(f'MIGRATION QA: all {len(legacy)} baseline sitemap routes retained')


if __name__=='__main__':main()
