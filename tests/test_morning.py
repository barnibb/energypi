import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from database import connect
from morning import update_morning,night_target_soc,market_context
from preferences import DEFAULTS

ZONE=ZoneInfo('Europe/Berlin')

class MorningTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'db'
  with connect(self.path):pass
  self.now=datetime(2026,9,26,6,0,tzinfo=ZONE).timestamp()
  self.prefs=DEFAULTS.copy();self.state={}
  self.charging={'stale':False,'state':{'active':False,'corrected_power_w':500}}
 def test_full_window_release_without_trigger_or_budget(self):
  limit,event=update_morning(self.path,self.state,self.prefs,self.charging,45,0,self.now)
  self.assertEqual((limit,event),(800,'START'))
  limit,event=update_morning(self.path,self.state,self.prefs,self.charging,45,800,self.now+30)
  self.assertEqual(limit,800);self.assertIsNone(event)
 def test_stops_at_soc_floor_and_restarts_after_recharge(self):
  update_morning(self.path,self.state,self.prefs,self.charging,15,0,self.now)
  limit,event=update_morning(self.path,self.state,self.prefs,self.charging,12,800,self.now+30)
  self.assertEqual((limit,event),(None,'END'))
  limit,event=update_morning(self.path,self.state,self.prefs,self.charging,20,0,self.now+60)
  self.assertEqual((limit,event),(800,'START'))
 def test_outside_window_only(self):
  early=datetime(2026,9,26,4,59,tzinfo=ZONE).timestamp()
  self.assertEqual(update_morning(self.path,self.state,self.prefs,self.charging,50,0,early)[0],None)
 def test_autoload_is_left_to_higher_priority_control_layer(self):
  self.charging['state']['active']=True
  self.assertEqual(update_morning(self.path,{},self.prefs,self.charging,50,0,self.now)[0],800)
 def test_night_target_and_missing_market_data(self):
  self.assertAlmostEqual(night_target_soc(self.prefs),46.375)
  context=market_context(self.path,self.prefs,self.now)
  self.assertIsNone(context['pv_remaining_kwh'])

if __name__=='__main__':unittest.main()
