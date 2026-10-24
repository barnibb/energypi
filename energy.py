"""SolarEdge-Tagesenergie aus /energy, nicht aus Momentanleistung integriert."""
from datetime import datetime, timedelta, date
import json
import math
import time
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler
from urllib.error import HTTPError
from database import connect
from solaredge import ZONE, NoRedirect


def initialize_energy(path):
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS solaredge_energy (day TEXT PRIMARY KEY,kwh REAL NOT NULL,fetched_at REAL NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS energy_attempts (ts REAL PRIMARY KEY,error TEXT)')


def parse_energy(data):
    energy=data['energy']
    factor={'Wh':0.001,'kWh':1}.get(energy['unit'])
    if factor is None or energy.get('timeUnit')!='DAY':raise ValueError('Ungültige Energieeinheit')
    values={}
    for item in energy['values']:
        day=datetime.fromisoformat(item['date']).date().isoformat()
        value=item['value']
        if value is None:continue
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError('Ungültige Energie')
        values[day]=value*factor
    return values


def fetch_energy(site,key,today):
    start=today-timedelta(days=7)
    params={'timeUnit':'DAY','startDate':start.isoformat(),'endDate':today.isoformat(),'api_key':key}
    url=f'https://monitoringapi.solaredge.com/site/{site}/energy.json?'+urlencode(params)
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(url,timeout=15) as response:
            raw=response.read(100_001)
            if len(raw)>100_000:raise ValueError('Antwort zu groß')
            values=parse_energy(json.loads(raw))
            if any(not start<=date.fromisoformat(day)<=today for day in values):raise ValueError('Datum außerhalb des Abrufs')
            return values
    except HTTPError as error:
        raise ValueError(f'SolarEdge-Energie HTTP {error.code}') from None
    except (OSError,ValueError,KeyError,TypeError):
        raise ValueError('SolarEdge-Energieabruf fehlgeschlagen') from None


def collect_energy(path,site,key,now=None,fetcher=fetch_energy):
    now=time.time() if now is None else now
    today=datetime.fromtimestamp(now,ZONE).date()
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        last=db.execute('SELECT MAX(ts) FROM energy_attempts').fetchone()[0]
        if last is not None and (now<last or int(now//3600)==int(last//3600)):return 'Energieintervall noch nicht erreicht'
        db.execute('INSERT INTO energy_attempts VALUES (?,?)',(now,'Energieabruf nicht abgeschlossen'))
    try:values=fetcher(site,key,today)
    except ValueError as error:
        with connect(path) as db:db.execute('UPDATE energy_attempts SET error=? WHERE ts=?',(str(error),now))
        return str(error)
    with connect(path) as db:
        for day,kwh in values.items():
            db.execute('INSERT INTO solaredge_energy VALUES (?,?,?) ON CONFLICT(day) DO UPDATE SET kwh=excluded.kwh,fetched_at=excluded.fetched_at',(day,kwh,now))
        db.execute('UPDATE energy_attempts SET error=NULL WHERE ts=?',(now,))
    return 'SolarEdge-Tageserträge gespeichert'
