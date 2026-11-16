import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES = json.loads((ROOT / 'data/collection_profiles.json').read_text())['profiles']


class ProfileFilmTest(unittest.TestCase):
    def test_every_profile_page_has_a_click_to_load_film_with_video_data(self):
        pages = list((ROOT / 'site/library').glob('*/*/index.html'))
        if not pages:
            self.skipTest('site not built')
        films = {p['film']['id'] for p in PROFILES}
        found = set()
        for page in pages:
            html = page.read_text()
            ids = set(re.findall(r'data-video="([A-Za-z0-9_-]{11})"', html)) & films
            if not ids:
                continue
            found |= ids
            self.assertNotIn('<iframe', html, page)
            blocks = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
            videos = [x for b in blocks for x in (b if isinstance(b, list) else [b]) if x.get('@type') == 'VideoObject']
            self.assertEqual(len(videos), 1, page)
            for key in ('name', 'description', 'thumbnailUrl', 'uploadDate', 'duration', 'embedUrl'):
                self.assertTrue(videos[0].get(key), (page, key))
            self.assertRegex(videos[0]['duration'], r'^PT\d+M\d+S$')
        self.assertEqual(found, films)


if __name__ == '__main__':
    unittest.main()
