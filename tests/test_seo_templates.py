import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from seo_templates import PageMetadata, normalise_search_metadata, metadata_issues, directory_jumps


class SearchTemplates(unittest.TestCase):
    def fixture(self, robots=''):
        nodes = [{'@type': 'WebPage', 'url': 'https://motorjury.com/library/example/',
                  'description': 'An incorrect generic description'},
                 {'@type': 'Article', 'dateModified': '2026-10-07', 'citation': ['https://example.com/source']}]
        return ('<html><head><title>A car &amp; its story</title>'
                '<meta name="description" content="A sourced &quot;car&quot; story.">'
                '<link rel="canonical" href="https://motorjury.com/library/example/">'
                '<meta property="og:description" content="Old boilerplate">'
                '<meta property="og:image" content="https://motorjury.com/og/default.png">'
                '<meta property="og:image:width" content="1200">'
                + (f'<meta name="robots" content="{robots}">' if robots else '')
                + '<script type="application/ld+json">' + json.dumps(nodes) + '</script>'
                '</head><body><img src="/icon.png" width="32" alt="Logo">'
                '<img src="https://images.example/car.jpg" width="960" alt="A photographed car">'
                '<h1>A car</h1></body></html>')

    def test_page_social_and_schema_agree_without_inventing_evidence(self):
        before = self.fixture()
        self.assertIn('Inconsistent og:description', metadata_issues(before))
        result = normalise_search_metadata(before)
        self.assertEqual(metadata_issues(result), [])
        p = PageMetadata(); p.feed(result)
        self.assertEqual(p.metas['og:description'], 'A sourced "car" story.')
        self.assertEqual(p.metas['twitter:image'], 'https://images.example/car.jpg')
        self.assertNotIn('og:image:width', result)
        nodes = json.loads(re.search(r'application/ld\+json">(.*?)</script>', result).group(1))
        self.assertEqual(nodes[0]['primaryImageOfPage']['url'], p.metas['og:image'])
        self.assertEqual(nodes[1]['dateModified'], '2026-10-07')
        self.assertEqual(nodes[1]['citation'], ['https://example.com/source'])
        self.assertNotIn('offers', result)
        self.assertNotIn('aggregateRating', result)
        self.assertEqual(normalise_search_metadata(result), result)

    def test_reference_and_preview_holds_and_explicit_image_limits_survive(self):
        for directive in ['noindex,follow', 'noindex,nofollow', 'none', 'max-image-preview:none']:
            text = normalise_search_metadata(self.fixture(directive))
            self.assertIn(f'content="{directive}"', text)
            self.assertNotIn('max-image-preview:large', text)
            self.assertEqual(metadata_issues(text), [])

    def test_malformed_schema_is_reported_rather_than_replaced_with_fake_data(self):
        text = self.fixture().replace('"@type": "Article"', 'bad json')
        result = normalise_search_metadata(text)
        self.assertIn('Malformed structured data', metadata_issues(result))
        self.assertIn('bad json', result)

    def test_invalid_image_dimensions_do_not_hide_later_real_photograph(self):
        text = self.fixture().replace('<body>', '<body><img src="/decoration.svg" width="100%" alt="Decoration">')
        p = PageMetadata(); p.feed(normalise_search_metadata(text))
        self.assertEqual(p.metas['og:image'], 'https://images.example/car.jpg')

    def test_directory_has_one_direct_link_to_every_range(self):
        rows = [{'n': 'Car ' + str(i)} for i in range(15888)]
        text = directory_jumps(rows)
        links = re.findall(r'href="([^"]+)"', text)
        self.assertEqual(len(links), 133)
        self.assertEqual(len(set(links)), 133)
        self.assertEqual(links[0], '/all-cars/')
        self.assertEqual(links[-1], '/all-cars/page/133/')
        self.assertIn('Car 15840 – Car 15887', text)

    def test_svg_accessibility_titles_do_not_change_the_document_title(self):
        text = self.fixture().replace('<body>', '<body><svg><title>EV badge</title></svg>')
        result = normalise_search_metadata(text)
        p = PageMetadata(); p.feed(result)
        self.assertEqual(p.title, 'A car & its story')
        self.assertEqual(p.metas['og:title'], p.title)
        self.assertEqual(metadata_issues(result), [])
        from audit_dashboard_seo import Head
        inventory = Head(); inventory.feed(result)
        self.assertEqual(inventory.title, p.title)


if __name__ == '__main__':
    unittest.main()
