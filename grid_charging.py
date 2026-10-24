"""Explicitly requested grid charging through reserved Marstek schedule six."""
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from database import connect
from preferences import read_preferences

ZONE = ZoneInfo('Europe/Berlin')

def initialize_grid_charging(path):
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS grid_charge_requests(
            id INTEGER PRIMARY KEY, created REAL NOT NULL, status TEXT NOT NULL,
            payload TEXT NOT NULL, message TEXT NOT NULL, updated REAL NOT NULL)''')

def _quarter_after(timestamp):
    return int((timestamp+899)//900*900)

def _manual_start(spec,now):
    mode=spec.get('start_mode')
    if mode=='now':return int(now//60*60)
    if mode=='delay':
        hours=float(spec.get('delay_hours',0))
        if not .25<=hours<=24:raise ValueError('Startverzögerung: 0,25 bis 24 Stunden.')
        return _quarter_after(now+hours*3600)
    if mode=='at':
        try:value=datetime.fromisoformat(str(spec.get('start_at',''))).replace(tzinfo=ZONE).timestamp()
        except ValueError as error:raise ValueError('Bitte eine gültige Startzeit wählen.') from error
        if value<now+60 or value>now+24*3600:raise ValueError('Startzeit muss zwischen einer Minute und 24 Stunden in der Zukunft liegen.')
        return value
    raise ValueError('Startart muss jetzt, verzögert oder Uhrzeit sein.')

def manual_plan(path,spec,now=None):
    now=time.time() if now is None else now
    if not isinstance(spec,dict):raise ValueError('Ungültiger Ladeauftrag.')
    prefs=read_preferences(path);start=_manual_start(spec,now)
    try:power=int(spec.get('power_w',0))
    except (TypeError,ValueError) as error:raise ValueError('Bitte eine gültige Ladeleistung wählen.') from error
    if not 50<=power<=2500 or power%50:raise ValueError('Ladeleistung: 50 bis 2.500 W in 50-W-Schritten.')
    with connect(path) as db:
        sample=db.execute('SELECT ts,soc,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone()
        meta=db.execute('SELECT home_id FROM tibber_meta WHERE id=1').fetchone()
    if not sample or sample['error'] or not 0<=now-sample['ts']<=90:raise ValueError('Aktueller Akku-Ladestand fehlt.')
    soc=float(sample['soc']);efficiency=prefs['plan_efficiency']/100;capacity=prefs['plan_capacity_kwh'];maximum=100
    target_mode=spec.get('target_mode')
    if target_mode=='energy':
        try:energy=float(spec.get('energy_kwh',0))
        except (TypeError,ValueError) as error:raise ValueError('Bitte eine gültige Energiemenge wählen.') from error
        if not .1<=energy<=10:raise ValueError('Energiemenge: 0,1 bis 10 kWh.')
        possible=max(0,(maximum-soc)/100*capacity);stored=min(energy,possible)
        duration=stored/(power/1000*efficiency) if stored else 0
    elif target_mode=='duration':
        try:duration=float(spec.get('duration_hours',0))
        except (TypeError,ValueError) as error:raise ValueError('Bitte eine gültige Ladedauer wählen.') from error
        if not .25<=duration<=12:raise ValueError('Ladedauer: 0,25 bis 12 Stunden.')
        possible=max(0,(maximum-soc)/100*capacity);stored=min(power/1000*duration*efficiency,possible)
        duration=stored/(power/1000*efficiency) if stored else 0
    else:raise ValueError('Ladeziel muss Energiemenge oder Dauer sein.')
    if stored<=0:raise ValueError(f'Der Akku hat den maximalen Ziel-SOC von {maximum:g} % bereits erreicht.')
    end=int((start+duration*3600)//60*60)
    if end<=start:raise ValueError('Die berechnete Ladedauer ist zu kurz.')
    duration=(end-start)/3600;stored=min(power/1000*duration*efficiency,max(0,(maximum-soc)/100*capacity))
    input_kwh=power/1000*duration;target=min(maximum,soc+stored/capacity*100)
    start_dt=datetime.fromtimestamp(start,ZONE);end_dt=datetime.fromtimestamp(end,ZONE)
    if start_dt.date()!=end_dt.date():raise ValueError('Der Ladeauftrag muss vor Mitternacht enden.')
    average=None
    if meta:
        with connect(path) as db:rows=db.execute('SELECT starts_at,ends_at,total FROM tibber_prices WHERE home_id=? AND starts_at<? AND ends_at>? ORDER BY starts_at',(meta['home_id'],end,start)).fetchall()
        weighted=sum(max(0,min(end,r['ends_at'])-max(start,r['starts_at']))*r['total']*100 for r in rows)
        seconds=sum(max(0,min(end,r['ends_at'])-max(start,r['starts_at'])) for r in rows)
        if seconds>=duration*3600*.95:average=weighted/seconds
    return {'available':True,'message':'Manuell gewählter Ladeauftrag.','created':now,'soc':soc,'target_soc':target,
            'start':start,'end':end,'power_w':power,'stored_kwh':stored,'input_kwh':input_kwh,
            'average_ct':average,'estimated_cost_eur':None if average is None else input_kwh*average/100,
            'slot':6,'simulation':False,'control_version':2,'expires':now+300,'manual':True}

def request(path,spec,now=None):
    now=time.time() if now is None else now;p=manual_plan(path,spec,now)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute("SELECT id,payload FROM grid_charge_requests WHERE status='confirmed'").fetchall()
        for row in rows:
            if now>json.loads(row['payload']).get('expires',0):
                db.execute("UPDATE grid_charge_requests SET status='expired',message='Bestätigung abgelaufen',updated=? WHERE id=?",(now,row['id']))
        active=db.execute("SELECT id FROM grid_charge_requests WHERE status IN ('confirmed','processing','scheduled','active','cancel_requested')").fetchone()
        if active:raise ValueError('Es besteht bereits ein Netzladeauftrag.')
        db.execute("INSERT INTO grid_charge_requests(created,status,payload,message,updated) VALUES (?,'confirmed',?,'Ladeauftrag gespeichert · Vorbereitung durch Akku-Worker',?)",(now,json.dumps(p,ensure_ascii=False),now))
    return request_status(path,now)

def request_status(path, now=None):
    now=time.time() if now is None else now
    with connect(path) as db:row=db.execute('SELECT * FROM grid_charge_requests ORDER BY id DESC LIMIT 1').fetchone()
    item=dict(row) if row else None
    if item:
        item['proposal']=json.loads(item.pop('payload'))
        if item['status']=='confirmed' and now>item['proposal'].get('expires',0):
            item.update(status='expired',message='Bestätigung abgelaufen',updated=now)
            with connect(path) as db:db.execute("UPDATE grid_charge_requests SET status='expired',message=?,updated=? WHERE id=?",(item['message'],now,item['id']))
    return {'request':item,'live_writes':True}

def _set(path,item,status,message,now):
    with connect(path) as db:
        db.execute('UPDATE grid_charge_requests SET status=?,message=?,updated=? WHERE id=?',(status,message,now,item['id']))
        db.execute('INSERT INTO marstek_control_events(ts,event,value_w,detail) VALUES (?,?,?,?)',(now,'GRID_CHARGE_'+status.upper(),item['proposal'].get('power_w'),message))

def _minutes(raw):
    hour,minute=divmod(raw,100)
    if hour>23 or minute>59:raise ValueError('Ungültige Zeit in vorhandenem Marstek-Zeitplan')
    return hour*60+minute

def _overlap(schedule,start,end,day_bit):
    days,start_raw,end_raw,_,enabled=schedule
    if not enabled or not days&day_bit:return False
    a,b=_minutes(start_raw),_minutes(end_raw);x=start.hour*60+start.minute;y=end.hour*60+end.minute
    if b<=a:return True # Tageswechsel konservativ blockieren.
    return max(a,x)<min(b,y)

def cancel(path, now=None):
    now=time.time() if now is None else now
    with connect(path) as db:row=db.execute('SELECT * FROM grid_charge_requests ORDER BY id DESC LIMIT 1').fetchone()
    if not row or row['status'] not in ('confirmed','processing','scheduled','active'):raise ValueError('Keine laufende Netzladung.')
    item=dict(row);item['proposal']=json.loads(item['payload'])
    if item['status']=='confirmed':
        _set(path,item,'done','Ladeauftrag vor Einrichtung abgebrochen · Eigenverbrauch blieb aktiv',now)
        return request_status(path,now)
    _set(path,item,'cancel_requested','Abbruch und Eigenverbrauch angefordert',now)
    return request_status(path,now)

def process(path,device,now=None):
    now=time.time() if now is None else now
    with connect(path) as db:row=db.execute("SELECT * FROM grid_charge_requests WHERE status IN ('confirmed','processing','scheduled','active','cancel_requested') ORDER BY id DESC LIMIT 1").fetchone()
    if not row:return False
    item=dict(row);item['proposal']=json.loads(item.pop('payload'));p=item['proposal']
    if p.get('simulation') is not False or p.get('control_version') not in (1,2):
        _set(path,item,'expired','Alter Testauftrag wurde nicht ausgeführt',now);return True
    try:
        limit,mode,rs485=device.read()
        start=datetime.fromtimestamp(p['start'],ZONE);end=datetime.fromtimestamp(p['end'],ZONE);day_bit=1<<start.weekday()
        expected=(day_bit,start.hour*100+start.minute,end.hour*100+end.minute,(-int(p['power_w']))&0xffff,1)
        if item['status']=='processing':
            actual=device.read_schedule(6)
            if actual==expected and rs485==21947:
                if mode==0:
                    _set(path,item,'active',f'Netzladung aktiv bis {end:%H:%M} Uhr',now);return True
                if mode==1 and now<start.timestamp():
                    _set(path,item,'scheduled',f'Netzladung eingeplant · Eigenverbrauch bis {start:%H:%M} Uhr',now);return True
                if mode==1:
                    device.set_manual();_,mode2,rs4852=device.read()
                    if mode2!=0 or rs4852!=21947:raise ValueError('Manueller Modus nicht bestätigt')
                    _set(path,item,'active',f'Netzladung aktiv bis {end:%H:%M} Uhr',now);return True
            if mode==1 and rs485==21947 and actual!=(0,0,0,0,0):
                device.clear_schedule_six();_set(path,item,'error','Unvollständiger Start sicher beendet; Eigenverbrauch blieb aktiv',now);return True
            raise ValueError('Startzustand nach Verbindungsabbruch unklar')
        if item['status']=='confirmed':
            if now>p['expires'] or now>=p['end']:_set(path,item,'expired','Bestätigung oder Ladefenster abgelaufen',now);return True
            if mode!=1 or rs485!=21947:raise ValueError('Marstek ist nicht im freigegebenen Eigenverbrauch')
            slot6=device.read_schedule(6)
            if slot6[4]!=0:raise ValueError('Zeitplan 6 ist noch aktiv')
            for slot in range(1,6):
                if _overlap(device.read_schedule(slot),start,end,day_bit):raise ValueError(f'Zeitplan {slot} überschneidet das Ladefenster')
            _set(path,item,'processing','Zeitplan wird geschrieben',now)
            item['status']='processing'
            device.write_schedule_six(day_bit,start.hour*100+start.minute,end.hour*100+end.minute,-int(p['power_w']),1)
            if now<start.timestamp():
                _set(path,item,'scheduled',f'Netzladung eingeplant · Eigenverbrauch bis {start:%H:%M} Uhr',now);return True
            device.set_manual()
            _,mode2,rs4852=device.read()
            if mode2!=0 or rs4852!=21947:raise ValueError('Manueller Modus nicht bestätigt')
            _set(path,item,'active',f'Netzladung aktiv bis {end:%H:%M} Uhr',now);return True
        actual=device.read_schedule(6)
        expected_disabled=(*expected[:4],0)
        if actual not in (expected,expected_disabled):
            _set(path,item,'error','Zeitplan 6 wurde extern verändert · keine weiteren Gerätebefehle · bitte in der App auf Eigenverbrauch wechseln',now)
            return True
        if item['status']=='scheduled':
            if actual!=expected:
                _set(path,item,'error','Eingeplanter Zeitplan wurde vor Ladebeginn deaktiviert · keine weiteren Gerätebefehle',now);return True
            if mode!=1:
                _set(path,item,'error','Betriebsart wurde vor Ladebeginn extern verändert · keine weiteren Gerätebefehle',now);return True
            if now<start.timestamp():return True
            if now>=end.timestamp():
                device.clear_schedule_six();_set(path,item,'expired','Ladefenster beendet · Eigenverbrauch blieb aktiv',now);return True
            with connect(path) as db:s=db.execute('SELECT ts,soc,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone()
            if s and not s['error'] and 0<=now-s['ts']<=90 and float(s['soc'])>=p['target_soc']:
                device.clear_schedule_six();_set(path,item,'done','Ziel-SOC vor Ladebeginn erreicht · Eigenverbrauch blieb aktiv',now);return True
            device.set_manual();_,mode2,rs4852=device.read()
            if mode2!=0 or rs4852!=21947:raise ValueError('Manueller Modus zum Ladebeginn nicht bestätigt')
            _set(path,item,'active',f'Netzladung aktiv bis {end:%H:%M} Uhr',now);return True
        soc=None
        with connect(path) as db:s=db.execute('SELECT ts,soc,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone()
        if s and not s['error'] and 0<=now-s['ts']<=90:soc=float(s['soc'])
        stop=item['status']=='cancel_requested' or now>=p['end'] or (soc is not None and soc>=p['target_soc'])
        if stop:
            if mode!=1:device.set_self_consumption()
            _,mode2,rs4852=device.read()
            if mode2!=1 or rs4852!=21947:raise ValueError('Eigenverbrauch nicht bestätigt')
            device.clear_schedule_six()
            reason='abgebrochen' if item['status']=='cancel_requested' else 'Ziel-SOC erreicht' if soc is not None and soc>=p['target_soc'] else 'Endzeit erreicht'
            _set(path,item,'done',f'Netzladung beendet · {reason} · Eigenverbrauch bestätigt',now);return True
        if mode!=0:
            _set(path,item,'error','Betriebsart wurde extern verändert · keine weiteren Gerätebefehle · bitte Zeitplan 6 in der App prüfen',now)
            return True
        return True
    except (OSError,ValueError) as error:
        # Während aktiver Ladung weiter versuchen, damit Endzeit und Rückkehr nachgeholt werden.
        status=item['status'] if item['status'] in ('scheduled','active','cancel_requested') else 'error'
        _set(path,item,status,f'Netzladung prüfen: {error}',now);return True
