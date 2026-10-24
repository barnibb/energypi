from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from database import connect
from webapp import create_app
from forecast import normalize, remaining, collect_forecast, forecast_status, forecast_url, ZONE
from energy import parse_energy, collect_energy


def data():
    return {'message':{'type':'success','info':{'timezone':'Europe/Berlin'}},'result':{
        'watt_hours_day':{'2026-09-13':2000},
        'watts':{'2026-09-13 08:00:00':0,'2026-09-13 10:00:00':1000,'2026-09-13 12:00:00':0},
        'watt_hours':{'2026-09-13 08:00:00':0,'2026-09-13 10:00:00':1000,'2026-09-13 12:00:00':2000}}}

class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db'
        self.app=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}})
        self.now=datetime(2026,9,13,9,0,tzinfo=ZONE).timestamp()

    def test_south_and_watt_hours(self):
        self.assertEqual(forecast_url({'latitude':52.0,'longitude':13.0,'tilt':43,'azimuth':180,'kwp':7}),
                         'https://api.forecast.solar/estimate/52.0/13.0/43/0/7')
        day=normalize(data())['2026-09-13']
        self.assertEqual(day['total_kwh'],2)
        self.assertEqual(remaining(day,self.now),1.5)
        self.assertEqual(remaining(day,self.now-7200),2)
        self.assertEqual(remaining(day,self.now+20000),0)

    def test_snapshots_preserved_and_failures_keep_last_forecast(self):
        def fetch(config):return normalize(data())
        collect_forecast(self.path,{},self.now,fetch)
        collect_forecast(self.path,{},self.now+1,fetch)
        collect_forecast(self.path,{},self.now+7200,fetch)
        def fail(config):raise ValueError('offline')
        collect_forecast(self.path,{},self.now+14400,fail)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM forecast_days').fetchone()[0],2)
        result=forecast_status(self.path,'2026-09-13',self.now+14400)
        self.assertEqual(result['forecast']['total_kwh'],2)
        self.assertEqual(result['message'],'offline')
        self.assertIsNone(forecast_status(self.path,'2026-09-14',self.now)['forecast'])

    def test_energy_conversion_null_not_zero_and_hourly_limit(self):
        response={'energy':{'unit':'Wh','timeUnit':'DAY','values':[{'date':'2026-09-13 00:00:00','value':12345},{'date':'2026-09-12 00:00:00','value':None}]}}
        self.assertEqual(parse_energy(response),{'2026-09-13':12.345})
        calls=[]
        def fetch(site,key,today):calls.append(True);return parse_energy(response)
        collect_energy(self.path,'1','fake',self.now,fetch)
        collect_energy(self.path,'1','fake',self.now+1,fetch)
        self.assertEqual(len(calls),1)
        self.assertEqual(forecast_status(self.path,'2026-09-13',self.now)['energy']['kwh'],12.345)
        self.assertIsNone(forecast_status(self.path,'2026-09-14',self.now)['energy'])
        def missing(site,key,today):return {}
        collect_energy(self.path,'1','fake',self.now+3600,missing)
        self.assertEqual(forecast_status(self.path,'2026-09-13',self.now)['energy']['fetched_at'],self.now)

    def test_invalid_and_empty_routes(self):
        client=self.app.test_client()
        self.assertEqual(client.get('/api/forecast?date=bad').status_code,400)
        self.assertEqual(client.get('/api/forecast?date=2026-09-13').status_code,200)
        broken=data();broken['result']['watts']={}
        with self.assertRaises(ValueError):normalize(broken)
        broken=data();broken['result']['watt_hours_day']['2026-09-13']=float('nan')
        with self.assertRaises(ValueError):normalize(broken)

if __name__=='__main__':unittest.main()

class ForecastHoursTests(unittest.TestCase):
    setUp=ForecastTests.setUp

    def test_fixed_diagram_hours_and_dst(self):
        from preferences import DEFAULTS,save_preferences
        result=forecast_status(self.path,'2026-03-29',self.now)
        start=datetime.fromtimestamp(result['view_start'],ZONE)
        end=datetime.fromtimestamp(result['view_end'],ZONE)
        self.assertEqual((start.hour,end.hour),(5,23))
        self.assertEqual(result['view_end']-result['view_start'],18*3600)
        save_preferences(self.path,{**DEFAULTS,'forecast_start_hour':0,'forecast_end_hour':24},5)
        result=forecast_status(self.path,'2026-03-29',self.now)
        self.assertEqual(result['view_end']-result['view_start'],23*3600)
