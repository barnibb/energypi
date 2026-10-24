"""Begrenzte Journale, 30 Tage Rohdaten und konsistente SQLite-Sicherungen."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import json
import logging
import os
from pathlib import Path
import sqlite3
import shutil
import signal
import subprocess
import sys
import time
from database import connect, initialize, summarize
from settings import load_settings
from retention import inventory as retention_inventory, with_growth


# Stufe 1 der Aufbewahrung: nur Protokolle und Abrufversuche. Energie- und
# Messreihen werden hier absichtlich nicht gelöscht. Mindestens der jüngste
# Datensatz jeder Tabelle bleibt als Diagnosehinweis erhalten.
JOURNAL_RETENTION = (
    ('energy_attempts', 'ts', 90, None),
    ('tibber_attempts', 'ts', 90, None),
    ('weather_attempts', 'ts', 90, None),
    ('fan_events', 'ts', 365, None),
    ('charging_events', 'detected_at', 730, None),
    ('marstek_control_events', 'ts', 730, None),
    ('preference_changes', 'ts', 730, None),
    ('observation_plans', 'ts', 14, None),
    ('marstek_actions', 'updated', 365, "status NOT IN ('pending','processing')"),
    ('grid_charge_requests', 'updated', 365, "status NOT IN ('pending','processing','confirmed','scheduled','active','cancel_requested')"),
)
MAX_DELETE_PER_TABLE = 10_000
TABLE_DELETE_LIMITS = {'observation_plans': 500}
MAX_ARCHIVE_MINUTES = 20_000
MAX_ARCHIVE_SECONDS = 600
BACKUP_TIMEOUT_SECONDS = 600
CHECK_TIMEOUT_SECONDS = 120
MIN_FREE_RESERVE_BYTES = 500 * 1024 * 1024
EXPORT_TIMEOUT_SECONDS = 900


def _table_exists(db, table):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def write_maintenance_status(path, payload, now=None):
    now = time.time() if now is None else now
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS maintenance_status(
            id INTEGER PRIMARY KEY CHECK(id=1), ts REAL NOT NULL, payload TEXT NOT NULL)''')
        db.execute('''INSERT INTO maintenance_status(id,ts,payload) VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET ts=excluded.ts,payload=excluded.payload''',
                   (now, json.dumps(payload, allow_nan=False, separators=(',', ':'))))


def cleanup_partials(directory, now=None, minimum_age=3600):
    now = time.time() if now is None else now
    removed = 0
    directory = Path(directory)
    for item in directory.glob('*.partial') if directory.exists() else ():
        try:
            if now-item.stat().st_mtime >= minimum_age:
                item.unlink()
                removed += 1
        except FileNotFoundError:
            pass
    return removed


def preflight(path):
    size = Path(path).stat().st_size
    free = shutil.disk_usage(Path(path).parent).free
    required = int(size * 1.5) + MIN_FREE_RESERVE_BYTES
    if free < required:
        raise RuntimeError(f'Zu wenig freier Speicher für sichere Sicherung: {free} statt {required} Byte')
    return {'database_bytes': size, 'free_bytes': free, 'required_bytes': required}


def run_worker(kind, timeout):
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--worker', kind],
            check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f'Wartungsphase {kind} nach {timeout} Sekunden beendet') from None
    except subprocess.CalledProcessError:
        raise RuntimeError(f'Wartungsphase {kind} fehlgeschlagen') from None
    return result.stdout.strip()


def export_backup(target, destination, timeout=EXPORT_TIMEOUT_SECONDS):
    def expired(signum, frame):
        raise TimeoutError(f'Sicherungsexport nach {timeout} Sekunden beendet')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(timeout)
    try:
        with Path(target).open('rb') as file:
            shutil.copyfileobj(file, destination, length=1024*1024)
        destination.flush()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def cleanup_journals(path, now=None, rules=JOURNAL_RETENTION, batch_size=MAX_DELETE_PER_TABLE, record_status=True):
    """Löscht begrenzte alte Journalzeilen in kleinen, getrennten Transaktionen."""
    if batch_size < 1:
        raise ValueError('Löschgrenze muss positiv sein')
    now = time.time() if now is None else now
    result = {}
    for table, timestamp, days, extra_where in rules:
        if days < 1:
            raise ValueError('Aufbewahrungsfrist muss mindestens einen Tag betragen')
        with connect(path) as db:
            if not _table_exists(db, table):
                result[table] = {'deleted': 0, 'remaining_old': 0, 'missing': True}
                continue
            columns = {row['name'] for row in db.execute(f'PRAGMA table_info("{table}")')}
            if timestamp not in columns:
                raise RuntimeError(f'Zeitspalte {timestamp} fehlt in {table}')
            cutoff = now - days * 86400
            condition = f'"{timestamp}" < ?'
            parameters = [cutoff]
            if extra_where:
                condition += f' AND ({extra_where})'
            # Der neueste Eintrag bleibt selbst dann erhalten, wenn ein Dienst
            # lange nicht gelaufen ist. So verschwindet der letzte Fehler nicht.
            condition += f' AND rowid != (SELECT rowid FROM "{table}" ORDER BY "{timestamp}" DESC, rowid DESC LIMIT 1)'
            db.execute('BEGIN IMMEDIATE')
            limit = min(batch_size, TABLE_DELETE_LIMITS.get(table, batch_size))
            deleted = db.execute(
                f'DELETE FROM "{table}" WHERE rowid IN '
                f'(SELECT rowid FROM "{table}" WHERE {condition} ORDER BY "{timestamp}", rowid LIMIT ?)',
                (*parameters, limit),
            ).rowcount
            remaining = db.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {condition}', parameters).fetchone()[0]
        result[table] = {'deleted': deleted, 'remaining_old': remaining, 'missing': False}
    if record_status:
        write_maintenance_status(path, result, now)
    return result


def acquire_lock(lock, timeout=60):
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError('Wartungssperre nach 60 Sekunden nicht verfügbar')
            time.sleep(0.25)


def compact(path, now=None, raw_days=30, gap_seconds=15, max_minutes=None, max_seconds=None):
    if raw_days < 1:
        raise ValueError('Mindestens ein Tag Rohdaten erforderlich')
    now = time.time() if now is None else now
    cutoff = int((now - raw_days * 86400) // 60) * 60
    minutes = 0
    deadline = time.monotonic()+max_seconds if max_seconds is not None else None
    # Kleine Transaktionen, damit die Erfassung parallel weiterarbeiten kann.
    while True:
        if max_minutes is not None and minutes >= max_minutes:
            break
        if deadline is not None and time.monotonic() >= deadline:
            break
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE')
            first = db.execute('SELECT MIN(ts) FROM measurements WHERE ts<?', (cutoff,)).fetchone()[0]
            if first is None:
                break
            minute = int(first // 60) * 60
            rows = db.execute('SELECT * FROM measurements WHERE ts>=? AND ts<? ORDER BY ts', (minute, minute + 60)).fetchall()
            payload = summarize(rows, 60, gap_seconds)
            # Bei unerwartet nachträglich eingefügten Altdaten abbrechen statt Archiv überschreiben.
            db.execute('INSERT INTO minute_archive(minute,payload) VALUES (?,?)',
                       (minute, json.dumps(payload, allow_nan=False, separators=(',', ':'))))
            db.execute('DELETE FROM measurements WHERE ts>=? AND ts<?', (minute, minute + 60))
        minutes += 1
    return minutes


def old_measurement_rows(path, now=None, raw_days=30):
    now = time.time() if now is None else now
    cutoff = int((now - raw_days * 86400) // 60) * 60
    with connect(path) as db:
        return db.execute('SELECT COUNT(*) FROM measurements WHERE ts<?', (cutoff,)).fetchone()[0]


def backup(path, directory, keep=7):
    if keep < 1:
        raise ValueError('Mindestens eine Sicherung behalten')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = directory / f'marstek-{stamp}.sqlite3'
    temporary = directory / (target.name + '.partial')
    try:
        with closing(sqlite3.connect(path, timeout=30)) as source, closing(sqlite3.connect(temporary)) as destination:
            source.execute('PRAGMA busy_timeout=30000')
            # Ein zusammenhängender Backup-Schritt verhindert, dass der alle
            # fünf Sekunden schreibende Collector einen kleinen Seitenlauf
            # immer wieder zurücksetzt und dadurch unbegrenzt verlängert.
            source.backup(destination, pages=-1, sleep=0.05)
            if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('Integritätsprüfung der Sicherung fehlgeschlagen')
            destination.execute('PRAGMA journal_mode=DELETE')
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        # Atomarer Zeiger: Downloads erhalten immer ein fertig geprüftes Backup.
        link = directory / '.latest.tmp'
        link.unlink(missing_ok=True)
        link.symlink_to(target.name)
        os.replace(link, directory / 'latest.sqlite3')
        for old in sorted(directory.glob('marstek-*.sqlite3'), reverse=True)[keep:]:
            old.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return target


def worker(kind):
    config = load_settings()
    path = config['database_path']
    if kind == 'check':
        with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)) as db:
            db.execute('PRAGMA busy_timeout=30000')
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('Integritätsprüfung der Datenbank fehlgeschlagen')
        print('ok')
    elif kind == 'backup':
        print(backup(path, path.parent/'backups'))
    else:
        raise ValueError('Unbekannte Wartungsphase')


def full_maintenance(path, config):
    started = time.time()
    previous_success = None
    previous_retention = None
    with connect(path) as db:
        if _table_exists(db, 'maintenance_status'):
            row = db.execute('SELECT payload FROM maintenance_status WHERE id=1').fetchone()
            if row:
                try:
                    previous_payload=json.loads(row['payload'])
                    previous_success=previous_payload.get('last_success')
                    previous_retention=previous_payload.get('retention')
                except (AttributeError, TypeError, ValueError): pass
    status = {'version': 2, 'outcome': 'running', 'started': started, 'phase': 'Vorprüfung',
              'last_success': previous_success}
    if previous_retention:
        status['retention']=previous_retention
    write_maintenance_status(path, status)
    try:
        backup_dir = path.parent/'backups'
        removed = cleanup_partials(backup_dir)
        storage = preflight(path)
        run_worker('check', CHECK_TIMEOUT_SECONDS)
        status['phase'] = 'Sicherung'
        write_maintenance_status(path, status)
        target = Path(run_worker('backup', BACKUP_TIMEOUT_SECONDS))
        logging.info('Sicherung vor Wartung geprüft: %s', target)
        status['phase'] = 'Archivierung'
        write_maintenance_status(path, status)
        count = compact(path, gap_seconds=max(15, config['shelly']['poll_seconds'] * 3),
                        max_minutes=MAX_ARCHIVE_MINUTES, max_seconds=MAX_ARCHIVE_SECONDS)
        remaining = old_measurement_rows(path)
        logging.info('%d Minuten archiviert; %d alte Rohzeilen verbleiben.', count, remaining)
        status['phase'] = 'Journalbereinigung'
        write_maintenance_status(path, status)
        cleanup = cleanup_journals(path, record_status=False)
        deleted = sum(item['deleted'] for item in cleanup.values())
        pending = sum(item['remaining_old'] for item in cleanup.values())
        logging.info('%d alte Journalzeilen entfernt; %d warten auf den nächsten Lauf.', deleted, pending)
        retention=with_growth(retention_inventory(path),previous_retention)
        status.update(outcome='success', phase='Abgeschlossen', finished=time.time(),
                      last_success=time.time(), duration_seconds=time.time()-started,
                      backup_bytes=target.stat().st_size, archived_minutes=count,
                      remaining_old_measurements=remaining, journal_deleted=deleted,
                      journal_remaining=pending, partials_removed=removed, storage=storage,
                      retention=retention)
        write_maintenance_status(path, status)
        return target
    except Exception as error:
        cleanup_partials(path.parent/'backups', minimum_age=0)
        status.update(outcome='error', phase=status.get('phase','Unbekannt'), finished=time.time(),
                      duration_seconds=time.time()-started, error=str(error))
        write_maintenance_status(path, status)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-only', action='store_true')
    parser.add_argument('--export-backup', action='store_true', help='Geprüfte Sicherung binär auf stdout ausgeben')
    parser.add_argument('--worker', choices=('backup','check'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return 0
    config = load_settings()
    path = config['database_path']
    initialize(path)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    with open(str(path) + '.maintenance.lock', 'a') as lock:
        acquire_lock(lock)
        if not (args.backup_only or args.export_backup):
            target = full_maintenance(path, config)
        else:
            preflight(path)
            run_worker('check', CHECK_TIMEOUT_SECONDS)
            target = Path(run_worker('backup', BACKUP_TIMEOUT_SECONDS))
            logging.info('Sicherung geprüft: %s', target)
        if args.export_backup:
            export_backup(target, sys.stdout.buffer)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
