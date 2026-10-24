"""Veröffentlichte Tibber-Preise; kein Schätzwert für unveröffentlichte Tage."""
import argparse
from datetime import datetime, timedelta
import json
import logging
import math
import os
from pathlib import Path
import time
import tomllib
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from database import connect, initialize
from settings import ROOT, load_settings
from solaredge import ZONE, NoRedirect
from opportunities import annotate

TIBBER_CONFIG = {'apiEndpoint':'https://api.tibber.com/v1-beta/gql'}
QUERY = '''{ viewer { homes { id currentSubscription {
 priceInfo(resolution: QUARTER_HOURLY) {
 today { total energy tax startsAt currency }
 tomorrow { total energy tax startsAt currency }
 } } } } }'''


def initialize_tibber(path):
    initialize(path)
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS tibber_prices (
            home_id TEXT NOT NULL, starts_at REAL NOT NULL, ends_at REAL NOT NULL,
            total REAL NOT NULL, energy REAL NOT NULL, tax REAL NOT NULL,
            currency TEXT NOT NULL, fetched_at REAL NOT NULL,
            PRIMARY KEY(home_id,starts_at))''')
        db.execute('CREATE TABLE IF NOT EXISTS tibber_attempts (ts REAL PRIMARY KEY,error TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS tibber_meta (id INTEGER PRIMARY KEY CHECK(id=1),home_id TEXT NOT NULL)')


def credentials():
    with Path(os.environ.get('MARSTEK_SECRETS',ROOT/'secrets.toml')).open('rb') as file:
        values=tomllib.load(file).get('tibber',{})
    token=str(values.get('token','')).strip()
    home_id=str(values.get('home_id','')).strip()
    if not token or token=='HIER_EINTRAGEN':raise ValueError('Tibber-Token fehlt')
    return token,home_id


def request_api(token, query=QUERY):
    req=Request(TIBBER_CONFIG['apiEndpoint'],data=json.dumps({'query':query}).encode(),
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','User-Agent':'Marstek-Control/1.0'})
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=20) as response:
            raw=response.read(1_000_001)
            if len(raw)>1_000_000:raise ValueError('Antwort zu groß')
            result=json.loads(raw)
        if not isinstance(result,dict) or result.get('errors'):
            raise ValueError('GraphQL-Fehler')
        return result
    except HTTPError as error:
        raise ValueError(f'Tibber HTTP {error.code}') from None
    except (OSError,ValueError,TypeError):
        # Weder Token, Antwort noch Authorization-Header protokollieren.
        raise ValueError('Tibber-Abfrage fehlgeschlagen; Token, Vertrag oder API prüfen') from None


def parse_prices(data,home_id,now):
    if not isinstance(data,dict) or data.get('errors'):raise ValueError('Tibber meldet einen API-Fehler')
    content=data.get('data')
    if not isinstance(content,dict) or not isinstance(content.get('viewer'),dict):raise ValueError('Tibber-Antwort enthält keine Preisdaten')
    homes=content['viewer'].get('homes')
    if not isinstance(homes,list) or not homes or any(not isinstance(h,dict) for h in homes):raise ValueError('Keine Tibber-Homes gefunden')
    if home_id:
        selected=[h for h in homes if h.get('id')==home_id]
    else:
        if len(homes)!=1:raise ValueError('Mehrere Tibber-Homes: home_id in secrets.toml angeben')
        selected=homes
    if len(selected)!=1:raise ValueError('Tibber-Home nicht gefunden')
    home=selected[0]
    subscription=home.get('currentSubscription')
    if not isinstance(subscription,dict) or not isinstance(subscription.get('priceInfo'),dict):
        raise ValueError('Kein aktiver Tibber-Preisvertrag verfügbar')
    info=subscription['priceInfo'];prices=[];seen=set()
    today=datetime.fromtimestamp(now,ZONE).date()
    for key,day in (('today',today),('tomorrow',today+timedelta(days=1))):
        if not isinstance(info.get(key),list):raise ValueError('Unvollständige Tibber-Antwort')
        for item in info[key]:
            dt=datetime.fromisoformat(item['startsAt'])
            if dt.tzinfo is None or dt.astimezone(ZONE).date()!=day:raise ValueError('Unerwarteter Preiszeitpunkt')
            ts=dt.timestamp()
            if ts in seen or ts%900:raise ValueError('Doppeltes oder ungültiges Preisintervall')
            seen.add(ts)
            values=[]
            for field in ('total','energy','tax'):
                v=item.get(field)
                if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v):raise ValueError('Ungültiger Preis')
                values.append(float(v))
            if item.get('currency')!='EUR':raise ValueError('Erwartet EUR für die Anlage in Deutschland')
            prices.append({'start':ts,'end':ts+900,'total':values[0],'energy':values[1],'tax':values[2]})
    if not info['today']:raise ValueError('Heutige Tibber-Preise fehlen')
    return str(home['id']),sorted(prices,key=lambda p:p['start'])


def bounds(day):
    return (datetime.combine(day,datetime.min.time(),ZONE).timestamp(),
            datetime.combine(day+timedelta(days=1),datetime.min.time(),ZONE).timestamp())


def complete(db,home_id,day):
    start,end=bounds(day)
    rows=db.execute('SELECT starts_at FROM tibber_prices WHERE home_id=? AND starts_at>=? AND starts_at<? ORDER BY starts_at',(home_id,start,end)).fetchall()
    return [r[0] for r in rows]==list(range(int(start),int(end),900))


def collect_tibber(path,token,home_id='',now=None,fetcher=request_api):
    now=time.time() if now is None else now
    local=datetime.fromtimestamp(now,ZONE);today=local.date()
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        last=db.execute('SELECT MAX(ts) FROM tibber_attempts').fetchone()[0]
        if last is not None and (now<last or int(now//3600)==int(last//3600)):return 'Tibber-Abrufintervall noch nicht erreicht'
        meta=db.execute('SELECT home_id FROM tibber_meta WHERE id=1').fetchone()
        active=home_id or (meta[0] if meta else '')
        if complete(db,active,today):
            if complete(db,active,today+timedelta(days=1)):return 'Preise heute und morgen bereits gespeichert'
            if local.hour<13 or local.hour>20:return 'Warte auf Veröffentlichung der morgigen Preise'
        db.execute('INSERT INTO tibber_attempts VALUES (?,?)',(now,'Tibber-Abfrage nicht abgeschlossen'))
    try:
        actual_id,prices=parse_prices(fetcher(token),home_id,now)
    except (ValueError,KeyError,TypeError) as error:
        message=str(error) if isinstance(error,ValueError) else 'Ungültige Tibber-Antwort'
        with connect(path) as db:db.execute('UPDATE tibber_attempts SET error=? WHERE ts=?',(message,now))
        return message
    with connect(path) as db:
        for p in prices:
            db.execute('''INSERT INTO tibber_prices VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(home_id,starts_at)
                DO UPDATE SET total=excluded.total,energy=excluded.energy,tax=excluded.tax,
                ends_at=excluded.ends_at,fetched_at=excluded.fetched_at''',
                       (actual_id,p['start'],p['end'],p['total'],p['energy'],p['tax'],'EUR',now))
        db.execute('INSERT INTO tibber_meta VALUES (1,?) ON CONFLICT(id) DO UPDATE SET home_id=excluded.home_id',(actual_id,))
        db.execute('UPDATE tibber_attempts SET error=NULL WHERE ts=?',(now,))
    return f'{len(prices)} Tibber-Preisintervalle gespeichert'


def price_status(path,day,now=None):
    now=time.time() if now is None else now
    start,end=bounds(day)
    with connect(path) as db:
        meta=db.execute('SELECT home_id FROM tibber_meta WHERE id=1').fetchone()
        home_id=meta[0] if meta else ''
        rows=db.execute('SELECT starts_at,ends_at,total,fetched_at FROM tibber_prices WHERE home_id=? AND starts_at>=? AND starts_at<? ORDER BY starts_at',(home_id,start,end)).fetchall()
        current=db.execute('SELECT total FROM tibber_prices WHERE home_id=? AND starts_at<=? AND ends_at>?',(home_id,now,now)).fetchone()
        attempt=db.execute('SELECT ts,error FROM tibber_attempts ORDER BY ts DESC LIMIT 1').fetchone()
        is_complete=complete(db,home_id,day)
    points=[{'start':r['starts_at'],'end':r['ends_at'],'ct':r['total']*100} for r in rows]
    today=datetime.fromtimestamp(now,ZONE).date()
    return {'day':day.isoformat(),'start':start,'end':end,'points':points,
            'current_ct':current[0]*100 if current else None,
            'min_ct':min((p['ct'] for p in points),default=None),'max_ct':max((p['ct'] for p in points),default=None),
            'average_ct':sum(p['ct'] for p in points)/len(points) if points else None,
            'complete':is_complete,'fetched_at':max((r['fetched_at'] for r in rows),default=None),
            'error':attempt['error'] if attempt else None,
            'pending':not points and day>today,
            **annotate(path,day,points,now,current[0]*100 if current else None)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--list-homes',action='store_true');args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    try:token,home_id=credentials()
    except (OSError,ValueError):
        logging.info('Tibber noch nicht eingerichtet: [tibber] token in secrets.toml ergänzen.');return
    if args.list_homes:
        try:
            homes=request_api(token,'{ viewer { homes { id } } }')['data']['viewer']['homes']
            for h in homes:print(h['id'])
        except (ValueError,KeyError,TypeError):logging.error('Tibber-Home-Liste konnte nicht geladen werden')
        return
    path=load_settings()['database_path'];initialize_tibber(path)
    logging.info('%s',collect_tibber(path,token,home_id))

if __name__=='__main__':main()
