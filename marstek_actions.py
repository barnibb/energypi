"""Persistente, ausdrücklich vom Browser angeforderte Moduswechsel; ein Worker."""
import time
from database import connect
from preferences import read_preferences
from charging import charging_status
from marstek_control import control_status, persist, observe, confirmed_message, latest_soc, update_soc_safety


def initialize_actions(path):
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS marstek_actions (
            id INTEGER PRIMARY KEY, created REAL NOT NULL, status TEXT NOT NULL,
            message TEXT NOT NULL, updated REAL NOT NULL)''')


def action_status(path):
    with connect(path) as db:
        row=db.execute('SELECT * FROM marstek_actions ORDER BY id DESC LIMIT 1').fetchone()
    return dict(row) if row else None


def request_mode(path, now=None):
    now=time.time() if now is None else now
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute("SELECT id FROM marstek_actions WHERE status IN ('pending','processing') LIMIT 1").fetchone()
        if not existing:
            db.execute("INSERT INTO marstek_actions(created,status,message,updated) VALUES (?,'pending','Eigenverbrauch angefordert',?)",(now,now))
            db.execute("INSERT INTO marstek_control_events(ts,event,detail) VALUES (?,'USER_MODE_REQUEST','Eigenverbrauch per Button angefordert')",(now,))
    return action_status(path)


def update(path, item, status, message, now):
    with connect(path) as db:
        previous=db.execute('SELECT status,message FROM marstek_actions WHERE id=?',(item['id'],)).fetchone()
        db.execute('UPDATE marstek_actions SET status=?,message=?,updated=? WHERE id=?',(status,message,now,item['id']))
        if previous and (previous['status'],previous['message'])!=(status,message):
            db.execute('INSERT INTO marstek_control_events(ts,event,detail) VALUES (?,?,?)',(now,'ACTION_'+status.upper(),message))


def process(path, device, now=None):
    now=time.time() if now is None else now
    item=action_status(path)
    if not item or item['status'] not in ('pending','processing'):return False
    state=control_status(path);prefs=read_preferences(path)
    try:
        current,mode,rs485=device.read()
        observe(state,current,mode,rs485,now)
        persist(path,state,now)
        if item['status']=='processing':
            # No replay of an ambiguous mode change after a crash/lost response.
            success=mode==1 and rs485==21947
            update(path,item,'done' if success else 'error',
                   'Eigenverbrauch bestätigt' if success else 'Wechsel nicht bestätigt; bitte erneut anfordern.',now)
            return True
        if now-item['created']>2*prefs['marstek_interval_seconds']+120:
            update(path,item,'error','Anforderung abgelaufen; bitte erneut anfordern.',now);return True
        if rs485!=21947:
            update(path,item,'error','RS485-Zwangssteuerung aktiv; bitte zuerst in der App beenden.',now);return True
        charging=charging_status(path,now)
        if charging['stale']:
            update(path,item,'pending','Warte auf aktuelle Autolade-Erkennung',now);return True
        # Der ausdrückliche Benutzerauftrag darf eine vorherige Schutzgrenze sofort
        # freigeben. Der Mindestabstand gilt weiterhin für automatische Änderungen.
        if state['conflict'] or (state['baseline'] is not None and current!=state['applied']):
            state.update(baseline=None,applied=None,pending=None,conflict=False)
        active=bool(charging['state']['active'])
        soc_limit,_=update_soc_safety(state,latest_soc(path,now),now,prefs)
        base=int(state['baseline']) if state['baseline'] is not None else current
        cap=min(base,int(prefs['ev_discharge_limit_w']) if active else base,
                int(soc_limit) if soc_limit is not None else base)
        update(path,item,'processing','Wechsel wird ausgeführt',now)
        state['message']='Eigenverbrauch ausdrücklich angefordert'
        persist(path,state,now,'MODE_REQUEST',1)
        if cap!=current:
            if state['baseline'] is None and cap<current:state['baseline']=current
            state['applied']=current;state['pending']=cap
            state['pending_reason']='soc_limit' if soc_limit is not None and cap==soc_limit else 'ev_limit'
            state['last_attempt']=now
            persist(path,state,now,'REQUEST',cap)
            device.write_limit(cap)
            if device.read()[0]!=cap:raise ValueError('Grenze nicht bestätigt')
            state.update(applied=cap,pending=None,observed_limit_w=cap)
            state['message']=confirmed_message(state,cap)
            persist(path,state,now,'CONFIRMED',cap)
            if state['baseline'] is not None and cap==base and not active:
                state.update(baseline=None,applied=None,pending_reason=None)
        if mode!=1:device.set_self_consumption()
        limit,confirmed,control=device.read()
        if confirmed!=1 or control!=21947:raise ValueError('Betriebsart nicht bestätigt')
        observe(state,limit,confirmed,control,now)
        state['message']='Eigenverbrauch bestätigt'
        persist(path,state,now,'MODE_CONFIRMED',1)
        update(path,item,'done','Eigenverbrauch bestätigt',now)
    except (OSError,ValueError):
        update(path,item,'error','Wechsel nicht bestätigt · Gerätestatus prüfen und bei Bedarf erneut anfordern.',now)
    return True
