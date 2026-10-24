import tempfile
import unittest
from pathlib import Path
from database import connect
from marstek import initialize_marstek
from battery_history import day_data

class BatteryHistoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'db';initialize_marstek(self.path)
 def insert(self,ts,power,soc=50,error=None):
  with connect(self.path) as db:db.execute('INSERT INTO marstek_samples(ts,soc,ac_power_w,error) VALUES(?,?,?,?)',(ts,soc,power,error))
 def test_crossing_and_day_boundary(self):
  self.insert(0,-1000);self.insert(60,1000)
  d=day_data(self.path,0,60)
  self.assertAlmostEqual(d['charge_kwh'],15000/3600000)
  self.assertAlmostEqual(d['discharge_kwh'],15000/3600000)
  self.assertEqual(d['coverage'],1)
  d=day_data(self.path,30,60)
  self.assertEqual(d['charge_kwh'],0)
  self.assertAlmostEqual(d['discharge_kwh'],15000/3600000)
 def test_gaps_and_errors_not_filled(self):
  self.insert(0,1000);self.insert(30,1000);self.insert(60,None,None,'offline');self.insert(90,1000);self.insert(200,1000)
  d=day_data(self.path,0,200)
  self.assertEqual(d['covered_seconds'],30)
  self.assertEqual([len(s) for s in d['segments']],[2,1,1])
 def test_no_data(self):
  d=day_data(self.path,0,60)
  self.assertIsNone(d['charge_kwh']);self.assertEqual(d['segments'],[])
