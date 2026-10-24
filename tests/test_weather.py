import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from weather import initialize_weather, normalize, collect, collect_sevilla, weather_status
from database import connect

class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db';initialize_weather(self.path)
        self.data={'current_units':{'temperature_2m':'°C','time':'unixtime'},'current':{'time':9000,'temperature_2m':-2.4}}
    def test_persistence_and_duplicate_attempt(self):
        fetch=Mock(return_value=self.data)
        collect(self.path,9100,fetch);collect(self.path,9200,fetch)
        self.assertEqual(fetch.call_count,1)
        result=weather_status(self.path,9200)
        self.assertFalse(result['stale']);self.assertEqual(result['sample']['temperature_c'],-2.4)
        with connect(self.path) as db:self.assertEqual(db.execute('select count(*) from weather_samples').fetchone()[0],1)
    def test_bad_data(self):
        for value in (None,True,float('nan'),float('inf'),-100,80):
            self.data['current']['temperature_2m']=value
            with self.assertRaises(ValueError):normalize(self.data,9100)
    def test_sevilla_is_stored_independently(self):
        fetch=Mock(return_value=self.data)
        collect_sevilla(self.path,9100,fetch);collect_sevilla(self.path,9200,fetch)
        self.assertEqual(fetch.call_count,1)
        result=weather_status(self.path,9200)['sevilla']
        self.assertFalse(result['stale']);self.assertEqual(result['sample']['temperature_c'],-2.4)
        self.assertAlmostEqual(result['sample']['latitude'],37.38620512)
    def test_stale_and_future_timestamp(self):
        for stamp in (0,10000):
            self.data['current']['time']=stamp
            with self.assertRaises(ValueError):normalize(self.data,9100)
    def test_failed_fetch_preserves_last_and_expires(self):
        collect(self.path,9100,lambda:self.data)
        collect(self.path,10000,Mock(side_effect=OSError()))
        result=weather_status(self.path,10001)
        self.assertIsNotNone(result['error']);self.assertEqual(result['sample']['valid_at'],9000)
        self.assertTrue(weather_status(self.path,13000)['stale'])
    def test_api_empty(self):
        from webapp import create_app
        client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
        response=client.get('/api/weather')
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.json['sample']);self.assertTrue(response.json['stale'])
        self.assertEqual(response.headers['Cache-Control'],'no-store')
