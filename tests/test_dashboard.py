import tempfile
from pathlib import Path
from datetime import date
import unittest
from unittest.mock import patch
from collector import validate
from database import FIELDS, initialize, save, recent_average, history
from webapp import create_app, day_bounds

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        initialize(self.path)
        self.values = dict.fromkeys(FIELDS, 100.0)
        self.client = create_app({'database_path':self.path, 'shelly':{'poll_seconds':5}}).test_client()

    def test_invalid_sensor_data(self):
        for value in (None, True, float('nan'), float('inf'), '100'):
            with self.assertRaises(ValueError):
                validate({**self.values, 'id':0, 'a_voltage':value})
        self.assertEqual(validate({**self.values,'id':0}), self.values)

    def test_empty_and_stale_status(self):
        self.assertTrue(self.client.get('/api/status').json['stale'])
        save(self.path, 100, self.values)
        with patch('webapp.time.time', return_value=110):
            self.assertFalse(self.client.get('/api/status').json['stale'])
        with patch('webapp.time.time', return_value=121):
            self.assertTrue(self.client.get('/api/status').json['stale'])
        save(self.path, 111, error='timeout')
        with patch('webapp.time.time', return_value=112):
            result=self.client.get('/api/status').json
            self.assertTrue(result['stale'])
            self.assertEqual(result['sample']['ts'],100)

    def test_gaps_and_minute_extrema(self):
        save(self.path, 120, self.values)
        save(self.path, 125, {**self.values,'total_act_power':300})
        save(self.path, 130, error='timeout')
        save(self.path, 135, self.values)
        save(self.path, 160, self.values)
        result=history(self.path,120,170)
        self.assertEqual(len(result),3)
        self.assertEqual(result[0][0]['total_act_power'],200)
        self.assertEqual(result[0][0]['total_act_power_min'],100)
        self.assertEqual(result[0][0]['total_act_power_max'],300)
        self.assertEqual(len(history(self.path,120,130,0)[0]),2)

    def test_fifteen_minute_average_is_time_weighted_and_signed(self):
        values = dict(self.values)
        for ts, watts in ((0, 300), (10, 300), (20, -300), (30, -300)):
            save(self.path, ts, {**values, 'total_act_power':watts})
        result = recent_average(self.path, 30, window_seconds=30, gap_seconds=15)
        self.assertTrue(result['complete'])
        self.assertAlmostEqual(result['watts'], 0)
        self.assertEqual(result['coverage'], 1)

    def test_fifteen_minute_average_rejects_insufficient_coverage(self):
        save(self.path, 0, {**self.values, 'total_act_power':200})
        save(self.path, 10, {**self.values, 'total_act_power':200})
        result = recent_average(self.path, 30, window_seconds=30, gap_seconds=15)
        self.assertFalse(result['complete'])
        self.assertAlmostEqual(result['coverage'], 1 / 3)

    def test_status_contains_fifteen_minute_average(self):
        for ts in range(100, 1001, 5):
            save(self.path, ts, {**self.values, 'total_act_power':250})
        with patch('webapp.time.time', return_value=1000):
            result = self.client.get('/api/status').json['average_15m']
        self.assertTrue(result['complete'])
        self.assertEqual(result['watts'], 250)

    def test_local_day_and_dst(self):
        for day,hours in ((date(2026,3,29),23),(date(2026,10,25),25),(date(2026,9,13),24)):
            start,end=day_bounds(day)
            self.assertEqual(end-start,hours*3600)
        start,end=day_bounds(date(2026,9,13))
        save(self.path,start-1,self.values)
        save(self.path,start,self.values)
        save(self.path,end,self.values)
        result=self.client.get('/api/history?date=2026-09-13').json
        self.assertEqual(sum(p['count'] for s in result['segments'] for p in s),1)

    def test_routes(self):
        self.assertEqual(self.client.get('/').status_code,200)
        response=self.client.get('/static/dashboard.js')
        self.assertEqual(response.status_code,200)
        response.close()
        self.assertEqual(self.client.get('/api/history?date=invalid').status_code,400)
        self.assertEqual(self.client.get('/api/history?mode=invalid').status_code,400)
        self.assertEqual(self.client.get('/api/status').headers['Cache-Control'],'no-store')
        script=Path(__file__).parents[1].joinpath('static/dashboard.js').read_text(encoding='utf-8')
        self.assertIn('setTimeout(refreshHistory,30000)',script)
        self.assertIn("document.addEventListener('visibilitychange'",script)
        self.assertIn('historyController?.abort()',script)
        self.assertIn('statusPending',script)

    def test_past_day_cache_expires_and_live_day_is_not_cached(self):
        from datetime import datetime
        from webapp import ZONE
        import webapp
        with patch('webapp.estimate', wraps=webapp.estimate) as calculate:
            with patch('webapp.time.monotonic', return_value=100):
                self.client.get('/api/history?date=2020-01-01')
                self.client.get('/api/history?date=2020-01-01')
                self.assertEqual(calculate.call_count,1)
            with patch('webapp.time.monotonic', return_value=161):
                self.client.get('/api/history?date=2020-01-01')
                self.assertEqual(calculate.call_count,2)
            today=datetime.now(ZONE).date().isoformat()
            self.client.get('/api/history?date='+today)
            self.client.get('/api/history?date='+today)
            self.assertEqual(calculate.call_count,4)

if __name__ == '__main__':
    unittest.main()
