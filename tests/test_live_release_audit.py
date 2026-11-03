import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_live_release import sitemap_inventory,comparable_url
class LiveReleaseAudit(unittest.TestCase):
 def fetcher(self,files):
  calls=[]
  def fetch(path):calls.append(path);return files.get(path,(404,{},''))
  return fetch,calls
 def test_xml_index_is_followed_and_utf8_locations_compare_correctly(self):
  f,calls=self.fetcher({'/sitemap.xml':(200,{},'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://motorjury.com/sitemap-0.xml</loc></sitemap></sitemapindex>'),'/sitemap-0.xml':(200,{},'<urlset><url><loc>https://motorjury.com/library/citro%C3%ABn/</loc></url><url><loc>https://motorjury.com/guides/?x=1&amp;y=2</loc></url></urlset>')})
  result=sitemap_inventory(f)
  self.assertEqual(calls,['/sitemap.xml','/sitemap-0.xml']);self.assertFalse(result['issues']);self.assertEqual(len(result['urls']),2)
  self.assertIn(comparable_url('https://motorjury.com/library/citroën/'),{comparable_url(u) for u in result['urls']})
 def test_failed_child_is_not_hidden_by_a_healthy_root(self):
  f,_=self.fetcher({'/sitemap.xml':(200,{},'<sitemapindex><sitemap><loc>https://motorjury.com/missing.xml</loc></sitemap></sitemapindex>')})
  result=sitemap_inventory(f);self.assertTrue(result['issues']);self.assertEqual(result['documents'][-1]['status'],404)
 def test_external_children_are_not_fetched_and_loops_are_bounded(self):
  f,calls=self.fetcher({'/sitemap.xml':(200,{},'<sitemapindex><sitemap><loc>https://motorjury.com/sitemap.xml</loc></sitemap><sitemap><loc>https://other.example/sitemap.xml</loc></sitemap></sitemapindex>')})
  result=sitemap_inventory(f);self.assertEqual(calls,['/sitemap.xml']);self.assertTrue(result['issues'])
 def test_malformed_and_missing_locations_remain_findings(self):
  for text in ['<urlset>','<urlset><url/></urlset>','<html/>']:
   f,_=self.fetcher({'/sitemap.xml':(200,{},text)});self.assertTrue(sitemap_inventory(f)['issues'])
