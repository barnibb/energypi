import tempfile
import unittest
from pathlib import Path

from database import connect, initialize, save
from finance_summary import financial_summary
from tibber import initialize_tibber


class FinanceSummaryTests(unittest.TestCase):
    def test_interval_price_applied_to_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'db'
            initialize(path);initialize_tibber(path)
            save(path, 1000, {'total_act_power':1000, **{f'{p}_{f}':0 for p in 'abc' for f in ('act_power','voltage','current')}})
            save(path, 1010, {'total_act_power':1000, **{f'{p}_{f}':0 for p in 'abc' for f in ('act_power','voltage','current')}})
            with connect(path) as db:
                db.execute('INSERT INTO tibber_meta VALUES(1,?)',('home',))
                db.execute('INSERT INTO tibber_prices VALUES(?,?,?,?,?,?,?,?)',
                           ('home',900,1100,.20,.10,.10,'EUR',900))
            flows=dict(valid=True,pv_kwh=2,export_kwh=.5,battery_in_kwh=.25,
                       battery_out_kwh=.4,house_kwh=2)
            result=financial_summary(path,1000,1011,flows,9)
            self.assertTrue(result['complete'])
            self.assertAlmostEqual(result['priced_import_kwh'],10/3600)
            self.assertAlmostEqual(result['import_cost_eur'],10/3600*.20)
            self.assertAlmostEqual(result['feed_revenue_eur'],.045)
            self.assertAlmostEqual(result['pv_direct_kwh'],1.25)
            self.assertAlmostEqual(result['pv_benefit_eur'],1.25*.11)
            self.assertAlmostEqual(result['battery_value_eur'],.08)
            self.assertAlmostEqual(result['actual_import_price_ct'],20)
            self.assertAlmostEqual(result['effective_house_price_ct'],
                                   (10/3600*.20-.045)/2*100)

    def test_missing_prices_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';initialize(path)
            result=financial_summary(path,1000,1010,dict(valid=True,pv_kwh=1,
                export_kwh=0,battery_in_kwh=0,battery_out_kwh=0),9)
            self.assertFalse(result['complete'])
            self.assertIsNone(result['import_cost_eur'])


if __name__ == '__main__':
    unittest.main()
