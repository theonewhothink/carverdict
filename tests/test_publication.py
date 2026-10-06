import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from publication_policy import apply, verify, load_policy
from nhtsa_records import records
from score_model_years import compute
from refresh_pilot import refresh
from tag_site import strip_measurement


class EvidenceChecks(unittest.TestCase):
    def test_service_specific_rx_alias(self):
        def get(url):
            if '/products/' in url:return {'results':[{'model':'RX 350'}]}
            if '/recalls/' in url:
                self.assertIn('model=RX350',url)
                return {'count':1,'results':[{'NHTSACampaignNumber':'20V682000'}]}
            self.assertIn('model=RX+350',url)
            return {'count':1,'results':[{'odiNumber':123}]}
        for kind in ['recalls','complaints']:
            result=records('LEXUS','RX 350',2020,kind,get)
            self.assertEqual(result['status'],'matched');self.assertEqual(result['count'],1)

    def test_missing_invalid_and_incomplete_data_never_become_zero(self):
        def incomplete(url):
            if '/products/' in url:return {'results':[{'model':'RX 350'}]}
            return {'count':2,'results':[{'NHTSACampaignNumber':'20V682000'}]}
        for get,status in [(lambda url:None,'unavailable'),(lambda url:{'results':[]},'unmatched'),(incomplete,'incomplete')]:
            result=records('LEXUS','RX 350',2020,'recalls',get)
            self.assertEqual(result['status'],status);self.assertIsNone(result['count'])

    def test_confirmed_empty_and_duplicate_campaigns(self):
        def get(url):
            if '/products/' in url:return {'results':[{'model':'RAV4'}]}
            return {'count':0,'results':[]}
        self.assertEqual(records('TOYOTA','RAV4',2020,'recalls',get)['status'],'empty')
        def duplicate(url):
            if '/products/' in url:return {'results':[{'model':'RAV4'}]}
            return {'count':2,'results':[{'NHTSACampaignNumber':'20V064000'}]*2}
        self.assertEqual(records('TOYOTA','RAV4',2020,'recalls',duplicate)['count'],1)
        self.assertEqual(records('TOYOTA','RAV4 HYBRID',2020,'recalls',get)['status'],'unmatched')

    def test_legacy_ratings_are_suspended(self):
        con=sqlite3.connect(':memory:')
        con.execute('CREATE TABLE model_years(id INT)');con.execute('INSERT INTO model_years VALUES(1)')
        compute(con)
        self.assertEqual(con.execute('SELECT reliability_score,verdict FROM computed_scores').fetchone(),(None,'RECORD ONLY'))

    def test_failed_refresh_retains_prior_evidence_and_date(self):
        prior = {'records':[{'make':'TOYOTA','model':'RAV4','year':2020,'checks':{'recalls':{'checked_at':'2026-10-01','count':6}}}]}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'records.json';path.write_text(json.dumps(prior))
            refresh(path, lambda url: None)
            self.assertEqual(json.loads(path.read_text()), prior)


class AdvertisingChecks(unittest.TestCase):
    def test_preview_removes_production_measurement_on_rebuild(self):
        text='<script async src="https://www.googletagmanager.com/gtag/js?id=TEST"></script><script>window.dataLayer=[];gtag("config","TEST");</script><script src="/assets/buying-brief.mjs"></script>'
        result=strip_measurement(text)
        self.assertNotIn('googletagmanager',result);self.assertNotIn('dataLayer',result)
        self.assertIn('buying-brief.mjs',result)
    def test_noindex_is_not_ad_approval(self):
        with tempfile.TemporaryDirectory() as d:
            site=Path(d);p=site/'library'/'index.html';p.parent.mkdir()
            p.write_text('<head><meta name="robots" content="noindex,follow"><script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"></script></head><ins class="adsbygoogle"></ins><script>(adsbygoogle=window.adsbygoogle||[]).push({});</script><script>keepUsefulCode()</script>')
            policy={'ads_enabled':False,'ad_pages':{}}
            with self.assertRaises(ValueError):verify(site,policy)
            apply(site,policy);verify(site,policy)
            self.assertNotIn('adsbygoogle',p.read_text());self.assertIn('keepUsefulCode()',p.read_text())
    def test_an_unrecorded_review_cannot_enable_ads(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'policy.json';p.write_text(json.dumps({'ads_enabled':True,'ad_pages':{'/buying-brief/':{}}}))
            with self.assertRaises(ValueError):load_policy(p)


if __name__=='__main__':unittest.main()
