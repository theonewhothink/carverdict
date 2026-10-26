"""Catalogue migrations must preserve identity and resolve to real content."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_recovery import build_redirects


class CatalogueRecovery(unittest.TestCase):
    def test_old_manufacturer_slug_and_capped_page_use_exact_roster_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / 'library/byd-auto/index.html'
            page.parent.mkdir(parents=True)
            page.write_text('<li id="m-byd-atto-3">BYD Atto 3</li>')
            raw = [{'q': 'Q1', 'm': 'BYD Auto', 'n': 'BYD Atto 3'}]
            rows = [{'q': 'Q1', 'b': 'BYD Auto', 'n': 'BYD Atto 3', 'u': '/library/byd-auto/#m-byd-atto-3'}]
            redirects = build_redirects(raw, rows, root)
            self.assertEqual(redirects['/library/byd/byd-atto-3/'], rows[0]['u'])
            self.assertEqual(redirects['/library/byd-auto/byd-atto-3/'], rows[0]['u'])
            self.assertNotIn('/library/byd/imaginary-car/', redirects)

    def test_missing_anchor_ambiguous_identity_and_existing_page_are_not_redirected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / 'library/audi/index.html'
            page.parent.mkdir(parents=True)
            page.write_text('<p>No matching roster entry</p>')
            raw = [{'q': 'Q1', 'm': 'Audi AG', 'n': 'Audi S7'}]
            rows = [{'q': 'Q1', 'b': 'Audi', 'n': 'Audi S7', 'u': '/library/audi/#m-audi-s7'}]
            self.assertEqual(build_redirects(raw, rows, root), {})
            page.write_text('<li id="m-audi-s7">Audi S7</li>')
            rows.append(dict(rows[0], u='/library/other/#m-audi-s7'))
            self.assertEqual(build_redirects(raw, rows, root), {})
            rows.pop()
            old = root / 'library/audi-ag/audi-s7/index.html'
            old.parent.mkdir(parents=True)
            old.write_text('Existing article')
            self.assertNotIn('/library/audi-ag/audi-s7/', build_redirects(raw, rows, root))
