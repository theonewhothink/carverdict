import unittest,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_dashboard_seo import audit
class SeoAuditTest(unittest.TestCase):
 def page(self,root,path,title='Distinct page',extra='',robots=''):
  dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);url='https://motorjury.com/'+path.removesuffix('index.html')
  dest.write_text(f'''<html lang="en"><head><title>{title}</title><meta name="description" content="{title} useful introduction"><meta name="robots" content="{robots}"><link rel="canonical" href="{url}"><meta property="og:title" content="{title}"><meta property="og:description" content="Intro"><meta property="og:url" content="{url}"><meta property="og:image" content="https://motorjury.com/photo.png"><script type="application/ld+json">{{"@type":"WebPage"}}</script>{extra}</head><body><h1>{title}</h1></body></html>''')
 def test_eligible_held_and_error_pages_are_distinct(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);self.page(p,'index.html');self.page(p,'reference/index.html',robots='noindex,follow');self.page(p,'404.html');(p/'sitemap.xml').write_text('<urlset><url><loc>https://motorjury.com/</loc></url></urlset>');(p/'robots.txt').write_text('User-agent: *\nAllow: /\n')
   result=audit(p);self.assertEqual(result['summary']['indexable_candidates'],1);self.assertEqual(result['summary']['noindex_pages'],1);self.assertEqual(result['issues'],[]);self.assertEqual(result['pages'][0]['indexing'],'Not verified');self.assertTrue(all(e['crawl_visits']=='Not connected' for e in result['engines']))
 def test_duplicate_and_malformed_metadata_cannot_get_a_clean_report(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);self.page(p,'index.html');self.page(p,'duplicate/index.html',extra='<script type="application/ld+json">bad json</script>');result=audit(p)
   self.assertEqual(result['summary']['duplicate_title_groups'],1);self.assertEqual(result['summary']['duplicate_description_groups'],1);self.assertTrue(any('Malformed structured data' in r['issues'] for r in result['issues']));self.assertTrue(any('Not present in generated sitemap' in r['issues'] for r in result['issues']))
if __name__=='__main__':unittest.main()
