from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from database import connect
from solaredge import parse_flow, initialize_solar, collect, solar_status, in_window, fetch_flow, ZONE
from webapp import create_app


def fixture(unit='kW'):
    return {'siteCurrentPowerFlow':{'unit':unit, 'PV':{'status':'Active','currentPower':2.5},
            'LOAD':{'status':'Active','currentPower':1.0},'GRID':{'status':'Active','currentPower':1.5},
            'connections':[{'from':'Load','to':'GRID'}]}}

class SolarEdgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'db.sqlite3'
        initialize_solar(self.path)
        self.now=datetime(2026,9,13,12,0,tzinfo=ZONE).timestamp()

    def test_units_and_directions(self):
        self.assertEqual(parse_flow(fixture()),{'pv_w':2500,'load_w':1000,'grid_w':-1500})
        f=fixture('W');f['siteCurrentPowerFlow']['connections']=[{'from':'GRID','to':'Load'}]
        self.assertEqual(parse_flow(f)['grid_w'],1.5)
        f['siteCurrentPowerFlow']['connections']=[]
        self.assertIsNone(parse_flow(f)['grid_w'])

    def test_bad_data_and_missing_optional_meter(self):
        for value in (None,True,'3',-1,float('nan')):
            f=fixture();f['siteCurrentPowerFlow']['PV']['currentPower']=value
            with self.assertRaises(ValueError):parse_flow(f)
        f=fixture();del f['siteCurrentPowerFlow']['LOAD'];del f['siteCurrentPowerFlow']['GRID']
        self.assertIsNone(parse_flow(f)['load_w'])
        for f in ({},fixture('MW')):
            with self.assertRaises(ValueError):parse_flow(f)

    def test_day_window_in_local_timezone(self):
        for hour,minute,expected in ((7,29,False),(7,30,True),(20,59,True),(21,0,False)):
            self.assertEqual(in_window(datetime(2026,9,13,hour,minute,tzinfo=ZONE).timestamp()),expected)

    def test_persisted_poll_reservation_and_status(self):
        calls=[]
        def fetch(site,key):
            calls.append(True)
            return parse_flow(fixture())
        collect(self.path,'123','not-a-real-key',self.now,fetch)
        collect(self.path,'123','not-a-real-key',self.now+1,fetch)
        self.assertEqual(len(calls),1)
        self.assertFalse(solar_status(self.path,self.now+10)['stale'])
        self.assertTrue(solar_status(self.path,self.now+1801)['stale'])
        def fail(site,key):raise ValueError('SolarEdge HTTP 403')
        collect(self.path,'123','not-a-real-key',self.now+900,fail)
        self.assertTrue(solar_status(self.path,self.now+910)['stale'])
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM solaredge_samples').fetchone()[0],2)

    def test_network_errors_do_not_disclose_key(self):
        for error in (HTTPError('https://example.test/?api_key=SECRET',403,'SECRET',{},None),URLError('SECRET')):
            with patch('solaredge.build_opener') as opener:
                opener.return_value.open.side_effect=error
                with self.assertRaises(ValueError) as caught:fetch_flow('123','SECRET')
                self.assertNotIn('SECRET',str(caught.exception))

    def test_web_reads_database_only(self):
        app=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}})
        with patch('solaredge.fetch_flow',side_effect=AssertionError('No cloud request from browser')):
            result=app.test_client().get('/api/solaredge')
        self.assertEqual(result.status_code,200)
        self.assertIsNone(result.json['sample'])

if __name__=='__main__':unittest.main()
