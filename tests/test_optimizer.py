import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from preferences import DEFAULTS,save_preferences,read_preferences
from optimizer import solve,build_plan,collect_plan,plan_status
from webapp import create_app

class OptimizerTests(unittest.TestCase):
 def slot(self,n,price,pv=0,load=.1):return dict(start=n*900,end=(n+1)*900,price_ct=price,pv_kwh=pv,load_kwh=load)
 def prefs(self,**kw):return {**DEFAULTS,'plan_capacity_kwh':1,'plan_min_soc':0,'plan_max_soc':100,'plan_end_soc':0,'plan_efficiency':100,'plan_wear_ct':0,'plan_margin_ct':0,**kw}
 def test_cheap_charge_expensive_discharge_and_terminal(self):
  slots=[self.slot(0,5),self.slot(1,50)]
  result=solve(slots,self.prefs(),50,True)
  self.assertGreater(result['slots'][0]['charge_kwh'],0)
  self.assertGreater(result['slots'][1]['discharge_kwh'],0)
  self.assertGreaterEqual(result['end_soc'],50)
  baseline=solve(slots,self.prefs(),50,False)
  self.assertLess(result['cost_eur'],baseline['cost_eur'])
 def test_no_battery_export_and_loss(self):
  result=solve([self.slot(0,5),self.slot(1,50)],self.prefs(plan_efficiency=81),50,True)
  for row in result['slots']:
   self.assertGreaterEqual(row['grid_kwh'],-1e-8)
  self.assertGreater(sum(r['charge_kwh'] for r in result['slots']),sum(r['discharge_kwh'] for r in result['slots']))
 def test_grid_disabled_and_negative_price(self):
  result=solve([self.slot(0,-10,load=0),self.slot(1,30,load=0)],self.prefs(),50,False)
  self.assertTrue(all(r['charge_kwh']==0 for r in result['slots']))
  result=solve([self.slot(0,-10,load=0)],self.prefs(),50,True)
  self.assertGreater(result['slots'][0]['charge_kwh'],0)
 def test_pv_opportunity_cost(self):
  slots=[self.slot(0,20,pv=.2,load=0),self.slot(1,50,pv=0,load=.1)]
  result=solve(slots,self.prefs(),50,False)
  self.assertGreater(result['slots'][0]['charge_kwh'],0)
  self.assertGreater(result['slots'][1]['discharge_kwh'],0)
 def test_api_no_io_and_preferences_validation(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';client=create_app({'database_path':path,'shelly':{'poll_seconds':5}}).test_client()
   with patch('socket.create_connection',side_effect=AssertionError('network')):
    self.assertEqual(client.get('/api/observation-plan').status_code,200)
    result=collect_plan(path,100)
   self.assertEqual(result['status'],'unavailable');self.assertIn('Ladestand',result['message'])
   for changed in ({'plan_efficiency':0},{'plan_min_soc':96},{'plan_hours':.5},{'plan_grid_charge':2}):
    with self.assertRaises(ValueError):save_preferences(path,{**DEFAULTS,**changed},5)
   self.assertFalse(plan_status(path,101)['stale'])
   save_preferences(path,{**DEFAULTS,'plan_house_w':200},5)
   self.assertTrue(plan_status(path,101)['settings_changed'])
 def test_complete_plan_from_stored_inputs(self):
  import json,math
  from datetime import datetime
  from zoneinfo import ZoneInfo
  from database import connect
  from marstek import collect
  now=datetime(2026,9,18,12,1,tzinfo=ZoneInfo('Europe/Berlin')).timestamp();start=math.ceil(now/900)*900
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';create_app({'database_path':path,'shelly':{'poll_seconds':5}})
   collect(path,{},lambda _:dict(soc=50,ac_power_w=0,battery_power_w=0,battery_voltage_v=53,ac_voltage_v=230),now)
   with connect(path) as db:
    db.execute("INSERT INTO tibber_meta VALUES(1,'test')")
    for i in range(4):db.execute('INSERT INTO tibber_prices VALUES(?,?,?,?,?,?,?,?)',('test',start+i*900,start+(i+1)*900,.2,0,0,'EUR',now))
    run=db.execute('INSERT INTO forecast_runs(ts,error) VALUES (?,NULL)',(now,)).lastrowid
    curve={'total_kwh':1,'points':[],'cumulative':[{'ts':start,'wh':0},{'ts':start+3600,'wh':1000}]}
    db.execute('INSERT INTO forecast_days VALUES(?,?,?)',(run,'2026-09-18',json.dumps(curve)))
   result=collect_plan(path,now)
   self.assertEqual(result['status'],'ready');self.assertEqual(len(result['slots']),4)
   self.assertGreaterEqual(result['end_soc'],result['start_soc'])
   self.assertEqual(plan_status(path,now+1)['slots'],result['slots'])
