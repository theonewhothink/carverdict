"""Jury photographs come only from Commons or from a Flickr file with its source page."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import build_jury  # noqa: E402

BASE = {'id': 'Q1', 'n': 'Car', 'b': 'Make', 'u': '/library/x/', 'p': 'Car.jpg', 'a': 'Someone', 'l': 'CC BY 2.0',
        'lu': 'https://creativecommons.org/licenses/by/2.0/'}


def check(row):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'data').mkdir()
        (Path(tmp) / 'data/jury_cars.json').write_text(json.dumps([row]))
        build_jury.cars.cache_clear()
        try:
            with mock.patch.object(build_jury, 'ROOT', Path(tmp)):
                return build_jury.cars()
        finally:
            build_jury.cars.cache_clear()


class JuryPhotos(unittest.TestCase):
    def test_flickr_needs_its_source_page(self):
        row = dict(BASE, t='https://live.staticflickr.com/1/2_a_b.jpg')
        with self.assertRaises(ValueError):
            check(row)
        self.assertEqual(len(check(dict(row, s='https://www.flickr.com/photos/a/2/'))), 1)

    def test_other_hosts_are_refused(self):
        with self.assertRaises(ValueError):
            check(dict(BASE, t='https://example.com/car.jpg', s='https://www.flickr.com/photos/a/2/'))

    def test_credit_links_to_source(self):
        self.assertEqual(build_jury.commons({'p': 'x', 's': 'https://www.flickr.com/photos/a/2/'}), 'https://www.flickr.com/photos/a/2/')
        self.assertEqual(build_jury.small('https://live.staticflickr.com/1/2_a_b.jpg'), 'https://live.staticflickr.com/1/2_a_n.jpg')


if __name__ == '__main__':
    unittest.main()
