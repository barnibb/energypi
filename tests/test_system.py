import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from webapp import create_app
from database import save, FIELDS
from system_status import SystemStatus

class SystemTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.db'
        self.client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
        self.status=SystemStatus(self.path,'1.1.0')

    def test_empty_and_endpoint(self):
        data=self.client.get('/api/system')
        self.assertEqual(data.status_code,200)
        self.assertEqual(data.headers['Cache-Control'],'no-store')
        self.assertEqual(data.json['items'][0]['level'],'error')
        self.assertEqual(data.json['items'][-1]['label'],'Noch keine Messdaten')

    def test_success_error_and_stale(self):
        save(self.path,100,dict.fromkeys(FIELDS,1))
        self.assertEqual(self.status.read(110)['items'][0]['level'],'ok')
        self.assertEqual(self.status.read(121)['items'][1]['level'],'error')
        save(self.path,125,error='secret-token-in-url')
        data=self.status.read(126)
        self.assertEqual(data['items'][0]['level'],'error')
        self.assertEqual(data['items'][1]['level'],'ok')
        self.assertNotIn('secret-token',str(data))

    def test_storage_cached(self):
        with patch('system_status.shutil.disk_usage',return_value=type('Usage',(),{'free':1234})()) as usage:
            self.status.read(100)
            self.status.read(101)
            self.assertEqual(usage.call_count,1)

    def test_failed_backup_displays_attempt_instead_of_previous_success(self):
        from backup_status import record
        record(self.path,'success',100)
        record(self.path,'failure',200)
        item=next(item for item in self.status.read(201)['items'] if item['name']=='Mac-Sicherung')
        self.assertEqual(item['last_success'],200)
        self.assertEqual(item['label'],'Letzter Versuch fehlgeschlagen')
        self.assertIn('letzte erfolgreiche Kopie bleibt erhalten',item['error'])

    def test_marstek_real_status(self):
        from marstek import collect
        collect(self.path,{},lambda _:dict(soc=80,ac_power_w=200,battery_power_w=-230,battery_voltage_v=53,ac_voltage_v=230),100)
        item=self.status.read(110)['items'][-1]
        self.assertEqual(item['level'],'ok');self.assertEqual(item['last_success'],100)
        self.assertEqual(self.status.read(191)['items'][-1]['level'],'warn')
        def fail(_):raise OSError('secret-do-not-publish')
        collect(self.path,{},fail,200)
        item=self.status.read(201)['items'][-1]
        self.assertEqual(item['level'],'error');self.assertEqual(item['last_success'],100)
        self.assertNotIn('secret-do-not-publish',str(item))

    def test_manual_override_neutral_but_real_errors_warn(self):
        from marstek import collect
        from marstek_control import control_status,persist
        collect(self.path,{},lambda _:dict(soc=80,ac_power_w=-2500,battery_power_w=2300,battery_voltage_v=53,ac_voltage_v=230),100)
        for message,conflict in [('Automatik pausiert: Eigenverbrauchsmodus erforderlich.',False),('Manuelle/externe Vorgabe aktiv · Automatik pausiert während dieser Betriebsart.',False),('Externe Änderung erkannt',True)]:
            state=control_status(self.path);state.update(message=message,conflict=conflict);persist(self.path,state,100)
            item=self.status.read(110)['items'][-1]
            self.assertEqual(item['level'],'neutral');self.assertIsNone(item['error'])
            self.assertIn('Manuelle Vorgabe aktiv',item['label'])
        state.update(message='Begrenzung nicht bestätigt: TimeoutError',conflict=False);persist(self.path,state,110)
        self.assertEqual(self.status.read(111)['items'][-1]['level'],'warn')

    def test_retention_inventory_is_shown_without_claiming_deletion(self):
        from maintenance import write_maintenance_status
        payload={'version':2,'outcome':'success','last_success':100,'duration_seconds':3,
                 'archived_minutes':0,'remaining_old_measurements':0,'journal_deleted':0,'journal_remaining':0,
                 'retention':{'version':1,'generated_at':100,'seconds_since_previous':None,'tables':{
                     'measurements':{'rows':123,'rows_since_previous':None},
                     'minute_archive':{'rows':45,'rows_since_previous':None},
                     'marstek_samples':{'rows':67,'rows_since_previous':None}}}}
        write_maintenance_status(self.path,payload,100)
        item=next(item for item in self.status.read(101)['items'] if item['name']=='Datenaufbewahrung')
        self.assertEqual(item['level'],'neutral');self.assertIn('Shelly roh 123',item['label'])
        self.assertIn('Originaldaten',item['error'])
