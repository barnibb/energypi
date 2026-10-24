import tempfile
import unittest
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from database import connect
from forecast import initialize_forecast
from grid_charging import initialize_grid_charging, manual_plan, request, request_status, process
from marstek import initialize_marstek
from preferences import initialize_preferences
from tibber import initialize_tibber

class GridChargingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db'
        initialize_marstek(self.path);initialize_tibber(self.path);initialize_forecast(self.path);initialize_preferences(self.path);initialize_grid_charging(self.path)
    def prices(self,now,soc=40):
        with connect(self.path) as db:
            db.execute('INSERT INTO marstek_samples VALUES (?,?,?,?,?,?,?)',(now,soc,0,0,52,230,None))
            db.execute("INSERT INTO tibber_meta VALUES(1,'home')")
            for i,ct in enumerate((30,18,20,35,40,42,38,36,34,33,32,31,30,29,28,27)):
                start=now+900+i*900
                db.execute("INSERT INTO tibber_prices VALUES('home',?,?,?,?,?,'EUR',?)",(start,start+900,ct/100,0,0,now))
    def spec(self,**changes):
        value={'start_mode':'now','target_mode':'energy','energy_kwh':1,'power_w':500}
        value.update(changes);return value
    def test_manual_preview_and_request_are_live_capable(self):
        now=1760173200;self.prices(now)
        value=manual_plan(self.path,self.spec(),now)
        self.assertTrue(value['available']);self.assertEqual(value['slot'],6);self.assertTrue(value['manual'])
        self.assertEqual(value['power_w'],500);self.assertGreater(value['end'],value['start']);self.assertLessEqual(value['start'],now)
        result=request(self.path,self.spec(),now)
        self.assertTrue(result['live_writes']);self.assertEqual(result['request']['status'],'confirmed')
        self.assertNotIn('proposal',result)
        with self.assertRaises(ValueError):request(self.path,self.spec(),now)
        self.assertEqual(request_status(self.path,now+301)['request']['status'],'expired')

    def test_delay_and_concrete_time_are_supported(self):
        now=1760173200;self.prices(now)
        delayed=manual_plan(self.path,self.spec(start_mode='delay',delay_hours=2,target_mode='duration',duration_hours=.5),now)
        exact=datetime.fromtimestamp(now+3600,ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%dT%H:%M')
        timed=manual_plan(self.path,self.spec(start_mode='at',start_at=exact),now)
        self.assertGreaterEqual(delayed['start'],now+7200);self.assertAlmostEqual(timed['start'],now+3600,delta=60)

    def test_manual_input_is_validated(self):
        now=1760173200;self.prices(now)
        for spec in (self.spec(power_w=525),self.spec(energy_kwh=0),self.spec(start_mode='delay',delay_hours=25),self.spec(target_mode='duration',duration_hours=0)):
            with self.assertRaises(ValueError):manual_plan(self.path,spec,now)

    def test_manual_api_requires_header_and_returns_preview(self):
        from webapp import create_app
        now=time.time();self.prices(now)
        client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
        self.assertEqual(client.post('/api/grid-charge/preview',json=self.spec()).status_code,403)
        response=client.post('/api/grid-charge/preview',json=self.spec(),headers={'X-EnergyPi':'settings'})
        self.assertEqual(response.status_code,200);self.assertTrue(response.json['manual'])
        created=client.post('/api/grid-charge',json=self.spec(),headers={'X-EnergyPi':'settings'})
        self.assertEqual(created.status_code,200);self.assertEqual(created.json['request']['status'],'confirmed')

    def test_confirmed_request_configures_slot_and_returns_to_self_consumption(self):
        class Device:
            def __init__(self):self.mode=1;self.rs485=21947;self.schedules={i:(0,0,0,0,0) for i in range(1,7)}
            def read(self):return 100,self.mode,self.rs485
            def read_schedule(self,slot):return self.schedules[slot]
            def write_schedule_six(self,days,start,end,power,enabled):self.schedules[6]=(days,start,end,power&0xffff,enabled)
            def set_manual(self):self.mode=0
            def set_self_consumption(self):self.mode=1
            def disable_schedule_six(self):self.schedules[6]=(*self.schedules[6][:4],0)
            def clear_schedule_six(self):self.schedules[6]=(0,0,0,0,0)
        now=1760173200;self.prices(now);request(self.path,self.spec(start_mode='delay',delay_hours=.25),now);device=Device()
        self.assertTrue(process(self.path,device,now));self.assertEqual(device.mode,1);self.assertEqual(request_status(self.path,now)['request']['status'],'scheduled')
        start=request_status(self.path,now)['request']['proposal']['start']
        self.assertTrue(process(self.path,device,start));self.assertEqual(device.mode,0);self.assertEqual(request_status(self.path,start)['request']['status'],'active')
        end=request_status(self.path,now)['request']['proposal']['end']
        self.assertTrue(process(self.path,device,end));self.assertEqual(device.mode,1);self.assertEqual(device.schedules[6],(0,0,0,0,0))
        self.assertEqual(request_status(self.path,end)['request']['status'],'done')

    def test_overlapping_app_schedule_blocks_start(self):
        class Device:
            mode=1;rs485=21947
            def read(self):return 100,self.mode,self.rs485
            def read_schedule(self,slot):return (127,0,2359,65036,1) if slot==1 else (0,0,0,0,0)
        now=1760173200;self.prices(now);request(self.path,self.spec(),now);process(self.path,Device(),now)
        self.assertEqual(request_status(self.path,now)['request']['status'],'error')
        self.assertIn('überschneidet',request_status(self.path,now)['request']['message'])

    def test_inactive_slot_six_with_old_values_can_be_reused(self):
        class Device:
            def __init__(self):self.mode=1;self.schedules={i:(0,0,0,0,0) for i in range(1,7)};self.schedules[6]=(64,0,0,64536,0)
            def read(self):return 100,self.mode,21947
            def read_schedule(self,slot):return self.schedules[slot]
            def write_schedule_six(self,days,start,end,power,enabled):self.schedules[6]=(days,start,end,power&0xffff,enabled)
            def set_manual(self):self.mode=0
        now=1760173200;self.prices(now);request(self.path,self.spec(),now);device=Device();process(self.path,device,now)
        self.assertEqual(request_status(self.path,now)['request']['status'],'active')
        self.assertEqual(device.mode,0);self.assertEqual(device.schedules[6][4],1)

    def test_external_schedule_change_is_reported_without_writes(self):
        class Device:
            def __init__(self):self.mode=1;self.schedule=(0,0,0,0,0);self.writes=[]
            def read(self):return 100,self.mode,21947
            def read_schedule(self,slot):return self.schedule
            def write_schedule_six(self,days,start,end,power,enabled):self.schedule=(days,start,end,power&0xffff,enabled);self.writes.append('schedule')
            def set_manual(self):self.mode=0;self.writes.append('manual')
            def set_self_consumption(self):self.mode=1;self.writes.append('self')
            def clear_schedule_six(self):self.schedule=(0,0,0,0,0);self.writes.append('clear')
        now=1760173200;self.prices(now);request(self.path,self.spec(),now);device=Device();process(self.path,device,now)
        self.assertEqual(request_status(self.path,now)['request']['status'],'active')
        device.writes.clear();device.schedule=(64,1300,1515,64536,1)
        process(self.path,device,now+30)
        item=request_status(self.path,now+30)['request']
        self.assertEqual(item['status'],'error');self.assertIn('extern verändert',item['message']);self.assertEqual(device.writes,[])
