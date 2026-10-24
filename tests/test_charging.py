import tempfile
import unittest
from pathlib import Path
from charging import ChargingRecorder, charging_status

RULE = dict(block_above_w=3000, release_below_w=2000, hold_seconds=180, max_gap_seconds=15)

class ChargingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        self.rec = ChargingRecorder(self.path, RULE)

    def sample(self, power, t):
        return self.rec.update(power, 1000+t, t)

    def test_start_end_and_no_duplicate(self):
        for t in range(0,180,5):
            self.assertIsNone(self.sample(4000,t))
        self.assertEqual(self.sample(4000,180),'START_DETECTED')
        self.sample(4000,185)
        status=charging_status(self.path,1185)
        self.assertEqual(len(status['events']),1)
        self.assertEqual(status['events'][0]['condition_since'],1000)
        self.assertTrue(status['state']['active'])
        for t in range(190,370,5): self.sample(1000,t)
        self.assertEqual(self.sample(1000,370),'END_DETECTED')
        self.assertFalse(charging_status(self.path,1370)['state']['active'])

    def test_gap_and_invalid_reset_qualification(self):
        for t in range(0,175,5): self.sample(4000,t)
        self.sample(None,175)
        self.assertTrue(charging_status(self.path,1175)['stale'])
        self.sample(4000,180)
        self.sample(4000,210)
        self.assertEqual(charging_status(self.path,1210)['state']['remaining'],180)
        self.assertEqual(charging_status(self.path,1210)['events'],[])

    def test_restart_restores_state_but_not_timer(self):
        for t in range(0,185,5): self.sample(4000,t)
        self.sample(1000,185)
        self.rec=ChargingRecorder(self.path,RULE)
        self.sample(1000,500)
        state=charging_status(self.path,1500)['state']
        self.assertTrue(state['active'])
        self.assertEqual(state['remaining'],180)
        self.assertEqual(state['active_since'],1180)

    def test_threshold_and_staleness(self):
        self.assertTrue(charging_status(self.path,1000)['stale'])
        for t in range(0,200,5): self.sample(3000,t)
        status=charging_status(self.path,1195)
        self.assertFalse(status['stale'])
        self.assertFalse(status['state']['active'])
        self.assertIsNone(status['state']['pending'])
        self.assertTrue(charging_status(self.path,1216)['stale'])

    def test_api(self):
        from webapp import create_app
        client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
        result=client.get('/api/charging')
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.json['stale'])
        self.assertEqual(result.headers['Cache-Control'],'no-store')

    def test_corrected_power_and_duration_reason_are_stored(self):
        rule={**RULE,'block_above_w':3000,'sustained_discharge_w':750,'sustained_discharge_seconds':600}
        self.rec=ChargingRecorder(self.path,rule)
        for t in range(0,600,5):self.assertIsNone(self.rec.update(1590,1000+t,t,800))
        self.assertEqual(self.rec.update(1590,1600,600,800),'START_DETECTED')
        result=charging_status(self.path,1600)
        self.assertEqual(result['state']['net_power_w'],1590)
        self.assertEqual(result['state']['corrected_power_w'],2390)
        self.assertEqual(result['state']['reason'],'sustained_discharge')
        self.assertEqual(result['events'][0]['reason'],'sustained_discharge')

    def test_latest_battery_discharge_requires_fresh_valid_sample(self):
        from charging import latest_battery_discharge
        from database import connect
        self.assertIsNone(latest_battery_discharge(self.path,1000))
        with connect(self.path) as db:
            db.execute('CREATE TABLE marstek_samples(ts REAL PRIMARY KEY,soc REAL,ac_power_w REAL,battery_power_w REAL,battery_voltage_v REAL,ac_voltage_v REAL,error TEXT)')
            db.execute('INSERT INTO marstek_samples VALUES(?,?,?,?,?,?,?)',(950,50,797,-800,51,230,None))
        self.assertEqual(latest_battery_discharge(self.path,1000),797)
        self.assertIsNone(latest_battery_discharge(self.path,1041))

    def test_existing_tables_are_extended_without_losing_state(self):
        from charging import initialize_charging
        from database import connect
        other=Path(self.temp.name)/'old.db'
        with connect(other) as db:
            db.execute('CREATE TABLE charging_state(id INTEGER PRIMARY KEY,active INTEGER,updated_at REAL,valid INTEGER,active_since REAL,pending TEXT,remaining REAL,start_w REAL,stop_w REAL,hold_s REAL)')
            db.execute('CREATE TABLE charging_events(id INTEGER PRIMARY KEY,detected_at REAL,event TEXT,condition_since REAL,power_w REAL,start_w REAL,stop_w REAL,hold_s REAL)')
            db.execute("INSERT INTO charging_state VALUES(1,1,100,1,90,NULL,NULL,1600,1000,180)")
        initialize_charging(other)
        with connect(other) as db:
            row=db.execute('SELECT active,protection_w,protection_hold_s FROM charging_state').fetchone()
            columns={r['name'] for r in db.execute('PRAGMA table_info(charging_events)')}
        self.assertEqual(dict(row),{'active':1,'protection_w':750,'protection_hold_s':600})
        self.assertIn('reason',columns)
