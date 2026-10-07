import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qa_publication import verify_reader_references
class ReaderReferences(unittest.TestCase):
 def test_visible_encyclopedia_and_article_links_fail_outside_terms(self):
  for content in ('<p>Source: Wikipedia</p>','<a href="https://en.wikipedia.org/wiki/Car">Read more</a>'):
   with self.assertRaises(ValueError):verify_reader_references(content,'/events/example/')
 def test_photo_delivery_path_and_file_credits_are_not_article_references(self):
  verify_reader_references('<img src="https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a1/Car.jpg/960px-Car.jpg"><a href="https://commons.wikimedia.org/wiki/File:Car.jpg">Image credit</a>','/library/example/')
 def test_legal_attribution_is_allowed_only_on_terms_pages(self):
  verify_reader_references('<p>Wikipedia licence notice</p>','/terms/')
  verify_reader_references('<p>Wikipedia licence notice</p>','/pt/terms/')
  with self.assertRaises(ValueError):verify_reader_references('<p>Wikipedia licence notice</p>','/about/')
