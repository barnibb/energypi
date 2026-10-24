import tempfile
import unittest
from pathlib import Path
from database import connect,initialize,save,FIELDS
from retention import inventory,with_growth


class RetentionInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db';initialize(self.path)

    def test_inventory_is_read_only_and_reports_ranges(self):
        save(self.path,100,dict.fromkeys(FIELDS,1));save(self.path,200,dict.fromkeys(FIELDS,2))
        with connect(self.path) as db:
            before={row['name'] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result=inventory(self.path,300)
        with connect(self.path) as db:
            after={row['name'] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(before,after)
        self.assertEqual(result['tables']['measurements']['rows'],2)
        self.assertEqual((result['tables']['measurements']['oldest'],result['tables']['measurements']['newest']),(100,200))
        self.assertFalse(result['tables']['marstek_samples']['present'])

    def test_growth_compares_two_bounded_snapshots(self):
        first=inventory(self.path,100)
        save(self.path,101,dict.fromkeys(FIELDS,1))
        second=with_growth(inventory(self.path,200),first)
        self.assertEqual(second['seconds_since_previous'],100)
        self.assertEqual(second['tables']['measurements']['rows_since_previous'],1)


if __name__=='__main__':unittest.main()
