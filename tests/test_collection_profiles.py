import unittest,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collection_stories import PROFILES,story
R=Path(__file__).resolve().parent.parent
class Profiles(unittest.TestCase):
    def test_scoped_illustrations_have_licences_and_do_not_replace_catalogue_references(self):
        credits=json.loads((R/'data/photo_credits.json').read_text())
        raw=json.loads((R/'data/car_library.json').read_text())
        for name,generation in (('Mazda MX-5','NA'),('BMW M3','E30'),('Honda NSX','NA1')):
            p=PROFILES[name]
            self.assertIn(generation,p['illustration'])
            self.assertIn('not verified',p['photo'])
            self.assertIn('introduced',p['scope'])
            self.assertTrue(credits[p['illustration']]['author'])
            self.assertTrue(credits[p['illustration']]['licence_url'])
            self.assertTrue(any(r['n']==name and r['p'] and r['p']!=p['illustration'] for r in raw))
    def test_research_is_explicit_and_unknown_entries_have_no_invented_story(self):
        self.assertEqual(story('Imaginary car'),'')
        for name,p in PROFILES.items():
            self.assertGreaterEqual(len(p['sources']),2)
            self.assertIn('not road-test findings',story(name))
            self.assertNotIn('wikipedia',story(name).lower())
            self.assertTrue(all(u.startswith('https://') for _,u,_ in p['sources']))
    def test_every_profile_is_an_intended_canonical_search_destination(self):
        policy=json.loads((R/'data/publication_policy.json').read_text())
        index=json.loads((R/'data/model_index.json').read_text())
        for name in PROFILES:
            paths=['/library/'+brand+'/'+model+'/' for brand,models in index.items() for n,model in models.items() if n==name]
            self.assertEqual(len(paths),1)
            self.assertIn(paths[0],policy['index_pages'])

    def test_responsive_photos_use_supported_thumbnail_steps(self):
        from catalogue_experience import image
        html=image('Ferrari_F40_7.jpg','Ferrari F40')
        self.assertIn('/330px-',html)
        self.assertIn('330w',html)
        self.assertNotIn('/320px-',html)
        self.assertIn('/960px-',html)
