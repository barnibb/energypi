import unittest
import tempfile
from pathlib import Path
from datetime import date,datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from finance_history import daily_point,history,persistent_point,store_point
from webapp import create_app


class FinanceHistoryTests(unittest.TestCase):
    def test_endpoint_and_markup(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=create_app({'database_path':Path(tmp)/'db','shelly':{'poll_seconds':5}}).test_client()
            with patch('webapp.finance_history',return_value={'days':7,'points':[]}) as calculate:
                response=client.get('/api/finance/history?days=7&week=2026-10-07')
            self.assertEqual(response.status_code,200);self.assertEqual(response.json['days'],7)
            self.assertEqual(calculate.call_args.args[-1],date(2026,10,5))
            self.assertEqual(client.get('/api/finance/history?days=1').status_code,400)
            self.assertEqual(client.get('/api/finance/history?week=ungueltig').status_code,400)
            html=client.get('/').text
            self.assertIn('id="finance-history-dialog"',html);self.assertIn('id="finance-week-previous"',html)
            self.assertIn('id="finance-week-current"',html);self.assertIn('id="finance-week-next"',html)
            self.assertIn('id="finance-view-money"',html);self.assertIn('id="finance-week-summary"',html)
            script=Path('static/finance-history.js').read_text()
            self.assertIn("shiftWeek(-1)",script);self.assertIn("shiftWeek(1)",script)
            self.assertIn("days=7&week=",script)
            self.assertIn("view==='money'",script);self.assertIn('Eigenversorgung und Energiekosten',script)
    def test_daily_point_exposes_components(self):
        now=datetime(2026,10,4,12,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
        flows={'house_kwh':10,'money':{'complete':True,'effective_house_price_ct':8.3,
               'import_cost_eur':1.1,'feed_revenue_eur':.27,'benefit_eur':1.5,
               'pv_benefit_eur':.8,'battery_value_eur':.43,'pv_direct_kwh':4},
               'battery_out_kwh':2}
        with patch('finance_history.estimate',return_value={'coverage':1}),patch('finance_history.flow_summary',return_value=flows):
            point=daily_point('db',date(2026,10,4),now,9)
        self.assertTrue(point['complete']);self.assertTrue(point['today'])
        self.assertAlmostEqual(point['net_cost_eur'],.83);self.assertEqual(point['house_kwh'],10)
        self.assertEqual(point['benefit_eur'],1.5)
        self.assertAlmostEqual(point['cost_without_self_supply_eur'],2.33)
        self.assertEqual(point['self_supply_kwh'],6)
        self.assertEqual(point['self_supply_percent'],60)

    def test_ten_days_and_completed_day_cache(self):
        now=datetime(2026,10,4,12,tzinfo=ZoneInfo('Europe/Berlin')).timestamp();cache={}
        def point(_path,day,_now,_feed):return {'day':day.isoformat(),'today':day==date(2026,10,4),'complete':True}
        with tempfile.TemporaryDirectory() as tmp,patch('finance_history.daily_point',side_effect=point) as build,patch('finance_history.persistent_point',return_value=None),patch('finance_history.store_point'):
            path=Path(tmp)/'db';first=history(path,now,9,10,cache);second=history(path,now,9,10,cache)
        self.assertEqual(len(first['points']),10);self.assertEqual(first['points'][0]['day'],'2026-09-25')
        self.assertEqual(first['points'][-1]['day'],'2026-10-04');self.assertEqual(build.call_count,11)
        self.assertEqual(second['formula'],'(Netzbezugskosten − Einspeisevergütung) ÷ Hausverbrauch')

    def test_calendar_week_has_monday_to_sunday_and_iso_number(self):
        now=datetime(2026,10,9,12,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
        def point(_path,day,_now,_feed):return {'day':day.isoformat(),'today':day==date(2026,10,9),'complete':False}
        with patch('finance_history.daily_point',side_effect=point),patch('finance_history.persistent_point',return_value=None):
            result=history('db',now,9,7,{},date(2026,10,5))
        self.assertEqual(result['week_number'],41);self.assertEqual(result['week_year'],2026)
        self.assertEqual(result['week_start'],'2026-10-05');self.assertEqual(result['week_end'],'2026-10-11')
        self.assertEqual([p['day'] for p in result['points']],['2026-10-05','2026-10-06','2026-10-07','2026-10-08','2026-10-09','2026-10-10','2026-10-11'])

    def test_week_summary_totals_only_complete_days(self):
        now=datetime(2026,10,9,12,tzinfo=ZoneInfo('Europe/Berlin')).timestamp()
        def point(_path,day,_now,_feed):
            complete=day<=date(2026,10,9)
            return {'cache_version':2,'day':day.isoformat(),'today':day==date(2026,10,9),'complete':complete,
                    'benefit_eur':2 if complete else None,'net_cost_eur':1 if complete else None,
                    'cost_without_self_supply_eur':3 if complete else None,'house_kwh':10 if complete else None,
                    'self_supply_kwh':6 if complete else None}
        with patch('finance_history.daily_point',side_effect=point),patch('finance_history.persistent_point',return_value=None),patch('finance_history.store_point'):
            result=history('db',now,9,7,{},date(2026,10,5))
        self.assertEqual(result['summary']['complete_days'],5)
        self.assertEqual(result['summary']['benefit_eur'],10)
        self.assertEqual(result['summary']['net_cost_eur'],5)
        self.assertEqual(result['summary']['self_supply_percent'],60)

    def test_completed_day_survives_memory_cache_and_invalidates_on_new_pv_fetch(self):
        from database import connect
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';day=date(2026,10,3)
            with connect(path) as db:
                db.execute('CREATE TABLE solaredge_energy(day TEXT PRIMARY KEY,kwh REAL,fetched_at REAL)')
                db.execute('INSERT INTO solaredge_energy VALUES(?,?,?)',(day.isoformat(),12.3,100))
            point={'day':day.isoformat(),'today':False,'complete':True,'effective_house_price_ct':7.2}
            store_point(path,point,9,200)
            self.assertEqual(persistent_point(path,day,9)['effective_house_price_ct'],7.2)
            with connect(path) as db:db.execute('UPDATE solaredge_energy SET fetched_at=101 WHERE day=?',(day.isoformat(),))
            self.assertIsNone(persistent_point(path,day,9))


if __name__=='__main__':unittest.main()
