"""Forecast.Solar: versionierte Prognosen für den lokal konfigurierten Anlagenstandort."""
from datetime import date, datetime, timedelta
import json
import logging
import math
import time
import tomllib
from urllib.request import build_opener, ProxyHandler
from urllib.error import HTTPError
from zoneinfo import ZoneInfo
from database import connect, initialize
from settings import ROOT, load_settings

ZONE = ZoneInfo('Europe/Berlin')


def initialize_forecast(path):
    initialize(path)
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS forecast_runs (id INTEGER PRIMARY KEY, ts REAL NOT NULL, error TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS forecast_days (run_id INTEGER NOT NULL, day TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,day))')
        db.execute('CREATE INDEX IF NOT EXISTS forecast_day ON forecast_days(day,run_id)')


def plant():
    path=ROOT/'forecast.toml'
    if not path.exists():path=ROOT/'forecast.example.toml'
    with path.open('rb') as file:
        config=tomllib.load(file)
    for key, low, high in (('latitude',-90,90),('longitude',-180,180),('kwp',0.001,1000),('tilt',0,90),('azimuth',0,360)):
        v=config.get(key)
        if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Ungültige Anlagenparameter')
    if not isinstance(config.get('name'),str) or not config['name'].strip():
        raise ValueError('Ungültiger Standortname')
    return config


def forecast_url(config):
    azimuth=config['azimuth']-180
    return 'https://api.forecast.solar/estimate/{latitude}/{longitude}/{tilt}/{azimuth}/{kwp}'.format(**{**config,'azimuth':azimuth})


def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise ValueError('Ungültiger Prognosewert')
    return float(value)


def normalize(data):
    if data.get('message',{}).get('type') != 'success':
        raise ValueError('Prognosedienst meldet Fehler')
    result=data['result']
    zone=ZoneInfo(data['message'].get('info',{}).get('timezone','Europe/Berlin'))
    if str(zone) != 'Europe/Berlin':
        raise ValueError('Unerwartete Zeitzone')
    days={}
    for day, value in result['watt_hours_day'].items():
        date.fromisoformat(day)
        days[day]={'total_kwh':number(value)/1000,'points':[],'cumulative':[]}
    for field,target,key in (('watts','points','w'),('watt_hours','cumulative','wh')):
        for stamp,value in result[field].items():
            dt=datetime.fromisoformat(stamp)
            dt=dt.replace(tzinfo=zone) if dt.tzinfo is None else dt.astimezone(zone)
            day=dt.date().isoformat()
            if day in days:
                days[day][target].append({'ts':dt.timestamp(),key:number(value)})
    if not days:
        raise ValueError('Prognose ist leer')
    for d in days.values():
        for field in ('points','cumulative'):
            d[field].sort(key=lambda p:p['ts'])
            if len(d[field])<2:
                raise ValueError('Prognose unvollständig')
        if any(b['wh']<a['wh'] for a,b in zip(d['cumulative'],d['cumulative'][1:])):
            raise ValueError('Energieverlauf ist nicht monoton')
    return days


def fetch(config):
    try:
        with build_opener(ProxyHandler({})).open(forecast_url(config),timeout=20) as response:
            raw=response.read(500_001)
            if len(raw)>500_000:raise ValueError('Antwort zu groß')
            return normalize(json.loads(raw))
    except HTTPError as error:
        raise ValueError(f'Forecast.Solar HTTP {error.code}') from None
    except (OSError,ValueError,KeyError,TypeError):
        raise ValueError('Forecast.Solar nicht erreichbar oder Antwort ungültig') from None


def store_days(path, run_id, days):
    with connect(path) as db:
        for day,payload in days.items():
            db.execute('INSERT INTO forecast_days VALUES (?,?,?)',(run_id,day,json.dumps(payload,allow_nan=False)))
        db.execute('UPDATE forecast_runs SET error=NULL WHERE id=?',(run_id,))


def collect_forecast(path, config, now=None, fetcher=fetch):
    now=time.time() if now is None else now
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        last=db.execute('SELECT MAX(ts) FROM forecast_runs').fetchone()[0]
        if last is not None and (now<last or int(now//7200)==int(last//7200)):
            return 'Prognoseintervall noch nicht erreicht'
        run_id=db.execute('INSERT INTO forecast_runs(ts,error) VALUES (?,?)',(now,'Prognoseabruf nicht abgeschlossen')).lastrowid
    try:
        days=fetcher(config)
    except ValueError as error:
        with connect(path) as db:db.execute('UPDATE forecast_runs SET error=? WHERE id=?',(str(error),run_id))
        return str(error)
    store_days(path,run_id,days)
    return 'Prognose gespeichert'


def latest_day(db, day):
    row=db.execute('SELECT r.ts,d.payload FROM forecast_days d JOIN forecast_runs r ON r.id=d.run_id WHERE d.day=? AND r.error IS NULL ORDER BY r.ts DESC LIMIT 1',(day,)).fetchone()
    return {'issued_at':row['ts'],**json.loads(row['payload'])} if row else None


def remaining(day, now):
    if day is None:return None
    curve=day['cumulative']
    if now<=curve[0]['ts']:return day['total_kwh']
    if now>=curve[-1]['ts']:return 0.0
    for a,b in zip(curve,curve[1:]):
        if a['ts']<=now<b['ts']:
            used=a['wh']+(b['wh']-a['wh'])*(now-a['ts'])/(b['ts']-a['ts'])
            return max(0,day['total_kwh']-used/1000)


def forecast_status(path, selected_day, now=None):
    now=time.time() if now is None else now
    today=datetime.fromtimestamp(now,ZONE).date()
    with connect(path) as db:
        selected=latest_day(db,selected_day)
        current=latest_day(db,today.isoformat())
        tomorrow=latest_day(db,(today+timedelta(days=1)).isoformat())
        attempt=db.execute('SELECT error FROM forecast_runs ORDER BY ts DESC LIMIT 1').fetchone()
        start=datetime.combine(date.fromisoformat(selected_day),datetime.min.time(),ZONE).timestamp()
        end=datetime.combine(date.fromisoformat(selected_day)+timedelta(days=1),datetime.min.time(),ZONE).timestamp()
        rows=db.execute('SELECT ts,pv_w,error FROM solaredge_samples WHERE ts>=? AND ts<? ORDER BY ts',(start,end)).fetchall()
        energy=db.execute('SELECT kwh,fetched_at FROM solaredge_energy WHERE day=?',(selected_day,)).fetchone()
        today_energy=db.execute('SELECT kwh,fetched_at FROM solaredge_energy WHERE day=?',(today.isoformat(),)).fetchone()
    from preferences import read_preferences
    prefs=read_preferences(path)
    midnight=datetime.combine(date.fromisoformat(selected_day),datetime.min.time(),ZONE)
    view_start=(midnight+timedelta(hours=prefs['forecast_start_hour'])).timestamp()
    view_end=(midnight+timedelta(hours=prefs['forecast_end_hour'])).timestamp()
    from battery_history import day_data
    battery=day_data(path,start,min(end,now)) if start<now else {'segments':[]}
    actual=[]; segment=[];last=None
    for r in rows:
        if r['error'] or (last is not None and r['ts']-last>1800):
            if segment:actual.append(segment)
            segment=[]
        if not r['error']:segment.append({'ts':r['ts'],'w':r['pv_w']})
        last=r['ts']
    if segment:actual.append(segment)
    site=plant()
    return {'day':selected_day,'start':start,'end':end,'view_start':view_start,'view_end':view_end,'view_end_hour':prefs['forecast_end_hour'],'forecast':selected,'actual':actual,'battery':battery,
            'site':{key:site[key] for key in ('name','kwp','tilt','azimuth')},
            'today_kwh':current['total_kwh'] if current else None,
            'cards_stale':current is None or tomorrow is None or now-current['issued_at']>14400 or now-tomorrow['issued_at']>14400,
            'remaining_kwh':remaining(current,now),'tomorrow_kwh':tomorrow['total_kwh'] if tomorrow else None,
            'energy':dict(energy) if energy else None,
            'today_energy':dict(today_energy) if today_energy else None,
            'stale':selected is None or now-selected['issued_at']>14400,
            'message':attempt['error'] if attempt else None}


def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    path=load_settings()['database_path'];initialize_forecast(path)
    logging.info('%s',collect_forecast(path,plant()))

if __name__=='__main__':main()
