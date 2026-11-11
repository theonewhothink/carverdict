"""A data refresh must not delete published year URLs below the new-page gate."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_record_pages as records


class PublishedYearRoutes(unittest.TestCase):
    def test_missing_published_year_is_rebuilt_from_its_exact_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            site = root / 'site'
            model = site / 'cars/test/model/index.html'
            model.parent.mkdir(parents=True)
            model.write_text('<head></head><main>Existing model</main>')
            existing = model.parent / '2016/index.html'
            existing.parent.mkdir()
            existing.write_text('<head></head><main>Existing year</main>')
            legacy = ['/cars/test/model/2014/', '/cars/test/model/2016/',
                      '/cars/test/unknown/2014/']
            (root / 'data/legacy_routes.json').write_text(json.dumps({'routes': legacy}))
            con = sqlite3.connect(root / 'data/cars.sqlite')
            con.executescript('''
                CREATE TABLE makes(id INTEGER, name TEXT, slug TEXT);
                CREATE TABLE models(id INTEGER, make_id INTEGER, name TEXT, slug TEXT);
                CREATE TABLE model_years(id INTEGER, model_id INTEGER, year INTEGER,
                    complaint_count INTEGER, recall_count INTEGER);
                CREATE TABLE source_checks(my_id INTEGER, service TEXT, status TEXT);
                INSERT INTO makes VALUES(1, 'Test', 'test');
                INSERT INTO models VALUES(1, 1, 'Model', 'model');
                INSERT INTO model_years VALUES(1, 1, 2014, 2, 1);
                INSERT INTO model_years VALUES(2, 1, 2015, 1, 0);
                INSERT INTO model_years VALUES(3, 1, 2016, 3, 1);
            ''')
            con.close()

            def write(path, title, body, **kwargs):
                page = site / path.strip('/') / 'index.html'
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text('<head></head><main>' + body + '</main>')

            with patch.multiple(records, ROOT=root, SITE=site, write=write,
                                apply_pilot=lambda con: None,
                                record_photo=lambda *args: ''):
                records.main()

            restored = (model.parent / '2014/index.html').read_text()
            self.assertIn('2014 Test Model', restored)
            self.assertIn('Not verified', restored)
            self.assertIn('noindex,follow', restored)
            self.assertNotIn('Complaint reports: <b>2</b>', restored)
            self.assertTrue(existing.is_file())
            # An unpublished year and a legacy URL without a matching database
            # identity must not acquire invented records.
            self.assertFalse((model.parent / '2015/index.html').exists())
            self.assertFalse((site / 'cars/test/unknown/2014/index.html').exists())

    def test_brand_page_links_only_indexable_years(self):
        # The model hub is noindex, so the brand page is the indexable route to a year.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            site = root / 'site'
            (site / 'cars/test/model').mkdir(parents=True)
            (site / 'cars/test/model/index.html').write_text('<head></head>')
            (root / 'data/legacy_routes.json').write_text(json.dumps(
                {'routes': ['/cars/test/model/2014/', '/cars/test/model/2016/']}))
            con = sqlite3.connect(root / 'data/cars.sqlite')
            con.executescript('''
                CREATE TABLE makes(id INTEGER, name TEXT, slug TEXT);
                CREATE TABLE models(id INTEGER, make_id INTEGER, name TEXT, slug TEXT);
                CREATE TABLE model_years(id INTEGER, model_id INTEGER, year INTEGER,
                    complaint_count INTEGER, recall_count INTEGER);
                CREATE TABLE source_checks(my_id INTEGER, service TEXT, status TEXT,
                    checked_at TEXT);
                CREATE TABLE recalls(my_id INTEGER, campaign TEXT, component TEXT, summary TEXT);
                INSERT INTO makes VALUES(1, 'Test', 'test');
                INSERT INTO models VALUES(1, 1, 'Model', 'model');
                INSERT INTO model_years VALUES(1, 1, 2014, 2, 1);
                INSERT INTO model_years VALUES(2, 1, 2016, 3, 0);
                INSERT INTO source_checks VALUES(2, 'recalls', 'empty', '2026-11-01');
            ''')
            con.close()

            def write(path, title, body, **kwargs):
                page = site / path.strip('/') / 'index.html'
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text('<head></head><main>' + body + '</main>')

            with patch.multiple(records, ROOT=root, SITE=site, write=write,
                                apply_pilot=lambda con: None,
                                record_photo=lambda *args: ''):
                records.main()

            brand = (site / 'cars/test/index.html').read_text()
            self.assertIn('href="/cars/test/model/2016/"', brand)
            self.assertNotIn('href="/cars/test/model/2014/"', brand)

    def test_recall_study_counts_distinct_campaigns_on_matched_years_only(self):
        con = sqlite3.connect(':memory:')
        con.row_factory = sqlite3.Row
        con.executescript('''
            CREATE TABLE recalls(my_id INTEGER, campaign TEXT, component TEXT);
            INSERT INTO recalls VALUES(1, '20V1', 'AIR BAGS:SENSOR');
            INSERT INTO recalls VALUES(1, '20V1', 'AIR BAGS:SENSOR');
            INSERT INTO recalls VALUES(1, '20V2', 'STEERING');
            INSERT INTO recalls VALUES(2, '20V3', 'STEERING');
            INSERT INTO recalls VALUES(2, '20V4', 'STEERING');
            INSERT INTO recalls VALUES(2, '20V5', 'STEERING');
        ''')
        row = lambda i, y: {'id': i, 'year': y, 'make': 'Test', 'model': 'Model',
                            'kslug': 'test', 'mslug': 'model'}
        rows = [row(1, 2020), row(2, 2021)]
        checks = {(1, 'recalls'): {'status': 'matched', 'checked_at': '2026-11-01T00:00'},
                  (2, 'recalls'): {'status': 'unmatched', 'checked_at': '2026-11-01T00:00'}}
        pages = {}
        with patch.object(records, 'write', lambda path, title, body, **kw: pages.update({path: body})):
            records.recall_study(con, rows, checks, {'/cars/test/model/': [2020]})
        body = pages['/recall-campaigns/']
        self.assertIn('<td><a href="/cars/test/model/2020/">2020 Test Model</a></td><td>2</td>', body)
        self.assertNotIn('2021 Test Model', body)
        self.assertIn('<td>Air bags</td><td>1</td>', body)


if __name__ == '__main__':
    unittest.main()
