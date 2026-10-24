import tempfile
import unittest
from pathlib import Path
from database import initialize, save, FIELDS
from balance import estimate, charging_periods
from charging import initialize_charging
from database import connect, history

class BalanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db';initialize(self.path);initialize_charging(self.path)
    def put(self,t,w):save(self.path,t,dict.fromkeys(FIELDS,w))
    def test_energy_and_gap(self):
        self.put(0,3600);self.put(10,3600);self.put(50,3600)
        b=estimate(self.path,0,60)
        self.assertAlmostEqual(b['import_kwh'],.01)
        self.assertEqual(b['missing_seconds'],50)
    def test_sign_change(self):
        self.put(0,3600);self.put(10,-3600)
        b=estimate(self.path,0,11)
        self.assertAlmostEqual(b['import_kwh'],.0025)
        self.assertAlmostEqual(b['export_kwh'],.0025)
    def test_empty(self):self.assertIsNone(estimate(self.path,0,60)['import_kwh'])
    def test_periods_clipped_to_observation(self):
        self.put(0,4000);self.put(10,4000);self.put(50,4000);self.put(55,4000)
        with connect(self.path) as db:db.execute("INSERT INTO charging_events(id,detected_at,event,condition_since,power_w,start_w,stop_w,hold_s) VALUES(1,5,'START_DETECTED',0,4000,3000,2000,180)")
        result=charging_periods(self.path,0,100,history(self.path,0,100))
        self.assertEqual(result,[dict(start=5,end=10),dict(start=50,end=55)])

    def test_error_break_and_archive_boundary(self):
        from maintenance import compact
        for ts, watts in [(120,3600),(125,3600),(135,-3600),(140,-3600),(180,3600),(185,3600)]:
            self.put(ts,watts)
        save(self.path,130,error='timeout')
        before=estimate(self.path,120,200)
        self.assertAlmostEqual(before['import_kwh'],.01)
        self.assertAlmostEqual(before['export_kwh'],.005)
        self.assertEqual(before['covered_seconds'],15)
        compact(self.path,now=86400+180,raw_days=1)
        self.assertEqual(estimate(self.path,120,200),before)
