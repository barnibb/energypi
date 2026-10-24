import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
from marstek import initialize_marstek
from marstek_control import step,control_status
from preferences import initialize_preferences,read_preferences,save_preferences
from charging import initialize_charging
from database import connect

class FakeDevice:
    def __init__(self): self.limit=800; self.mode=1; self.rs485=21947; self.writes=[]; self.fail=False
    def read(self): return self.limit,self.mode,self.rs485
    def write_limit(self,value):
        self.writes.append(value);self.limit=value
        if self.fail: raise TimeoutError('Antwort verloren')

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db';initialize_marstek(self.path);initialize_preferences(self.path);initialize_charging(self.path)
        self.device=FakeDevice()
    def tick(self,now,active=True,stale=False):
        with patch('marstek_control.charging_status',return_value={'state':{'active':active},'stale':stale}):
            return step(self.path,self.device,now)
    def soc(self,now,value):
        with connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO marstek_samples(ts,soc,ac_power_w,battery_power_w,battery_voltage_v,ac_voltage_v,error) VALUES(?,?,?,?,?,?,?)',(now,value,0,0,51,230,None))
    def test_cap_and_restore_with_persisted_interval(self):
        self.tick(100);self.assertEqual(self.device.writes,[200])
        self.tick(200,False);self.assertEqual(self.device.limit,200)
        self.tick(1000,False);self.assertEqual(self.device.writes,[200,800])
        self.assertIsNone(control_status(self.path)['baseline'])
        self.tick(1001);self.assertEqual(self.device.limit,200) # neuer Schutz senkt sofort
        self.tick(1900);self.assertEqual(self.device.limit,200)
    def test_unknown_holds_limit(self):
        self.tick(100,stale=True);self.assertEqual(self.device.writes,[])
        self.tick(101);self.tick(2000,False,True);self.assertEqual(self.device.limit,200)
    def test_lost_ack_is_reconciled_without_second_write(self):
        self.device.fail=True;self.tick(100)
        self.assertEqual(control_status(self.path)['pending'],200)
        self.tick(101);self.assertEqual(self.device.writes,[200])
        self.assertIsNone(control_status(self.path)['pending'])
    def test_external_change_pauses_and_does_not_restore(self):
        self.tick(100);self.device.limit=100
        self.assertTrue(self.tick(1000,False)['conflict'])
        self.tick(2000,False);self.assertEqual(self.device.writes,[200])
    def test_lower_existing_limit_not_raised(self):
        self.device.limit=100;self.tick(100);self.tick(1100,False)
        self.assertEqual(self.device.writes,[])
    def test_modes_not_taken_over(self):
        self.device.mode=0;self.tick(100)
        self.device.mode=1;self.device.rs485=21930;self.tick(1100)
        self.assertEqual(self.device.writes,[])
    def test_configured_limit_and_clock_reversal(self):
        save_preferences(self.path,{**read_preferences(self.path),'ev_discharge_limit_w':350},5)
        self.tick(1000);self.assertEqual(self.device.limit,350)
        self.tick(500,False);self.assertEqual(self.device.writes,[350])
    def test_validation_and_old_preferences(self):
        for value in (201,801,-50,True):
            with self.assertRaises(ValueError):save_preferences(self.path,{**read_preferences(self.path),'ev_discharge_limit_w':value},5)
    def test_write_whitelist_and_echo(self):
        import struct
        from unittest.mock import Mock
        from marstek_control import Device
        packet=struct.pack('>HHHBBHH',4,0,6,1,6,44003,200)
        sock=Mock();sock.recv.side_effect=[packet[:7],packet[7:]]
        with patch('marstek_control.socket.create_connection') as connector:
            connector.return_value.__enter__.return_value=sock
            Device(dict(host='test',port=502,unit=1)).write_limit(200)
        sock.sendall.assert_called_once_with(packet)
        for value in (-1,3000,200.5,True):
            with self.assertRaises(ValueError):Device({}).write_limit(value)
    def test_schedule_six_is_disabled_filled_enabled_and_verified(self):
        from unittest.mock import Mock,call,patch
        from marstek_control import Device
        device=Device({});device._write=Mock();device.read_schedule=Mock(return_value=(64,1200,1230,65036,1))
        with patch('marstek_control.time.sleep'):
            device.write_schedule_six(64,1200,1230,-500,1)
        self.assertEqual(device._write.call_args_list,[call(43129,0),call(43125,64),call(43126,1200),call(43127,1230),call(43128,65036),call(43129,1)])
    def test_schedule_read_uses_modbus_reader(self):
        import struct
        from unittest.mock import Mock,patch
        from marstek_control import Device
        sock=Mock();reply=struct.pack('>HHHHH',64,1200,1230,65036,1)
        with patch('marstek_control.socket.create_connection') as connector, patch('marstek.read_registers',return_value=reply) as reader:
            connector.return_value.__enter__.return_value=sock
            result=Device(dict(host='test',port=502,unit=1)).read_schedule(6)
        self.assertEqual(result,(64,1200,1230,65036,1))
        reader.assert_called_once_with(sock,16,1,43125,5)
    def test_soc_profile_lowers_immediately_and_rises_after_interval(self):
        self.soc(100,59);self.tick(100,False)
        self.assertEqual(self.device.writes,[300])
        self.soc(200,61);self.tick(200,False)
        self.assertEqual(self.device.limit,300) # 3 percentage point hysteresis
        self.soc(300,63);self.tick(300,False)
        self.assertEqual(self.device.limit,300) # increases still obey 15 minutes
        self.soc(1000,63);self.tick(1000,False)
        self.assertEqual(self.device.writes,[300,800])
    def test_soc_low_and_reserve_use_verified_100_w_floor(self):
        now=datetime(2026,9,26,12,0,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
        self.soc(now,35);self.tick(now,False);self.assertEqual(self.device.limit,100)
        self.soc(now+100,15);self.tick(now+100,False)
        self.assertEqual(self.device.limit,100)
        self.assertEqual(control_status(self.path)['soc_band'],'reserve')
    def test_soc_cap_wins_over_autoload_target(self):
        now=datetime(2026,9,26,12,0,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
        self.soc(now,70);self.tick(now,True)
        self.assertEqual(self.device.limit,200)
        self.soc(now+100,35);self.tick(now+100,True) # SOC reduction bypasses recent EV write
        state=control_status(self.path)
        self.assertEqual(self.device.limit,100)
        self.assertEqual(state['effective_reason'],'night_reserve')
    def test_night_supply_uses_energy_budget_average(self):
        now=datetime(2026,9,26,23,0,tzinfo=ZoneInfo('Europe/Berlin')).timestamp();self.soc(now,35)
        state=self.tick(now,False)
        self.assertEqual(self.device.limit,250);self.assertEqual(state['effective_reason'],'night_supply')
    def test_stale_soc_never_raises_previous_cap(self):
        self.soc(100,59);self.tick(100,False);self.assertEqual(self.device.limit,300)
        self.tick(2000,False)
        self.assertEqual(self.device.writes,[300])
        self.assertTrue(control_status(self.path)['soc_stale'])
    def test_morning_comfort_overrides_soc_cap_then_returns_to_safety(self):
        now=datetime(2026,9,26,6,0,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
        self.soc(now,15)
        status={'state':{'active':False,'reason':None,'corrected_power_w':500},'stale':False}
        with patch('marstek_control.charging_status',return_value=status):state=step(self.path,self.device,now)
        self.assertTrue(state['morning']['active']);self.assertEqual(state['effective_target_w'],800)
        self.soc(now+4*3600+1,15);status['state']['corrected_power_w']=100
        with patch('marstek_control.charging_status',return_value=status):state=step(self.path,self.device,now+4*3600+1)
        self.assertFalse(state['morning']['active']);self.assertEqual(self.device.limit,100)
    def test_autoload_still_overrides_full_morning_release(self):
        now=datetime(2026,9,26,6,0,tzinfo=ZoneInfo('Europe/Berlin')).timestamp();self.soc(now,50)
        status={'state':{'active':True,'reason':'corrected_load','corrected_power_w':3000},'stale':False}
        with patch('marstek_control.charging_status',return_value=status):state=step(self.path,self.device,now)
        self.assertTrue(state['morning']['active']);self.assertEqual(self.device.limit,200);self.assertEqual(state['effective_reason'],'ev_limit')
    def test_hard_soc_floor_stops_discharge(self):
        now=datetime(2026,9,26,6,0,tzinfo=ZoneInfo('Europe/Berlin')).timestamp();self.soc(now,12)
        self.tick(now,False);self.assertEqual(self.device.limit,0)
