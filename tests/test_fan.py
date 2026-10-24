import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fan import initialize_fan,state,select_device,observe,request_action,expire,status,acknowledge
from preferences import initialize_preferences,save_preferences,DEFAULTS
from fan_worker import reconcile

class Device:
 def __init__(self,name='Lüfter Bad',uuid='one',on=False):self.name=name;self.uuid=uuid;self.on=on;self.calls=[]
 async def async_update(self):pass
 def is_on(self,channel=0):return self.on
 async def async_turn_on(self,channel=0):self.calls.append('on');self.on=True
 async def async_turn_off(self,channel=0):self.calls.append('off');self.on=False

class FanTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'db'
  initialize_preferences(self.path);initialize_fan(self.path)
 def ready(self,on=False):
  d=Device(on=on);select_device(self.path,[d]);observe(self.path,on,100);return d
 def test_identity_pinned_and_ambiguous(self):
  with self.assertRaises(ValueError):select_device(self.path,[Device(),Device(uuid='two')])
  self.ready()
  with self.assertRaises(ValueError):select_device(self.path,[Device(uuid='two')])
  self.assertEqual(select_device(self.path,[Device(name='Renamed')]).uuid,'one')
 def test_deadline_restart_and_duration_change(self):
  self.ready();request_action(self.path,'start',100)
  save_preferences(self.path,{**DEFAULTS,'fan_minutes':5},5)
  initialize_fan(self.path)
  self.assertEqual(state(self.path)['deadline'],1300)
  expire(self.path,1301);self.assertEqual(state(self.path)['desired'],0)
  self.assertIsNone(state(self.path)['deadline'])
 def test_stale_start_rejected_stop_allowed(self):
  self.ready()
  with self.assertRaises(ValueError):request_action(self.path,'start',300)
  request_action(self.path,'stop',300);self.assertEqual(state(self.path)['desired'],0)
 def test_expired_never_switches_on(self):
  d=self.ready();request_action(self.path,'start',100)
  with patch('fan_worker.time.time',return_value=1301):asyncio.run(reconcile(self.path,d))
  self.assertEqual(d.calls,[]);self.assertIsNone(state(self.path)['desired'])
 def test_switch_on_and_confirmed_off(self):
  d=self.ready();request_action(self.path,'start',100)
  with patch('fan_worker.time.time',return_value=101):asyncio.run(reconcile(self.path,d))
  self.assertEqual(d.calls,['on'])
  with patch('fan_worker.time.time',return_value=1301):asyncio.run(reconcile(self.path,d))
  self.assertEqual(d.calls,['on','off'])
 def test_old_ack_does_not_clear_new_command(self):
  self.ready();request_action(self.path,'stop',100);old=state(self.path)['revision']
  request_action(self.path,'start',101);acknowledge(self.path,old)
  self.assertEqual(state(self.path)['desired'],1)
 def test_off_failure_keeps_pending(self):
  class Failed(Device):
   async def async_turn_off(self,channel=0):raise OSError()
  d=Failed(on=True);select_device(self.path,[d]);request_action(self.path,'stop',100)
  with self.assertRaises(OSError):asyncio.run(reconcile(self.path,d))
  self.assertEqual(state(self.path)['desired'],0)
 def test_endpoint_and_default(self):
  from webapp import create_app
  client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
  self.assertEqual(client.get('/api/fan').json['duration_minutes'],20)
  self.assertEqual(client.post('/api/fan',json={'action':'start'}).status_code,403)
  self.assertEqual(client.post('/api/fan',json={'action':'start'},headers={'X-EnergyPi':'settings'}).status_code,400)
 def test_diagnostics_exclude_secrets(self):
  from fan_worker import safe_error
  message=safe_error('Meross-Anmeldung (EU)',ValueError('password=secret&token=private'))
  self.assertEqual(message,'Meross-Anmeldung (EU): ValueError')
  self.assertNotIn('secret',message)
