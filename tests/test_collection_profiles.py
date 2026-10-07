import unittest,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collection_stories import PROFILES,story
R=Path(__file__).resolve().parent.parent
class Profiles(unittest.TestCase):
    def test_later_photographs_do_not_inherit_original_car_specs(self):
        for name in ('Mazda MX-5','BMW M3','Honda NSX'):
            p=PROFILES[name]
            self.assertIn('not the original',p['photo'])
            self.assertIn('introduced',p['scope'])
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
