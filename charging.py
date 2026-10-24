"""Vermutetes Autoladen aus Netzbezug. Keine Gerätebefehle."""
import math
import time
from controller import Controller
from database import connect


def initialize_charging(path):
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS charging_state (
            id INTEGER PRIMARY KEY CHECK(id=1), active INTEGER NOT NULL,
            updated_at REAL NOT NULL, valid INTEGER NOT NULL,
            active_since REAL, pending TEXT, remaining REAL,
            start_w REAL NOT NULL, stop_w REAL NOT NULL, hold_s REAL NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS charging_events (
            id INTEGER PRIMARY KEY, detected_at REAL NOT NULL, event TEXT NOT NULL,
            condition_since REAL NOT NULL, power_w REAL NOT NULL,
            start_w REAL NOT NULL, stop_w REAL NOT NULL, hold_s REAL NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS charging_event_time ON charging_events(detected_at)')
        state_columns={r['name'] for r in db.execute('PRAGMA table_info(charging_state)')}
        event_columns={r['name'] for r in db.execute('PRAGMA table_info(charging_events)')}
        additions={'reason':'TEXT','net_power_w':'REAL','corrected_power_w':'REAL','battery_discharge_w':'REAL',
                   'protection_w':'REAL NOT NULL DEFAULT 750','protection_hold_s':'REAL NOT NULL DEFAULT 600'}
        for name,definition in additions.items():
            if name not in state_columns:db.execute(f'ALTER TABLE charging_state ADD COLUMN {name} {definition}')
        if 'reason' not in event_columns:db.execute('ALTER TABLE charging_events ADD COLUMN reason TEXT')


def latest_battery_discharge(path,ts,max_age=90):
    with connect(path) as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='marstek_samples'").fetchone()
        row=db.execute('SELECT ts,ac_power_w,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone() if exists else None
    if not row or row['error'] or row['ac_power_w'] is None or not 0<=ts-row['ts']<=max_age:return None
    return max(0,float(row['ac_power_w']))


class ChargingRecorder:
    def __init__(self,path,rule):
        self.path=path
        start,stop,hold,gap=(float(rule[k]) for k in ('block_above_w','release_below_w','hold_seconds','max_gap_seconds'))
        protection=float(rule.get('sustained_discharge_w',750));protection_hold=float(rule.get('sustained_discharge_seconds',600))
        if not all(math.isfinite(v) for v in (start,stop,hold,gap,protection,protection_hold)) or not 0<=stop<start or hold<=0 or gap<=0 or not 0<=protection<=800 or protection_hold<=0:
            raise ValueError('Ungültige Autolade-Erkennungsregel')
        initialize_charging(path)
        with connect(path) as db:previous=db.execute('SELECT * FROM charging_state WHERE id=1').fetchone()
        self.controller=Controller(start,stop,hold,gap,protection,protection_hold,blocked=bool(previous and previous['active']))
        self.active_since=previous['active_since'] if previous else None
        self.active_reason=previous['reason'] if previous and previous['active'] else None
        # Nach Neustart keine unbeobachtete Zeit auf die Dreiminutenfrist anrechnen.

    def update(self,power,ts,monotonic,battery_discharge=None):
        c=self.controller
        valid=power is not None and math.isfinite(power)
        battery_valid=battery_discharge is not None and math.isfinite(battery_discharge) and battery_discharge>=0
        corrected=power+(battery_discharge if battery_valid else 0) if valid else None
        load_candidate=c.since;protection_candidate=c.sustained_since;ended_reason=self.active_reason
        action=c.update(corrected if valid else None,monotonic,battery_discharge if battery_valid else None)
        event=None
        if action:
            event='START_DETECTED' if c.blocked else 'END_DETECTED'
            if c.blocked:
                self.active_since=ts
                self.active_reason='sustained_discharge' if action=='WUERDE_SPERREN_DAUERLAST' else 'corrected_load'
            else:self.active_since=None;self.active_reason=None
        pending_info=c.pending(monotonic);pending=pending_info[0] if pending_info else None;remaining=pending_info[1] if pending_info else None
        event_reason=self.active_reason if c.blocked else ended_reason
        candidate=protection_candidate if action=='WUERDE_SPERREN_DAUERLAST' else load_candidate
        with connect(self.path) as db:
            if event:
                event_hold=c.sustained_discharge_s if action=='WUERDE_SPERREN_DAUERLAST' else c.hold_s
                db.execute('INSERT INTO charging_events(detected_at,event,condition_since,power_w,start_w,stop_w,hold_s,reason) VALUES (?,?,?,?,?,?,?,?)',
                           (ts,event,ts-(monotonic-candidate),corrected,c.block_w,c.release_w,event_hold,event_reason))
            db.execute('''INSERT INTO charging_state
                (id,active,updated_at,valid,active_since,pending,remaining,start_w,stop_w,hold_s,reason,net_power_w,corrected_power_w,battery_discharge_w,protection_w,protection_hold_s)
                VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET active=excluded.active,updated_at=excluded.updated_at,
                valid=excluded.valid,active_since=excluded.active_since,pending=excluded.pending,
                remaining=excluded.remaining,start_w=excluded.start_w,stop_w=excluded.stop_w,hold_s=excluded.hold_s,
                reason=excluded.reason,net_power_w=excluded.net_power_w,corrected_power_w=excluded.corrected_power_w,
                battery_discharge_w=excluded.battery_discharge_w,protection_w=excluded.protection_w,
                protection_hold_s=excluded.protection_hold_s''',
                       (int(c.blocked),ts,int(valid),self.active_since,pending,remaining,c.block_w,c.release_w,c.hold_s,
                        self.active_reason,power if valid else None,corrected,battery_discharge if battery_valid else None,
                        c.sustained_discharge_w,c.sustained_discharge_s))
        return event


def charging_status(path,now=None):
    now=time.time() if now is None else now
    with connect(path) as db:
        row=db.execute('SELECT * FROM charging_state WHERE id=1').fetchone()
        events=db.execute('SELECT detected_at,event,condition_since,power_w,reason FROM charging_events ORDER BY detected_at DESC,id DESC LIMIT 10').fetchall()
    state=dict(row) if row else None
    from preferences import read_preferences
    prefs=read_preferences(path)
    return {'state':state,'stale':state is None or not state['valid'] or not 0<=now-state['updated_at']<=20,
            'discharge_limit_w':prefs['ev_discharge_limit_w'],'max_gap_seconds':prefs['max_gap_seconds'],
            'marstek_interval_seconds':prefs['marstek_interval_seconds'],
            'events':[dict(e) for e in events]}
