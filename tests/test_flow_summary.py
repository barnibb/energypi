import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from database import connect
from energy import initialize_energy
from flow_summary import flow_summary

class FlowTests(unittest.TestCase):
 def test_balance_and_missing_battery(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';initialize_energy(path)
   b=dict(import_kwh=2,export_kwh=3,coverage=.99)
   self.assertFalse(flow_summary(path,'2026-09-13',b,1800000000)['valid'])
   with connect(path) as db:db.execute('INSERT INTO solaredge_energy VALUES(?,?,?)',('2026-09-13',10,0))
   self.assertFalse(flow_summary(path,'2026-09-13',b,1800000000)['valid'])
   battery=dict(charge_kwh=4,discharge_kwh=1,coverage=.99,start_soc=20,end_soc=60)
   with patch('flow_summary.day_data',return_value=battery):
    result=flow_summary(path,'2026-09-13',b,1800000000)
    self.assertTrue(result['valid']);self.assertEqual(result['house_kwh'],6)
    self.assertEqual(result['battery_in_kwh'],4)
    self.assertIsNone(result['autarky_percent'])
    self.assertFalse(flow_summary(path,'2026-09-13',{**b,'export_kwh':20},1800000000)['valid'])
    self.assertFalse(flow_summary(path,'2026-09-13',{**b,'coverage':.5},1800000000)['valid'])
 def test_today_alignment(self):
  from datetime import datetime
  from zoneinfo import ZoneInfo
  now=datetime(2026,9,18,13,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';initialize_energy(path)
   with connect(path) as db:db.execute('INSERT INTO solaredge_energy VALUES(?,?,?)',('2026-09-18',10,now-1800))
   with patch('flow_summary.estimate',return_value={'import_kwh':1,'export_kwh':1,'coverage':1}) as estimate:
    result=flow_summary(path,'2026-09-18',{},now)
    self.assertEqual(estimate.call_args.args[2],now-1800)
    self.assertEqual(result['until'],now-1800)
 def test_today_accepts_closing_value_after_sunset(self):
  from datetime import datetime
  from zoneinfo import ZoneInfo
  zone=ZoneInfo('Europe/Berlin')
  now=datetime(2026,10,23,21,tzinfo=zone).timestamp()
  fetched=datetime(2026,10,23,18,0,tzinfo=zone).timestamp()
  battery=dict(charge_kwh=1,discharge_kwh=.5,coverage=1,start_soc=40,end_soc=50)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';initialize_energy(path)
   with connect(path) as db:db.execute('INSERT INTO solaredge_energy VALUES(?,?,?)',('2026-10-23',4.5,fetched))
   with patch('flow_summary.estimate',return_value={'import_kwh':2,'export_kwh':1,'coverage':1}),patch('flow_summary.day_data',return_value=battery):
    result=flow_summary(path,'2026-10-23',{},now)
   self.assertTrue(result['valid'])
   self.assertEqual(result['until'],fetched)
   self.assertIn('PV-Tag nach Sonnenuntergang abgeschlossen',result['reason'])
 def test_today_rejects_old_value_even_after_sunset(self):
  from datetime import datetime
  from zoneinfo import ZoneInfo
  zone=ZoneInfo('Europe/Berlin')
  now=datetime(2026,10,23,21,tzinfo=zone).timestamp()
  fetched=datetime(2026,10,23,17,tzinfo=zone).timestamp()
  battery=dict(charge_kwh=1,discharge_kwh=.5,coverage=1,start_soc=40,end_soc=50)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';initialize_energy(path)
   with connect(path) as db:db.execute('INSERT INTO solaredge_energy VALUES(?,?,?)',('2026-10-23',4.5,fetched))
   with patch('flow_summary.estimate',return_value={'import_kwh':2,'export_kwh':1,'coverage':1}),patch('flow_summary.day_data',return_value=battery):
    result=flow_summary(path,'2026-10-23',{},now)
   self.assertFalse(result['valid'])
   self.assertIn('veraltet',result['reason'])
