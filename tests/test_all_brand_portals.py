"""Protect the full catalogue while scaling the Porsche presentation."""
import html
import json
import re
import sys
import unittest
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from all_brand_portals import media_records, photographs
from prepare_brand_media import selected_rows


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.models = [], [], []
        self.headings = 0
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'h1':
            self.headings += 1
        if 'data-model-name' in attrs:
            self.models.append(attrs['data-model-name'])


class AllBrandPortals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / 'site/assets/catalogue-data.json').read_text())
        cls.manifest = json.loads((ROOT / 'site/assets/brand-portals.json').read_text())
        cls.groups = defaultdict(list)
        for row in cls.rows:
            cls.groups[row['b']].append(row)

    def test_every_brand_retains_its_complete_exact_identity_roster(self):
        self.assertEqual({x['brand'] for x in self.manifest}, set(self.groups))
        self.assertEqual(len({x['path'] for x in self.manifest}), len(self.groups))
        self.assertEqual(sum(x['entries'] for x in self.manifest), len(self.rows))
        for record in self.manifest:
            text = (ROOT / 'site' / record['path'].strip('/') / 'index.html').read_text()
            page = Page(text)
            self.assertEqual(page.headings, 1, record['brand'])
            self.assertEqual(len(page.ids), len(set(page.ids)), record['brand'])
            self.assertCountEqual(page.models, [x['n'] for x in self.groups[record['brand']]], record['brand'])
            self.assertIn('data-brand-portal', text)
            for row in self.groups[record['brand']]:
                self.assertIn(row['u'], page.links, row['n'])
                if '#' in row['u']:
                    self.assertIn(row['u'].split('#', 1)[1], page.ids)
            for url in page.links:
                if url.startswith('#'):
                    self.assertIn(url[1:], page.ids, (record['brand'], url))

    def test_reference_portals_keep_the_existing_indexing_hold(self):
        for record in self.manifest:
            if record['brand'] == 'Porsche':
                continue
            text = (ROOT / 'site' / record['path'].strip('/') / 'index.html').read_text()
            self.assertTrue(record['previous_noindex_preserved'], record['brand'])
            self.assertRegex(text, r'<meta name="robots" content="noindex,follow">')
            self.assertIn('data-brand-name="' + html.escape(record['brand'], quote=True) + '"', text)
            if not record['photographs']:
                self.assertNotIn('data-hero-carousel', text)
                self.assertNotIn('data-photo-open=', text)
                self.assertIn('bp-archive-cover', text)

    def test_gallery_photographs_have_actual_identity_and_permissions(self):
        credits = media_records()
        for brand, rows in self.groups.items():
            for photo in photographs(rows, credits):
                self.assertIn(photo['name'], {r['n'] for r in rows})
                self.assertIn(photo['url'], {r['u'] for r in rows})
                for key in ('author', 'licence', 'checked_at'):
                    self.assertTrue(photo[key], (brand, key))
                for key in ('src', 'page', 'licence_url'):
                    self.assertTrue(photo[key].startswith('https://'), (brand, key))

    def test_media_selection_is_deterministic_and_never_repeats_a_file(self):
        rows = [{'n': str(i), 'p': f'photo {i}.jpg'} for i in range(70)]
        first = selected_rows(rows, {})
        self.assertEqual(first, selected_rows(rows[::-1], {}))
        self.assertEqual(len(first), 24)
        self.assertEqual(len({r['p'] for r in first}), 24)
        self.assertEqual(selected_rows([{'n': 'No photo', 'p': ''}], {}), [])

    def test_editorial_and_video_sources_are_recorded_per_brand(self):
        data = json.loads((ROOT / 'data/brand_portal_stories.json').read_text())
        for brand, story in data.items():
            self.assertIn(brand, self.groups)
            self.assertTrue(story['checked_at'])
            self.assertTrue(story['sources'])
            self.assertTrue(story['sections'])
            ids = [film['id'] for film in story['films']]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(all(re.fullmatch(r'[A-Za-z0-9_-]{11}', video) for video in ids))
            self.assertTrue(all(film['publisher'] for film in story['films']))


if __name__ == '__main__':
    unittest.main()
