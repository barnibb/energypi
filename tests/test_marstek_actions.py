import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from marstek import initialize_marstek
from database import connect
from marstek_actions import request_mode,process,action_status,update
from marstek_control import control_status,persist
from preferences import initialize_preferences
from tests.test_marstek_control import FakeDevice

class ActionsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'db';initialize_marstek(self.path);initialize_preferences(self.path)
  self.device=FakeDevice();self.device.mode=0
  self.device.set_self_consumption=lambda:setattr(self.device,'mode',1)
 def run_action(self,now=100,active=False,stale=False):
  with patch('marstek_actions.charging_status',return_value={'stale':stale,'state':{'active':active}}):
   return process(self.path,self.device,now)
 def test_request_deduplicated_and_mode_confirmed(self):
  first=request_mode(self.path,100);self.assertEqual(request_mode(self.path,101)['id'],first['id'])
  self.run_action();self.assertEqual(self.device.mode,1);self.assertEqual(action_status(self.path)['status'],'done')
 def test_cap_before_mode(self):
  request_mode(self.path,100)
  def switch():
   self.assertEqual(self.device.limit,200);self.device.mode=1
  self.device.set_self_consumption=switch
  self.run_action(active=True)
  self.assertEqual(control_status(self.path)['baseline'],800)
  self.assertEqual(self.device.writes,[200])
 def test_explicit_request_ignores_automatic_interval_but_waits_for_fresh_detection(self):
  request_mode(self.path,100);state=control_status(self.path);state['last_attempt']=99;persist(self.path,state,99)
  self.run_action();self.assertEqual(self.device.mode,1)
  request_mode(self.path,1000);self.device.mode=0;self.run_action(1000,stale=True);self.assertEqual(self.device.mode,0)
  self.run_action(1001);self.assertEqual(self.device.mode,1)
 def test_explicit_request_restores_known_baseline_immediately(self):
  state=control_status(self.path);state.update(baseline=800,applied=0,observed_limit_w=0,last_attempt=99);persist(self.path,state,99)
  self.device.limit=0;request_mode(self.path,100);self.run_action(100)
  self.assertEqual(self.device.limit,800);self.assertEqual(self.device.mode,1)
  state=control_status(self.path);self.assertIsNone(state['baseline']);self.assertIsNone(state['applied'])
  self.assertEqual(action_status(self.path)['message'],'Eigenverbrauch bestätigt')
 def test_explicit_request_keeps_soc_protection_while_restoring(self):
  state=control_status(self.path);state.update(baseline=800,applied=0,observed_limit_w=0);persist(self.path,state,99)
  self.device.limit=0
  with connect(self.path) as db:db.execute('INSERT INTO marstek_samples VALUES (?,?,?,?,?,?,?)',(100,30,0,0,52,230,None))
  request_mode(self.path,100);self.run_action(100)
  self.assertEqual(self.device.limit,100);self.assertEqual(control_status(self.path)['baseline'],800)
 def test_crash_does_not_replay(self):
  item=request_mode(self.path,100);update(self.path,item,'processing','test',100)
  self.run_action();self.assertEqual(self.device.mode,0);self.assertEqual(action_status(self.path)['status'],'error')
 def test_rs485_not_overridden(self):
  request_mode(self.path,100);self.device.rs485=21930;self.run_action()
  self.assertEqual(self.device.mode,0);self.assertEqual(action_status(self.path)['status'],'error')
 def test_endpoint_guard_and_no_device_access(self):
  from webapp import create_app
  client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
  url='/api/marstek/self-consumption'
  self.assertEqual(client.post(url,json={}).status_code,403)
  with patch('socket.create_connection',side_effect=AssertionError('network')):
   self.assertEqual(client.post(url,json={},headers={'X-EnergyPi':'settings'}).status_code,202)
  self.assertIn('id="marstek-self"',client.get('/').text)
 def test_mode_packet_is_only_self_consumption(self):
  import struct
  from unittest.mock import Mock
  from marstek_control import Device
  packet=struct.pack('>HHHBBHH',4,0,6,1,6,43000,1)
  sock=Mock();sock.recv.side_effect=[packet[:7],packet[7:]]
  with patch('marstek_control.socket.create_connection') as connector:
   connector.return_value.__enter__.return_value=sock
   Device(dict(host='test',port=502,unit=1)).set_self_consumption()
  sock.sendall.assert_called_once_with(packet)
