import tempfile
import unittest
from pathlib import Path
from backup_status import initialize_backup,record,status

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db';initialize_backup(self.path)
    def test_empty(self):self.assertEqual(status(self.path,0)['level'],'neutral')
    def test_success_and_overdue(self):
        record(self.path,'success',100)
        self.assertEqual(status(self.path,101)['level'],'ok')
        self.assertEqual(status(self.path,100+36*3600+1)['label'],'Überfällig')
    def test_failure_keeps_success_and_recovery(self):
        record(self.path,'success',100);record(self.path,'failure',200)
        failed=status(self.path,201)
        self.assertEqual(failed['last_success'],100)
        self.assertEqual(failed['last_attempt'],200)
        self.assertEqual(failed['display_time'],200)
        self.assertEqual(failed['level'],'warn')
        record(self.path,'success',300)
        recovered=status(self.path,301)
        self.assertIsNone(recovered['error'])
        self.assertEqual(recovered['display_time'],300)
    def test_reject_invalid(self):
        with self.assertRaises(ValueError):record(self.path,'arbitrary command',100)
