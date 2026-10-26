import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from search_presence import build_sources, machine_guide, page_entities
import build_buying_brief


class SearchPresenceTest(unittest.TestCase):
    def test_site_publisher_and_article_share_stable_identities(self):
        source = {'@type': 'Article', 'headline': 'A sourced answer',
                  'author': {'@type': 'Organization', 'name': 'MotorJury'},
                  'dateModified': '2026-10-06', 'citation': ['https://www.nhtsa.gov/recalls']}
        graph = page_entities('Title', 'Description', '/guides/example/', [source])
        by_type = {node['@type']: node for node in graph}
        self.assertEqual(by_type['Article']['publisher']['@id'], by_type['Organization']['@id'])
        self.assertEqual(by_type['WebPage']['isPartOf']['@id'], by_type['WebSite']['@id'])
        self.assertEqual(by_type['Article']['dateModified'], source['dateModified'])
        self.assertEqual(by_type['Article']['citation'], source['citation'])
        self.assertNotIn('datePublished', by_type['Article'])
        self.assertNotIn('@id', source)
        self.assertNotIn('sameAs', by_type['Organization'])

    def test_modern_shell_has_working_asset_path_and_parseable_schema(self):
        with patch.object(build_buying_brief, 'shell_assets', return_value=('', '/assets/genius.js')), \
             patch('collection_stories.asset_script', return_value=''):
            rendered = build_buying_brief.shell('Cars <and> sources', '/', '<h1>Cars</h1>')
        self.assertIn('content="https://motorjury.com/og/default.png"', rendered)
        self.assertNotIn('/assets/og/default.png', rendered)
        blocks = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', rendered)]
        self.assertEqual(sum(x['@type'] == 'WebSite' for x in blocks), 1)
        self.assertIn('href="/sources/"', rendered)
        self.assertIn('href="/about/"', rendered)

    def test_unmatched_snapshot_does_not_become_zero_or_a_fresh_review(self):
        record = {'make': 'TEST', 'model': 'Example', 'year': 2020,
                  'checks': {'complaints': {'status': 'unmatched', 'count': 0, 'checked_at': '2026-10-06', 'urls': []},
                             'recalls': {'status': 'empty', 'count': 0, 'checked_at': '2026-10-07', 'urls': []}}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'data').mkdir()
            (root / 'data/pilot_records.json').write_text(json.dumps({'records': [record]}))
            (root / 'data/collection_profiles.json').write_text(json.dumps({'profiles': []}))
            written = []
            build_sources(lambda *args, **kwargs: written.append((args, kwargs)), root=root)
            body = written[0][0][2]
            self.assertIn('<td>Unavailable<br>', body)
            self.assertIn('<td>0<br>', body)
            self.assertIn('Checked 2026-10-06', body)
            export = json.loads((root / 'site/assets/motorjury-evidence.json').read_text())
            self.assertEqual(export['records'], [record])
            self.assertIn('not a representative reliability study', export['scope'])
            self.assertIn('recommendations are suspended', (root / 'site/llms.txt').read_text())

    def test_machine_guide_references_current_reviewed_material(self):
        guide = machine_guide()
        self.assertIn('https://motorjury.com/sources/', guide)
        self.assertIn('not failure rates', guide)
        self.assertIn('not a new source review', guide)
        self.assertNotIn('computed reliability scores', guide)


if __name__ == '__main__':
    unittest.main()
