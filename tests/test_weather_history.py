import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from database import connect
from weather import weather_history,sevilla_weather_history
from webapp import create_app,day_bounds
from datetime import date
from sun_times import sun_times

class WeatherHistoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'db';self.client=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}}).test_client()
 def test_model_time_duplicates_and_gaps(self):
  with connect(self.path) as db:
   for fetched,valid,value in [(200,100,1),(201,100,2),(1001,1000,-2),(3101,3100,4),(6101,6100,99)]:
    db.execute('INSERT INTO weather_samples VALUES(?,?,?,?,?,?)',(fetched,valid,value,54,9,'test'))
  data=weather_history(self.path,0,6000,5000)
  self.assertEqual(data['count'],3);self.assertEqual(data['minimum'],-2);self.assertEqual(data['maximum'],4)
  self.assertEqual([len(s) for s in data['segments']],[2,1]);self.assertEqual(data['segments'][0][0]['temperature_c'],2)
 def test_day_bounds_dst(self):
  a,b=day_bounds(date(2026,3,29));self.assertEqual(b-a,23*3600)
  a,b=day_bounds(date(2026,10,25));self.assertEqual(b-a,25*3600)
 def test_sevilla_history_is_returned_separately(self):
  with connect(self.path) as db:
   db.execute('INSERT INTO weather_sevilla_samples VALUES(?,?,?,?,?,?)',(201,100,7.5,37.38620512,-5.99251368,'test'))
  data=sevilla_weather_history(self.path,0,6000,5000)
  self.assertEqual(data['count'],1);self.assertEqual(data['segments'][0][0]['temperature_c'],7.5)
  response=self.client.get('/api/weather/history?date=1970-01-01')
  self.assertIn('sevilla',response.json);self.assertIsNotNone(response.json['sevilla']['sunrise']);self.assertIsNotNone(response.json['sevilla']['sunset'])
 def test_sun_times_are_local_stable_and_include_daylight(self):
  winter=sun_times(date(2026,1,15),54,10);summer=sun_times(date(2026,6,21),54,10)
  self.assertIsNone(winter['polar_state']);self.assertIsNone(summer['polar_state'])
  self.assertGreater(summer['daylight_seconds'],winter['daylight_seconds'])
  self.assertGreater(summer['daylight_seconds'],16*3600)
  self.assertLess(winter['daylight_seconds'],8*3600)
  sevilla=sun_times(date(2026,6,21),37.38620512,-5.99251368)
  self.assertLess(sevilla['daylight_seconds'],summer['daylight_seconds'])
 def test_endpoint_empty_invalid_no_network(self):
  with patch('weather.fetch_weather',side_effect=AssertionError('network')):
   response=self.client.get('/api/weather/history?date=2026-09-18')
  self.assertEqual(response.status_code,200);self.assertEqual(response.json['count'],0)
  self.assertIsNotNone(response.json['sunrise']);self.assertIsNotNone(response.json['sunset'])
  self.assertGreater(response.json['daylight_seconds'],0)
  self.assertIsNone(response.json['minimum']);self.assertEqual(response.headers['Cache-Control'],'no-store')
  self.assertEqual(self.client.get('/api/weather/history?date=bad').status_code,400)
  html=self.client.get('/').text;self.assertIn('id="weather-dialog"',html);self.assertIn('id="weather-open"',html);self.assertIn('id="weather-previous-day"',html);self.assertIn('id="weather-next-day"',html);self.assertIn('id="weather-sevilla-value"',html);self.assertIn('id="weather-sevilla-sunrise"',html);self.assertIn('id="weather-sevilla-sunset"',html);self.assertIn('spanische Ortszeit',html)
  script=Path(__file__).parents[1].joinpath('static/weather-history.js').read_text();self.assertIn("curve(payload.segments,'#df8c3c')",script);self.assertIn("curve(payload.sevilla?.segments||[],'#72c477')",script)
