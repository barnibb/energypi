from datetime import date,datetime,timedelta
from pathlib import Path
import tempfile
import unittest
from database import connect
from webapp import create_app
from forecast import store_days
from opportunities import annotate, interpolate, battery_thresholds
from solaredge import ZONE

class OpportunityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db'
        self.app=create_app({'database_path':self.path,'shelly':{'poll_seconds':5}})
        self.day=date(2026,9,13);self.now=datetime(2026,9,13,12,tzinfo=ZONE).timestamp()

    def forecast(self,power=3610,age=0):
        points=[{'ts':self.now,'w':power},{'ts':self.now+3600,'w':power}]
        with connect(self.path) as db:
            run=db.execute('INSERT INTO forecast_runs(ts) VALUES (?)',(self.now-age,)).lastrowid
        store_days(self.path,run,{self.day.isoformat():{'points':points,'cumulative':[],'total_kwh':5}})

    def test_price_quarter_ties_and_nine_cent_boundary(self):
        prices=[{'start':self.now+i*900,'ct':v} for i,v in enumerate([8,9,9,30,40,50,60,70])]
        r=annotate(self.path,self.day,prices,self.now)
        slots=[s for s in r['slots'] if s['ct'] is not None]
        self.assertEqual(r['cheap_threshold_ct'],9)
        self.assertEqual(sum(s['cheap'] for s in slots),3)
        self.assertEqual(sum(s['below_feed_in'] for s in slots),1)
        self.assertFalse(any(s['pv_good'] for s in slots))

    def test_flat_prices_not_relatively_cheap(self):
        r=annotate(self.path,self.day,[{'start':self.now,'ct':5}],self.now)
        self.assertIsNone(r['cheap_threshold_ct'])
        self.assertFalse(any(s['cheap'] for s in r['slots']))
        self.assertTrue(any(s['below_feed_in'] for s in r['slots']))

    def test_pv_band_without_prices_and_stale_forecast(self):
        self.forecast()
        r=annotate(self.path,self.day,[],self.now)
        self.assertEqual(sum(s['pv_good'] for s in r['slots']),4)
        self.assertEqual(next(s for s in r['slots'] if s['pv_good'])['pv_surplus_w'],3450)
        r=annotate(self.path,self.day,[],self.now+14401)
        self.assertEqual(r['pv_state'],'stale')
        self.assertFalse(any(s['pv_good'] for s in r['slots']))

    def test_below_threshold_and_interpolation_gaps(self):
        self.forecast(3609)
        self.assertFalse(any(s['pv_good'] for s in annotate(self.path,self.day,[],self.now)['slots']))
        self.assertIsNone(interpolate([{'ts':0,'w':4000},{'ts':10000,'w':4000}],500))
        self.assertEqual(interpolate([{'ts':0,'w':0},{'ts':3600,'w':4000}],1800),2000)

    def test_dst_and_api(self):
        for day,count in ((date(2026,3,29),92),(date(2026,10,25),100)):
            self.assertEqual(len(annotate(self.path,day,[],self.now)['slots']),count)
        result=self.app.test_client().get('/api/tibber?date=2026-09-13')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['pv_threshold_w'],3610)

    def test_battery_economic_thresholds(self):
        settings={'plan_efficiency':85,'plan_wear_ct':2,'plan_margin_ct':3,'feed_in_ct':9}
        pv,grid=battery_thresholds(settings,17.05)
        self.assertAlmostEqual(pv,15.588235,places=5)
        self.assertAlmostEqual(grid,25.058823,places=5)
        self.assertEqual(battery_thresholds(settings)[1],None)

if __name__=='__main__':unittest.main()
