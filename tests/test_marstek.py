import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from marstek import initialize_marstek, fetch, collect, status, read_registers
from database import connect
from preferences import read_preferences

class MarstekTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'test.db'; initialize_marstek(self.path)
        self.values = dict(soc=91, ac_power_w=797, battery_power_w=-888,
                           battery_voltage_v=53.29, ac_voltage_v=233.5)

    def test_decoding_both_directions(self):
        for ac_power, battery_power in ((797,-888),(-500,450)):
            with patch('marstek.socket.create_connection'), patch('marstek.read_registers', side_effect=[
                struct.pack('>HhiH',5329,-1667,battery_power,91),struct.pack('>HhiH',2335,347,ac_power,5003)]):
                data=fetch(dict(host='test',port=502,unit=1))
            self.assertEqual(data['ac_power_w'],ac_power)
            self.assertEqual(data['battery_power_w'],battery_power)
            self.assertEqual(data['soc'],91)
            self.assertEqual(data['battery_voltage_v'],53.29)

    def test_fragmented_read_and_read_only_request(self):
        sock=Mock(); raw=struct.pack('>HHHB',1,0,5,1)+b'\x03\x02\x00\x5b'
        sock.recv.side_effect=[bytes([v]) for v in raw]
        self.assertEqual(read_registers(sock,1,1,32104,1),b'\x00\x5b')
        self.assertEqual(sock.sendall.call_args.args[0],struct.pack('>HHHBBHH',1,0,6,1,3,32104,1))

    def test_reject_bad_transaction_exception_and_truncated_connection(self):
        for parts in ([struct.pack('>HHHB',9,0,5,1)],
                      [struct.pack('>HHHB',1,0,3,1),b'\x83\x02'], [b'']):
            sock=Mock(); sock.recv.side_effect=parts
            with self.assertRaises((ValueError,ConnectionError)):
                read_registers(sock,1,1,32104,1)

    def test_persistence_failure_and_staleness(self):
        self.assertTrue(status(self.path,100)['stale'])
        collect(self.path,{},lambda _:self.values,100)
        self.assertFalse(status(self.path,110)['stale'])
        self.assertTrue(status(self.path,191)['stale'])
        collect(self.path,{},Mock(side_effect=TimeoutError('Timeout')),120)
        data=status(self.path,121)
        self.assertTrue(data['stale']); self.assertEqual(data['sample']['soc'],91)
        with connect(self.path) as db:
            row=db.execute('SELECT * FROM marstek_samples WHERE ts=120').fetchone()
            self.assertIsNone(row['ac_power_w']); self.assertIn('Timeout',row['error'])
        collect(self.path,{},lambda _:self.values,130)
        self.assertFalse(status(self.path,131)['stale'])

    def test_api_does_not_contact_device(self):
        from webapp import create_app
        with patch('marstek.socket.create_connection',side_effect=AssertionError('network')):
            client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
            response=client.get('/api/marstek')
            self.assertEqual(response.status_code,200); self.assertTrue(response.json['stale'])
            self.assertEqual(client.post('/api/marstek').status_code,405)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertIn('marstek-soc',client.get('/').text)
            self.assertIn('marstek-soc-ring',client.get('/').text)
            self.assertIn('id="battery-summary"',client.get('/').text)
            self.assertNotIn('Noch nicht angebunden',client.get('/').text)
            html=client.get('/').text
            self.assertIn('id="grid-charge-open"',html)
            self.assertIn('id="grid-charge-dialog"',html)
            self.assertNotIn('id="grid-charge-confirm"',html)
            self.assertIn('id="solar-pv"',html)
            observation=html[html.index('aria-label="Kosten-Beobachtungsmodus"'):]
            self.assertNotIn('id="grid-charge-box"',observation)

    def test_discharge_target_endpoint_is_guarded_validated_and_audited(self):
        from webapp import create_app
        client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
        self.assertEqual(client.get('/api/marstek').json['discharge_target_w'],200)
        self.assertEqual(client.post('/api/marstek/discharge-target',json={'value_w':350}).status_code,403)
        headers={'X-EnergyPi':'settings'}
        self.assertEqual(client.post('/api/marstek/discharge-target',json={'value_w':325},headers=headers).status_code,400)
        response=client.post('/api/marstek/discharge-target',json={'value_w':350},headers=headers)
        self.assertEqual(response.status_code,200);self.assertEqual(response.json['value_w'],350)
        self.assertEqual(read_preferences(self.path)['ev_discharge_limit_w'],350)
        with connect(self.path) as db:
            row=db.execute("SELECT event,value_w,detail FROM marstek_control_events WHERE event='TARGET_CHANGED'").fetchone()
        self.assertEqual(row['value_w'],350);self.assertIn('200 W auf 350 W',row['detail'])
        self.assertEqual(client.get('/api/marstek').json['discharge_target_w'],350)
