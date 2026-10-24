"""Persistente Lüfteranforderung; ausschließlich der Hintergrunddienst schaltet."""
import time
from database import connect
from preferences import read_preferences


def initialize_fan(path):
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS fan_state (
            id INTEGER PRIMARY KEY CHECK(id=1), uuid TEXT, revision INTEGER NOT NULL DEFAULT 0,
            desired INTEGER, deadline REAL, observed INTEGER, checked REAL, error TEXT)''')
        db.execute('INSERT OR IGNORE INTO fan_state(id) VALUES(1)')
        db.execute('CREATE TABLE IF NOT EXISTS fan_events(id INTEGER PRIMARY KEY,ts REAL,action TEXT,deadline REAL)')


def state(path):
    with connect(path) as db:return dict(db.execute('SELECT * FROM fan_state WHERE id=1').fetchone())


def status(path, now=None):
    now=time.time() if now is None else now
    s=state(path)
    fresh=s['checked'] is not None and 0<=now-s['checked']<=90 and not s['error']
    return dict(observed=bool(s['observed']) if fresh and s['observed'] is not None else None,
                available=bool(s['uuid']) and fresh,desired=s['desired'],deadline=s['deadline'],
                remaining_seconds=max(0,s['deadline']-now) if s['deadline'] is not None else None,
                error=s['error'],checked=s['checked'],duration_minutes=read_preferences(path)['fan_minutes'])


def request_action(path,action,now=None):
    now=time.time() if now is None else now
    if action not in ('start','stop'):raise ValueError('Ungültige Lüfteraktion')
    minutes=read_preferences(path)['fan_minutes']
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        s=dict(db.execute('SELECT * FROM fan_state WHERE id=1').fetchone())
        if action=='start' and (not s['uuid'] or s['checked'] is None or not 0<=now-s['checked']<=90 or s['error']):
            raise ValueError('Lüfter nicht bereit. Zugangsdaten und Hintergrunddienst prüfen.')
        deadline=now+minutes*60 if action=='start' else None
        db.execute('UPDATE fan_state SET revision=revision+1,desired=?,deadline=? WHERE id=1',(int(action=='start'),deadline))
        db.execute('INSERT INTO fan_events(ts,action,deadline) VALUES(?,?,?)',(now,action,deadline))


def expire(path,now):
    with connect(path) as db:
        row=db.execute('SELECT deadline FROM fan_state WHERE id=1').fetchone()
        if row['deadline'] is not None and row['deadline']<=now:
            db.execute('UPDATE fan_state SET desired=0,deadline=NULL,revision=revision+1 WHERE id=1')
            db.execute("INSERT INTO fan_events(ts,action) VALUES(?,'expired')",(now,))


def observe(path,on,now):
    with connect(path) as db:db.execute('UPDATE fan_state SET observed=?,checked=?,error=NULL WHERE id=1',(int(on),now))


def acknowledge(path,revision):
    with connect(path) as db:
        # Ein Ausschaltauftrag bleibt bis zur bestätigten Abschaltung bestehen.
        db.execute('UPDATE fan_state SET desired=NULL WHERE id=1 AND revision=? AND desired=0',(revision,))


def failure(path,message):
    with connect(path) as db:db.execute('UPDATE fan_state SET error=? WHERE id=1',(message,))


def select_device(path,devices):
    saved=state(path)['uuid']
    matches=[d for d in devices if (d.uuid==saved if saved else d.name=='Lüfter Bad')]
    if len(matches)!=1:raise ValueError('Lüfter Bad nicht eindeutig gefunden; keine Schaltung.')
    device=matches[0]
    if not saved:
        with connect(path) as db:db.execute('UPDATE fan_state SET uuid=? WHERE id=1',(device.uuid,))
    return device
