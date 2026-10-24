"""SolarEdge-Istwerte. Zugangsdaten werden weder gespeichert noch protokolliert."""
from datetime import datetime
import json
import logging
import math
import os
from pathlib import Path
import time
import tomllib
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from zoneinfo import ZoneInfo
from database import connect, initialize
from settings import load_settings, ROOT

INTERVAL = 900
ZONE = ZoneInfo('Europe/Berlin')


def initialize_solar(path):
    initialize(path)
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS solaredge_samples (
            id INTEGER PRIMARY KEY, ts REAL NOT NULL, pv_w REAL, load_w REAL,
            grid_w REAL, error TEXT)''')
        db.execute('CREATE INDEX IF NOT EXISTS solaredge_time ON solaredge_samples(ts)')


def credentials():
    # Nur der Sammler liest diese Datei; nie über Webrouten oder in der Datenbank.
    path = Path(os.environ.get('MARSTEK_SECRETS', ROOT / 'secrets.toml'))
    with path.open('rb') as file:
        section = tomllib.load(file).get('solaredge', {})
    site = str(section.get('site_id', '')).strip()
    key = str(section.get('api_key', '')).strip()
    if not site.isascii() or not site.isdigit() or not key or key == 'HIER_EINTRAGEN':
        raise ValueError('SolarEdge-Zugangsdaten fehlen oder sind ungültig')
    return site, key


def in_window(ts):
    local = datetime.fromtimestamp(ts, ZONE)
    return 450 <= local.hour * 60 + local.minute < 1260


def parse_flow(data):
    if not isinstance(data, dict) or not isinstance(data.get('siteCurrentPowerFlow'), dict):
        raise ValueError('SolarEdge-Leistungsfluss fehlt')
    flow = data['siteCurrentPowerFlow']
    unit = flow.get('unit')
    factors = {'W': 1, 'kW': 1000}
    if unit not in factors:
        raise ValueError('Unbekannte Leistungseinheit')

    def value(name, required=False):
        element = flow.get(name)
        if element is None and not required:
            return None
        if not isinstance(element, dict) or element.get('status') not in ('Active', 'Idle'):
            if required:
                raise ValueError('PV-Daten nicht verfügbar')
            return None
        number = element.get('currentPower')
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number < 0:
            raise ValueError('Ungültiger Leistungswert')
        return number * factors[unit]

    pv, load, magnitude = value('PV', True), value('LOAD'), value('GRID')
    connections = flow.get('connections', [])
    if not isinstance(connections, list):
        raise ValueError('Ungültige Flussrichtungen')
    directions = set()
    for connection in connections:
        if not isinstance(connection, dict):
            raise ValueError('Ungültige Flussrichtung')
        origin, destination = str(connection.get('from', '')).upper(), str(connection.get('to', '')).upper()
        if origin == 'GRID':
            directions.add(1)
        if destination == 'GRID':
            directions.add(-1)
    grid = 0.0 if magnitude == 0 else magnitude * next(iter(directions)) if magnitude is not None and len(directions) == 1 else None
    return {'pv_w': pv, 'load_w': load, 'grid_w': grid}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_flow(site, key):
    url = f'https://monitoringapi.solaredge.com/site/{site}/currentPowerFlow.json?' + urlencode({'api_key':key})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(url, timeout=15) as response:
            raw = response.read(100_001)
            if len(raw) > 100_000:
                raise ValueError('Antwort zu groß')
            return parse_flow(json.loads(raw))
    except HTTPError as error:
        # Niemals error/URL ausgeben: Der Schlüssel steht im Querystring.
        raise ValueError(f'SolarEdge HTTP {error.code}') from None
    except (URLError, OSError):
        raise ValueError('SolarEdge-Verbindung fehlgeschlagen') from None
    except (ValueError, TypeError, KeyError):
        raise ValueError('SolarEdge-Antwort fehlt oder ist ungültig') from None


def collect(path, site, key, now=None, fetch=fetch_flow):
    now = time.time() if now is None else now
    if not in_window(now):
        return 'Außerhalb der Abfragezeit (07:30–21:00)'
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        last = db.execute('SELECT MAX(ts) FROM solaredge_samples').fetchone()[0]
        if last is not None and (now < last or int(now // INTERVAL) == int(last // INTERVAL)):
            return 'Abfrageintervall noch nicht erreicht'
        # Vor dem Request reservieren, damit Neustarts/Parallelstarts das Limit respektieren.
        sample_id = db.execute('INSERT INTO solaredge_samples(ts,error) VALUES (?,?)', (now,'Abfrage nicht abgeschlossen')).lastrowid
    try:
        values = fetch(site, key)
    except ValueError as error:
        # fetch_flow liefert ausschließlich fest definierte, bereinigte Meldungen.
        message = str(error)
        with connect(path) as db:
            db.execute('UPDATE solaredge_samples SET error=? WHERE id=?', (message,sample_id))
        return message
    with connect(path) as db:
        db.execute('UPDATE solaredge_samples SET pv_w=?,load_w=?,grid_w=?,error=NULL WHERE id=?',
                   (values['pv_w'],values['load_w'],values['grid_w'],sample_id))
    return 'SolarEdge-Messwerte gespeichert'


def solar_status(path, now=None):
    now = time.time() if now is None else now
    with connect(path) as db:
        sample = db.execute('SELECT ts,pv_w,load_w,grid_w FROM solaredge_samples WHERE error IS NULL ORDER BY ts DESC LIMIT 1').fetchone()
        attempt = db.execute('SELECT ts,error FROM solaredge_samples ORDER BY ts DESC LIMIT 1').fetchone()
    stale = sample is None or now - sample['ts'] > 1800 or now < sample['ts'] or bool(attempt and attempt['error'])
    return {'sample':dict(sample) if sample else None, 'stale':stale,
            'message':attempt['error'] if attempt and attempt['error'] else None,
            'scheduled_pause':not in_window(now)}


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    try:
        site, key = credentials()
    except (OSError, ValueError):
        logging.info('SolarEdge noch nicht eingerichtet: secrets.toml mit site_id und api_key ausfüllen.')
        return 0
    path = load_settings()['database_path']
    initialize_solar(path)
    logging.info('%s', collect(path,site,key))
    from energy import initialize_energy, collect_energy
    initialize_energy(path)
    logging.info('%s',collect_energy(path,site,key))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
