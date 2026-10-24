"""Open-Meteo model temperatures for the configured site and Sevilla, Spain."""
import json
import math
import time
import logging
from urllib.request import urlopen
from urllib.parse import urlencode
from database import connect, initialize
from settings import load_settings
from forecast import plant

SEVILLA_LATITUDE, SEVILLA_LONGITUDE = 37.38620512, -5.99251368
SOURCE = 'Open-Meteo · Best Match'


def weather_url(latitude, longitude):
    return 'https://api.open-meteo.com/v1/forecast?' + urlencode(dict(
        latitude=latitude, longitude=longitude, current='temperature_2m',
        timeformat='unixtime', timezone='UTC', forecast_days=1))


SEVILLA_URL = weather_url(SEVILLA_LATITUDE, SEVILLA_LONGITUDE)


def initialize_weather(path):
    initialize(path)
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS weather_samples (
            fetched_at REAL PRIMARY KEY, valid_at REAL NOT NULL, temperature_c REAL NOT NULL,
            latitude REAL NOT NULL, longitude REAL NOT NULL, source TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS weather_valid_time ON weather_samples(valid_at,fetched_at)')
        db.execute('CREATE TABLE IF NOT EXISTS weather_attempts (slot INTEGER PRIMARY KEY, ts REAL NOT NULL, error TEXT)')
        db.execute('''CREATE TABLE IF NOT EXISTS weather_sevilla_samples (
            fetched_at REAL PRIMARY KEY, valid_at REAL NOT NULL, temperature_c REAL NOT NULL,
            latitude REAL NOT NULL, longitude REAL NOT NULL, source TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS weather_sevilla_valid_time ON weather_sevilla_samples(valid_at,fetched_at)')
        db.execute('CREATE TABLE IF NOT EXISTS weather_sevilla_attempts (slot INTEGER PRIMARY KEY, ts REAL NOT NULL, error TEXT)')


def fetch_weather():
    site=plant()
    with urlopen(weather_url(site['latitude'],site['longitude']), timeout=10) as response:
        return json.load(response)


def fetch_sevilla_weather():
    with urlopen(SEVILLA_URL, timeout=10) as response:
        return json.load(response)


def normalize(data, now):
    if data['current_units']['temperature_2m'] != '°C' or data['current_units']['time'] != 'unixtime':
        raise ValueError('Unexpected units')
    value, stamp = data['current']['temperature_2m'], data['current']['time']
    for item in (value, stamp):
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError('Invalid weather value')
    if not -90 <= value <= 60 or not 0 <= now - stamp <= 3600:
        raise ValueError('Invalid temperature or weather time')
    return stamp, value


def collect(path, now=None, fetch=fetch_weather):
    now = time.time() if now is None else now
    slot = int(now // 900)
    with connect(path) as db:
        inserted = db.execute('INSERT OR IGNORE INTO weather_attempts VALUES (?,?,?)',
                              (slot, now, 'Abruf nicht abgeschlossen')).rowcount
    if not inserted:
        return 'Wetterabruf in dieser Viertelstunde bereits versucht.'
    try:
        stamp, value = normalize(fetch(), now)
    except (OSError, ValueError, KeyError, TypeError):
        with connect(path) as db:
            db.execute('UPDATE weather_attempts SET error=? WHERE slot=?',
                       ('Wetterabruf fehlgeschlagen', slot))
        return 'Wetterabruf fehlgeschlagen; nächster Versuch in der nächsten Viertelstunde.'
    with connect(path) as db:
        site=plant()
        db.execute('INSERT INTO weather_samples VALUES (?,?,?,?,?,?)',
                   (now, stamp, value, site['latitude'], site['longitude'], SOURCE))
        db.execute('UPDATE weather_attempts SET error=NULL WHERE slot=?', (slot,))
    return 'Wetterwert gespeichert.'


def collect_sevilla(path, now=None, fetch=fetch_sevilla_weather):
    now = time.time() if now is None else now
    slot = int(now // 900)
    with connect(path) as db:
        inserted = db.execute('INSERT OR IGNORE INTO weather_sevilla_attempts VALUES (?,?,?)',
                              (slot, now, 'Abruf nicht abgeschlossen')).rowcount
    if not inserted:
        return 'Sevilla-Abruf in dieser Viertelstunde bereits versucht.'
    try:
        stamp, value = normalize(fetch(), now)
    except (OSError, ValueError, KeyError, TypeError):
        with connect(path) as db:
            db.execute('UPDATE weather_sevilla_attempts SET error=? WHERE slot=?',
                       ('Sevilla-Abruf fehlgeschlagen', slot))
        return 'Sevilla-Abruf fehlgeschlagen; nächster Versuch in der nächsten Viertelstunde.'
    with connect(path) as db:
        db.execute('INSERT INTO weather_sevilla_samples VALUES (?,?,?,?,?,?)',
                   (now, stamp, value, SEVILLA_LATITUDE, SEVILLA_LONGITUDE, SOURCE))
        db.execute('UPDATE weather_sevilla_attempts SET error=NULL WHERE slot=?', (slot,))
    return 'Sevilla-Wetterwert gespeichert.'


def _status(db, sample_table, attempt_table, now):
    row = db.execute(f'SELECT * FROM {sample_table} ORDER BY fetched_at DESC LIMIT 1').fetchone()
    attempt = db.execute(f'SELECT ts,error FROM {attempt_table} ORDER BY slot DESC LIMIT 1').fetchone()
    sample = dict(row) if row else None
    stale = sample is None or any(not 0 <= now-sample[key] <= 3600 for key in ('valid_at','fetched_at'))
    return dict(sample=sample, stale=stale, error=attempt['error'] if attempt else None)


def weather_status(path, now=None):
    now = time.time() if now is None else now
    with connect(path) as db:
        primary = _status(db, 'weather_samples', 'weather_attempts', now)
        primary['sevilla'] = _status(db, 'weather_sevilla_samples', 'weather_sevilla_attempts', now)
    primary['site_name'] = plant()['name']
    return primary


def weather_history(path, start, end, now=None):
    now=time.time() if now is None else now
    with connect(path) as db:
        rows=db.execute('SELECT valid_at,fetched_at,temperature_c FROM weather_samples WHERE valid_at>=? AND valid_at<? AND valid_at<=? ORDER BY valid_at,fetched_at',(start,end,now)).fetchall()
    # Repeated fetches of one model timestamp count once, latest stored version wins.
    points={row['valid_at']:dict(ts=row['valid_at'],temperature_c=row['temperature_c']) for row in rows}
    segments=[];segment=[];last=None
    for ts,point in points.items():
        if last is not None and ts-last>1200:
            segments.append(segment);segment=[]
        segment.append(point);last=ts
    if segment:segments.append(segment)
    values=[p['temperature_c'] for p in points.values()]
    return dict(start=start,end=end,segments=segments,count=len(values),
                minimum=min(values) if values else None,maximum=max(values) if values else None)


def sevilla_weather_history(path, start, end, now=None):
    now=time.time() if now is None else now
    with connect(path) as db:
        rows=db.execute('SELECT valid_at,fetched_at,temperature_c FROM weather_sevilla_samples WHERE valid_at>=? AND valid_at<? AND valid_at<=? ORDER BY valid_at,fetched_at',(start,end,now)).fetchall()
    points={row['valid_at']:dict(ts=row['valid_at'],temperature_c=row['temperature_c']) for row in rows}
    segments=[];segment=[];last=None
    for ts,point in points.items():
        if last is not None and ts-last>1200:
            segments.append(segment);segment=[]
        segment.append(point);last=ts
    if segment:segments.append(segment)
    values=[p['temperature_c'] for p in points.values()]
    return dict(segments=segments,count=len(values),minimum=min(values) if values else None,
                maximum=max(values) if values else None)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    path = load_settings()['database_path']
    initialize_weather(path)
    logging.info('%s', collect(path))
    logging.info('%s', collect_sevilla(path))
