from datetime import datetime, date, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from webapp import create_app
from database import connect
from tibber import bounds, parse_prices, collect_tibber, price_status, request_api
from solaredge import ZONE


def response(day, tomorrow=True):
    def prices(d):
        start,end=bounds(d)
        return [{'startsAt':datetime.fromtimestamp(t,timezone.utc).isoformat(),'total':-.05 if i==0 else .25,'energy':.15,'tax':.10,'currency':'EUR'} for i,t in enumerate(range(int(start),int(end),900))]
    return {'data':{'viewer':{'homes':[{'id':'test-home','currentSubscription':{'priceInfo':{'today':prices(day),'tomorrow':prices(day+timedelta(days=1)) if tomorrow else []}}}]}}}

class TibberTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db'
        self.app=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}})
        self.day=date(2026,9,13)
        self.now=datetime(2026,9,13,12,0,tzinfo=ZONE).timestamp()

    def test_negative_prices_and_cents(self):
        collect_tibber(self.path,'fake',now=self.now,fetcher=lambda token:response(self.day))
        result=price_status(self.path,self.day,self.now)
        self.assertEqual(result['min_ct'],-5)
        self.assertEqual(result['current_ct'],25)
        self.assertAlmostEqual(result['battery_pv_threshold_ct'],9/.85+5)
        self.assertAlmostEqual(result['battery_grid_threshold_ct'],25/.85+5)
        self.assertEqual(result['battery_grid_reference_ct'],25)
        self.assertTrue(result['complete'])
        self.assertEqual(len(result['points']),96)

    def test_dst_days(self):
        for day,count in ((date(2026,3,29),92),(date(2026,10,25),100)):
            now=datetime.combine(day,datetime.min.time(),ZONE).timestamp()+3600
            _,prices=parse_prices(response(day,False),'',now)
            self.assertEqual(len(prices),count)
            self.assertEqual(len({p['start'] for p in prices}),count)

    def test_cache_avoids_calls_and_pending_is_not_zero(self):
        calls=[]
        def fetch(token):calls.append(True);return response(self.day)
        collect_tibber(self.path,'fake',now=self.now,fetcher=fetch)
        collect_tibber(self.path,'fake',now=self.now+3600,fetcher=fetch)
        self.assertEqual(len(calls),1)
        future=price_status(self.path,self.day+timedelta(days=2),self.now)
        self.assertTrue(future['pending']);self.assertIsNone(future['average_ct'])

    def test_missing_tomorrow_retries_only_later_slot(self):
        calls=[]
        def fetch(token):calls.append(True);return response(self.day,False)
        collect_tibber(self.path,'fake',now=self.now,fetcher=fetch)
        collect_tibber(self.path,'fake',now=self.now+1,fetcher=fetch)
        collect_tibber(self.path,'fake',now=self.now+3600,fetcher=fetch)
        self.assertEqual(len(calls),2)
        self.assertEqual(price_status(self.path,self.day+timedelta(days=1),self.now)['points'],[])

    def test_invalid_data_and_multiple_homes(self):
        data=response(self.day);data['data']['viewer']['homes']*=2
        with self.assertRaises(ValueError):parse_prices(data,'',self.now)
        for data in ({'errors':[{'message':'no'}]},{'data':None}):
            with self.assertRaises(ValueError):parse_prices(data,'',self.now)
        data=response(self.day);data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['today'][0]['total']=float('nan')
        with self.assertRaises(ValueError):parse_prices(data,'',self.now)

    def test_error_does_not_leak_token(self):
        with patch('tibber.build_opener') as opener:
            opener.return_value.open.side_effect=HTTPError('https://api.tibber.com',401,'SECRET',{},None)
            with self.assertRaises(ValueError) as caught:request_api('SECRET')
            self.assertNotIn('SECRET',str(caught.exception))

    def test_route_and_gaps(self):
        data=response(self.day,False);data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['today'].pop(5)
        collect_tibber(self.path,'fake',now=self.now,fetcher=lambda token:data)
        result=self.app.test_client().get('/api/tibber?date=2026-09-13')
        self.assertEqual(result.status_code,200)
        self.assertFalse(result.json['complete']);self.assertEqual(len(result.json['points']),95)
        self.assertEqual(self.app.test_client().get('/api/tibber?date=bad').status_code,400)

if __name__=='__main__':unittest.main()
