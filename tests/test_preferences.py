import tempfile
import unittest
from pathlib import Path
from preferences import DEFAULTS,read_preferences,save_preferences
from webapp import create_app
from database import connect

class PreferencesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'db'
  self.client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
 def test_persistence_and_audit(self):
  values={**DEFAULTS,'feed_in_ct':8.5};save_preferences(self.path,values,5)
  self.assertEqual(read_preferences(self.path),values)
  with connect(self.path) as db:self.assertEqual(db.execute('SELECT count(*) FROM preference_changes').fetchone()[0],1)
 def test_invalid(self):
  for changed in ({'release_below_w':2500},{'max_gap_seconds':5},{'feed_in_ct':float('nan')},{'hold_seconds':0},{'sustained_discharge_w':49},{'sustained_discharge_seconds':59}):
   with self.assertRaises(ValueError):save_preferences(self.path,{**DEFAULTS,**changed},5)
 def test_post_guard(self):
  self.assertEqual(self.client.post('/api/preferences',json=DEFAULTS).status_code,403)
  self.assertEqual(self.client.post('/api/preferences',json=DEFAULTS,headers={'X-EnergyPi':'settings'}).status_code,200)

 def test_old_preferences_keep_custom_values(self):
  import json
  old={k:v for k,v in DEFAULTS.items() if k not in ('base_load_w','ev_current_a')}
  old['feed_in_ct']=8
  with connect(self.path) as db:db.execute('UPDATE preferences SET payload=?',(json.dumps(old),))
  result=read_preferences(self.path)
  self.assertEqual(result['feed_in_ct'],8)
  self.assertEqual(result['base_load_w'],160)
  self.assertEqual(result['ev_current_a'],5)
 def test_pv_threshold_and_validation(self):
  from opportunities import annotate
  from datetime import date
  values={**DEFAULTS,'base_load_w':200,'ev_current_a':7}
  save_preferences(self.path,values,5)
  result=annotate(self.path,date(2026,9,14),[],0)
  self.assertEqual(result['pv_threshold_w'],5030)
  for changes in ({'base_load_w':-1},{'ev_current_a':0}):
   with self.assertRaises(ValueError):save_preferences(self.path,{**values,**changes},5)

 def test_pv_sunshine_threshold(self):
  values={**DEFAULTS,'pv_sunshine_threshold_w':2500}
  save_preferences(self.path,values,5)
  self.assertEqual(read_preferences(self.path)['pv_sunshine_threshold_w'],2500)
  for value in (400,2050,7100):
   with self.assertRaises(ValueError):save_preferences(self.path,{**DEFAULTS,'pv_sunshine_threshold_w':value},5)

 def test_frost_temperature_threshold(self):
  values={**DEFAULTS,'frost_temperature_c':-1.5}
  save_preferences(self.path,values,5)
  self.assertEqual(read_preferences(self.path)['frost_temperature_c'],-1.5)
  save_preferences(self.path,{**DEFAULTS,'frost_temperature_c':18},5)
  for value in (-20.5,18.5,0.25):
   with self.assertRaises(ValueError):save_preferences(self.path,{**DEFAULTS,'frost_temperature_c':value},5)

 def test_forecast_hours(self):
  for changes in ({'forecast_start_hour':23,'forecast_end_hour':5},{'forecast_start_hour':-1},{'forecast_end_hour':25},{'forecast_start_hour':5.5}):
   with self.assertRaises(ValueError):save_preferences(self.path,{**DEFAULTS,**changes},5)
  save_preferences(self.path,{**DEFAULTS,'forecast_start_hour':0,'forecast_end_hour':24},5)
  self.assertEqual(read_preferences(self.path)['forecast_end_hour'],24)
 def test_morning_parameters(self):
  values={**DEFAULTS,'morning_start_hour':4,'morning_end_hour':11,'night_start_hour':21,'morning_min_soc':13,'night_energy_kwh':1.8}
  save_preferences(self.path,values,5);self.assertEqual(read_preferences(self.path)['night_energy_kwh'],1.8)
  for changes in ({'morning_start_hour':10,'morning_end_hour':5},{'morning_release_w':825},{'morning_min_soc':10},{'night_start_hour':9},{'night_energy_kwh':11},{'soc_low_threshold':45}):
   with self.assertRaises(ValueError):save_preferences(self.path,{**DEFAULTS,**changes},5)
