import tempfile
import unittest
from pathlib import Path
from database import connect
from webapp import create_app
from marstek_display import operating_status,decision_log

class DisplayTests(unittest.TestCase):
 def test_modes_limits_and_stale(self):
  state=dict(observed_mode=1,observed_rs485=21947,observed_limit_w=200,checked_at=100,baseline=800,applied=200,conflict=False)
  self.assertEqual(operating_status(state,{'ac_power_w':199},False,110)['label'],'Autolade-Begrenzung')
  state['pending_reason']='sustained_limit'
  self.assertEqual(operating_status(state,{'ac_power_w':199},False,110)['label'],'Dauerlast-Begrenzung')
  state['effective_reason']='soc_safety'
  self.assertEqual(operating_status(state,{'ac_power_w':199},False,110)['label'],'SOC-Sicherheitsbegrenzung')
  state.update(effective_reason='morning',morning={'active':True})
  self.assertEqual(operating_status(state,{'ac_power_w':199},False,110)['label'],'Morgenkomfort')
  state.update(baseline=None,effective_reason='normal',morning={'active':False})
  self.assertEqual(operating_status(state,None,False,110)['label'],'Eigenverbrauch')
  state['observed_mode']=0
  self.assertEqual(operating_status(state,{'ac_power_w':-2500},False,110)['label'],'Manuelles Laden')
  self.assertEqual(operating_status(state,{'ac_power_w':0},False,110)['label'],'Manueller Modus · Pause')
  self.assertTrue(operating_status(state,None,False,200)['stale'])
  self.assertEqual(operating_status({},None,True,200)['limit_w'],None)
 def test_log_and_endpoint(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';client=create_app({'database_path':path,'shelly':{'poll_seconds':5}}).test_client()
   with connect(path) as db:
    db.execute("INSERT INTO charging_events(detected_at,event,condition_since,power_w,start_w,stop_w,hold_s) VALUES(100,'START_DETECTED',90,2500,2000,1000,180)")
    db.execute("INSERT INTO charging_events(detected_at,event,condition_since,power_w,start_w,stop_w,hold_s,reason) VALUES(101,'START_DETECTED',91,1500,2000,1000,600,'sustained_discharge')")
    db.execute("INSERT INTO marstek_control_events(ts,event,value_w,detail) VALUES(110,'CONFIRMED',200,'Autoladen erkannt → Entladegrenze auf 200 W bestätigt')")
    db.execute("INSERT INTO marstek_control_events(ts,event,value_w,detail) VALUES(111,'ERROR',200,'do-not-expose-raw')")
    db.execute("INSERT INTO marstek_control_events(ts,event,value_w,detail) VALUES(112,'TARGET_CHANGED',350,'Autolade-Ziel von 200 W auf 350 W geändert')")
   entries=decision_log(path)
   self.assertIn('Autolade-Ziel',entries[0]['text']);self.assertEqual(entries[1]['kind'],'error');self.assertNotIn('do-not-expose',str(entries))
   self.assertIn('200 W bestätigt',entries[2]['text']);self.assertEqual(entries[3]['text'],'Dauerlastschutz aktiviert');self.assertEqual(entries[4]['text'],'Autoladen erkannt')
   response=client.get('/api/marstek/decisions');self.assertEqual(response.status_code,200)
   self.assertEqual(response.headers['Cache-Control'],'no-store')
   html=client.get('/').text;self.assertLess(html.index('decisions-list'),html.index('system-summary'))
   with connect(path) as db:
    db.executemany("INSERT INTO marstek_control_events(ts,event,value_w) VALUES(?,'REQUEST',200)",[(n,) for n in range(200,300)])
   self.assertEqual(len(decision_log(path)),50)
