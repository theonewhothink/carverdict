"""Check final files, not the promises made by individual templates."""
import json
import html
import re
from collections import Counter
import sys
from pathlib import Path
from publication_policy import ROOT, verify


def verify_collection(site):
    from catalogue_experience import rows
    expected,_=rows()
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
    print(f"COLLECTION QA: all {len(actual):,} entries and {coverage['photo_references']:,} photo references retained; every static directory row and destination verified")


def main():
    site=ROOT/'site';verify(site);verify_collection(site)
    pages=list(site.rglob('*.html'));dead=set()
    for f in pages:
        text=f.read_text()
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
