"""Empfängt ausschließlich Sicherungsrückmeldungen über einen eingeschränkten SSH-Schlüssel."""
import json
import sys
import time
from database import connect
from settings import load_settings


def initialize_backup(path):
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS backup_status (id INTEGER PRIMARY KEY CHECK(id=1), last_success REAL, last_attempt REAL NOT NULL, outcome TEXT NOT NULL)')


def record(path, outcome, now=None):
    if outcome not in ('success','failure'):
        raise ValueError('Ungültige Rückmeldung')
    now=time.time() if now is None else now
    initialize_backup(path)
    with connect(path) as db:
        db.execute('''INSERT INTO backup_status VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET
            last_success=CASE WHEN excluded.outcome='success' THEN excluded.last_success ELSE backup_status.last_success END,
            last_attempt=excluded.last_attempt,outcome=excluded.outcome''',
            (now if outcome=='success' else None,now,outcome))


def status(path,now):
    with connect(path) as db:row=db.execute('SELECT * FROM backup_status WHERE id=1').fetchone()
    if row is None:return dict(level='neutral',label='Noch keine Rückmeldung',last_success=None,last_attempt=None,display_time=None,error=None)
    success=row['last_success']
    overdue=success is not None and not 0<=now-success<=36*3600
    failed=row['outcome']=='failure'
    return dict(level='warn' if failed or overdue else 'ok',
                label='Letzter Versuch fehlgeschlagen' if row['outcome']=='failure' else 'Überfällig' if overdue else 'Aktuell · auf Mac geprüft',
                last_success=success,last_attempt=row['last_attempt'],
                display_time=row['last_attempt'] if failed else success,
                error='Mac meldet fehlgeschlagene Sicherung; die letzte erfolgreiche Kopie bleibt erhalten' if failed else None)

if __name__=='__main__':
    outcome=sys.stdin.read(32).strip()
    record(load_settings()['database_path'],outcome)
    print('Sicherungsstatus gespeichert')
