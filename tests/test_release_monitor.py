import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from monitor_release import evaluate
class ReleaseMonitor(unittest.TestCase):
 def test_wrong_source_and_failed_route_cannot_be_healthy(self):
  sha='a'*40;manifest={'sha':sha,'checks':'passed','preview':False}
  self.assertEqual(evaluate(manifest,[{'path':'/','status':200}],sha),[])
  self.assertTrue(evaluate(manifest,[{'path':'/','status':404}],sha))
  self.assertTrue(evaluate(manifest,[{'path':'/','status':200}],'b'*40))
  self.assertTrue(evaluate(None,[],sha))
  self.assertTrue(evaluate(dict(manifest,preview=True),[],sha))
  self.assertTrue(evaluate(dict(manifest,sha='main'),[],sha))
