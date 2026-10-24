import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from database import FIELDS, connect, history, initialize, save
from maintenance import compact, backup, cleanup_journals, cleanup_partials, preflight, run_worker

class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'measurements.db'
        initialize(self.path)
        self.values = dict.fromkeys(FIELDS, 100.0)

    def test_archive_preserves_history_and_recent_raw_data(self):
        for ts in (120,125,135,160,180,185):
            save(self.path, ts, {**self.values,'total_act_power':ts})
        save(self.path,130,error='timeout')
        save(self.path,195,error='timeout')
        save(self.path,200,self.values)
        before=history(self.path,0,300)
        self.assertEqual(compact(self.path,now=86400+180,raw_days=1),1)
        self.assertEqual(history(self.path,0,300),before)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT MIN(ts) FROM measurements').fetchone()[0],180)
        self.assertEqual(compact(self.path,now=86400+180,raw_days=1),0)
        compact(self.path,now=86400+300,raw_days=1)
        self.assertEqual(history(self.path,0,300),before)

    def test_failure_rolls_back_deletion(self):
        save(self.path,120,self.values)
        with connect(self.path) as db:
            db.execute("CREATE TRIGGER refuse_archive BEFORE INSERT ON minute_archive BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            compact(self.path,now=86400+180,raw_days=1)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM minute_archive').fetchone()[0],0)

    def test_backup_contains_wal_and_archive_and_rotates(self):
        save(self.path,120,self.values)
        compact(self.path,now=86400+180,raw_days=1)
        # Halte Verbindung offen, sodass WAL-Dateien beim Backup existieren.
        with connect(self.path) as live:
            live.execute('SELECT * FROM minute_archive').fetchall()
            save(self.path,200,self.values)
            directory=Path(self.temp.name)/'backups'
            for _ in range(3):
                target=backup(self.path,directory,keep=2)
            self.assertEqual(len(list(directory.glob('marstek-*.sqlite3'))),2)
            self.assertEqual((directory/'latest.sqlite3').resolve(),target.resolve())
            with connect(target) as copied:
                self.assertEqual(copied.execute('PRAGMA quick_check').fetchone()[0],'ok')
                self.assertEqual(copied.execute('SELECT COUNT(*) FROM minute_archive').fetchone()[0],1)
                self.assertEqual(copied.execute('SELECT MAX(ts) FROM measurements').fetchone()[0],200)
            self.assertEqual(history(target,0,300),history(self.path,0,300))

    def test_minute_boundary_cutoff_keeps_incomplete_minute(self):
        save(self.path,180,self.values)
        compact(self.path,now=86400+185,raw_days=1)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0],1)

    def test_cleanup_only_removes_expired_journals_and_keeps_latest(self):
        with connect(self.path) as db:
            db.execute('CREATE TABLE energy_attempts(ts REAL PRIMARY KEY,error TEXT)')
            db.executemany('INSERT INTO energy_attempts VALUES(?,?)',[(1,'alt'),(2,'letzter')])
            db.execute('CREATE TABLE solaredge_energy(day TEXT PRIMARY KEY,kwh REAL,fetched_at REAL)')
            db.execute("INSERT INTO solaredge_energy VALUES('2025-01-01',1.0,1)")
        result=cleanup_journals(self.path,now=100*86400,rules=(('energy_attempts','ts',90,None),))
        self.assertEqual(result['energy_attempts']['deleted'],1)
        with connect(self.path) as db:
            self.assertEqual([r['ts'] for r in db.execute('SELECT ts FROM energy_attempts')],[2])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM solaredge_energy').fetchone()[0],1)
            status=db.execute('SELECT payload FROM maintenance_status WHERE id=1').fetchone()
            self.assertIsNotNone(status)

    def test_cleanup_is_bounded_and_preserves_active_requests(self):
        with connect(self.path) as db:
            db.execute('CREATE TABLE marstek_actions(id INTEGER PRIMARY KEY,created REAL,status TEXT,message TEXT,updated REAL)')
            db.executemany('INSERT INTO marstek_actions VALUES(?,?,?,?,?)',[
                (1,1,'done','alt',1),(2,2,'error','alt',2),(3,3,'pending','offen',3),(4,4,'done','neuester',4)])
        rules=(('marstek_actions','updated',1,"status NOT IN ('pending','processing')"),)
        first=cleanup_journals(self.path,now=10*86400,rules=rules,batch_size=1)
        self.assertEqual((first['marstek_actions']['deleted'],first['marstek_actions']['remaining_old']),(1,1))
        cleanup_journals(self.path,now=10*86400,rules=rules,batch_size=1)
        with connect(self.path) as db:
            rows=[(r['id'],r['status']) for r in db.execute('SELECT id,status FROM marstek_actions ORDER BY id')]
        self.assertEqual(rows,[(3,'pending'),(4,'done')])

    def test_cleanup_reports_missing_table_without_creating_it(self):
        result=cleanup_journals(self.path,now=100,rules=(('not_installed','ts',1,None),))
        self.assertTrue(result['not_installed']['missing'])
        with connect(self.path) as db:
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='not_installed'").fetchone())

    def test_compaction_stops_at_configured_minute_limit(self):
        for ts in (60,120,180):save(self.path,ts,self.values)
        self.assertEqual(compact(self.path,now=86400+300,raw_days=1,max_minutes=1),1)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM minute_archive').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0],2)

    def test_partial_cleanup_only_removes_old_files(self):
        directory=Path(self.temp.name)/'backups';directory.mkdir()
        old=directory/'old.partial';new=directory/'new.partial';old.write_text('x');new.write_text('x')
        import os
        os.utime(old,(1,1));os.utime(new,(100,100))
        self.assertEqual(cleanup_partials(directory,now=200,minimum_age=150),1)
        self.assertFalse(old.exists());self.assertTrue(new.exists())

    def test_preflight_reports_required_storage(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with patch('maintenance.shutil.disk_usage',return_value=SimpleNamespace(free=2*1024**3)):
            result=preflight(self.path)
        self.assertGreater(result['required_bytes'],result['database_bytes'])
        self.assertGreater(result['free_bytes'],0)

    def test_worker_timeout_becomes_clear_maintenance_error(self):
        import subprocess
        from unittest.mock import patch
        with patch('maintenance.subprocess.run',side_effect=subprocess.TimeoutExpired(['worker'],10)):
            with self.assertRaisesRegex(TimeoutError,'nach 10 Sekunden beendet'):
                run_worker('backup',10)

    def test_observation_plans_keep_14_days_latest_and_delete_at_most_500(self):
        with connect(self.path) as db:
            db.execute('CREATE TABLE observation_plans(id INTEGER PRIMARY KEY,ts REAL,payload TEXT)')
            db.executemany('INSERT INTO observation_plans(ts,payload) VALUES(?,?)',
                           [(n,'{}') for n in range(1,503)])
        rules=(('observation_plans','ts',14,None),)
        result=cleanup_journals(self.path,now=20*86400,rules=rules,batch_size=10_000)
        self.assertEqual(result['observation_plans']['deleted'],500)
        self.assertEqual(result['observation_plans']['remaining_old'],1)
        with connect(self.path) as db:
            rows=[row['ts'] for row in db.execute('SELECT ts FROM observation_plans ORDER BY ts')]
        self.assertEqual(rows,[501,502])

if __name__ == '__main__':
    unittest.main()
