import json,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import reader_guides
NEW=('used-car-ownership-budget','hybrid-fuel-break-even','match-car-version-before-you-buy','recall-check-to-dealer-record','car-design-timeline','compare-car-design-briefs')
class GuideExpansion(unittest.TestCase):
 def test_routes_metadata_sources_and_related_destinations_are_complete(self):
  pages={}
  reader_guides.main(lambda path,title,body,**meta:pages.update({path:(title,body,meta)}))
  policy=json.loads((ROOT/'data/publication_policy.json').read_text())
  for slug in NEW:
   path='/guides/'+slug+'/';title,body,meta=pages[path]
   self.assertIn(path,policy['index_pages'])
   self.assertIn('guide-visual',body)
   self.assertIn('10 November 2026',body)
   article=meta['jsonld'][0]
   self.assertEqual(article['url'],'https://motorjury.com'+path)
   self.assertTrue(any(x.startswith('https://') and not x.startswith('https://motorjury.com') for x in article['citation']))
   for target in re.findall(r'href="(/guides/[^"]+)"',body):
    self.assertIn(target,pages,target)
  self.assertEqual(len(pages),len(reader_guides.SLUGS)+1)
  self.assertFalse(policy['ads_enabled'])
 def test_dynamic_tools_have_named_units_required_inputs_and_non_javascript_fallback(self):
  for slug in NEW[:2]:
   body=reader_guides.visual(slug)
   self.assertIn('<noscript>',body)
   self.assertIn('aria-live="polite"',body)
   self.assertIn('US MPG',body)
   self.assertIn('US gallon',body)
   self.assertIn(' required',body)
