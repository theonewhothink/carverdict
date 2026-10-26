"""Reader-facing regressions: exact identities, full coverage and global navigation."""
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import site_chrome
from brand_portals import load


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = []
        self.links = []
        self.h1s = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'h1':
            self.h1s += 1


class BrandPortal(unittest.TestCase):
    def test_global_search_keeps_native_fallback_and_is_idempotent(self):
        with patch.object(site_chrome, 'prepare', return_value=('header.css', 'header.mjs')):
            for shell in ('<header><div class="wrap"><a class="logo" href="/">MotorJury</a><nav>Navigation</nav></div></header>',
                          '<header><nav>Legacy navigation</nav></header>'):
                original = '<html><head></head><body>' + shell + '</body></html>'
                result = site_chrome.enhance(original)
                self.assertEqual(result, site_chrome.enhance(result))
                self.assertEqual(result.count('id="header-car-search"'), 1)
                self.assertIn('action="/library/" method="get"', result)
                self.assertIn('name="q"', result)
                self.assertIn('Navigation' if 'logo' in shell else 'Legacy navigation', result)

    def test_portal_has_individually_licensed_distinct_photographs(self):
        data = load()
        self.assertEqual(len(data['photographs']), 24)
        self.assertEqual(len({photo['file'] for photo in data['photographs']}), 24)
        self.assertEqual(len(data['films']), 6)
        self.assertEqual(len({film['id'] for film in data['films']}), 6)
        for photo in data['photographs']:
            for key in ('author', 'licence', 'licence_url', 'page', 'src', 'checked_at'):
                self.assertTrue(photo[key], (photo['name'], key))
            self.assertTrue(photo['src'].startswith('https://'))
        self.assertTrue(all(re.fullmatch(r'[A-Za-z0-9_-]{11}', film['id']) for film in data['films']))

    def test_media_and_history_are_visible_without_extra_disclosure_clicks(self):
        data = load()
        text = (ROOT / 'site/library/porsche/index.html').read_text()
        self.assertNotIn('<details', text)
        self.assertNotIn('<summary', text)
        self.assertIn('data-hero-interval="2000"', text)
        self.assertEqual(text.count('data-hero-slide '), len(data['hero_slides']))
        self.assertEqual(len(data['hero_slides']), 6)
        self.assertEqual(text.count('class="bp-feature-film bp-section"'), 3)
        self.assertEqual(text.count('class="bp-milestone-heading"'), 8)
        for film in data['films']:
            self.assertIn(f'https://i.ytimg.com/vi/{film["id"]}/hqdefault.jpg', text)
            self.assertIn(f'https://www.youtube.com/watch?v={film["id"]}', text)

    def test_homepage_keeps_car_search_and_removes_the_inline_ai_form(self):
        text = (ROOT / 'site/index.html').read_text()
        self.assertNotIn('data-chat-entry', text)
        self.assertNotIn('home-car-question', text)
        self.assertIn('id="car-search"', text)

    def test_final_portal_preserves_every_porsche_anchor_and_destination(self):
        text = (ROOT / 'site/library/porsche/index.html').read_text()
        page = Page(text)
        self.assertEqual(page.h1s, 1)
        self.assertEqual(len(page.ids), len(set(page.ids)))
        self.assertIn('data-brand-portal', text)
        rows = json.loads((ROOT / 'site/assets/catalogue-data.json').read_text())
        expected = [row for row in rows if row['b'] == 'Porsche']
        self.assertEqual(text.count('data-model-name='), len(expected))
        for row in expected:
            path, _, anchor = row['u'].partition('#')
            self.assertTrue((ROOT / 'site' / path.strip('/') / 'index.html').is_file())
            if anchor:
                self.assertIn(anchor, page.ids)
        for url in page.links:
            if url.startswith('#'):
                self.assertIn(url[1:], page.ids)

    def test_search_index_cannot_invent_or_drop_car_destinations(self):
        index = json.loads((ROOT / 'site/assets/header-search-index.json').read_text())
        catalogue = json.loads((ROOT / 'site/assets/catalogue-data.json').read_text())
        self.assertEqual([(row['n'], row['u']) for row in index['cars']], [(row['n'], row['u']) for row in catalogue])
        self.assertEqual({row['n'] for row in index['brands']}, {row['b'] for row in catalogue})
        for row in index['brands']:
            self.assertTrue((ROOT / 'site' / row['u'].strip('/') / 'index.html').is_file(), row['u'])
        self.assertIn({'n': 'Porsche', 'u': '/library/porsche/'}, index['brands'])


if __name__ == '__main__':
    unittest.main()
