"""Liest ausschließlich Shelly-Messwerte; keine Steuerbefehle."""
import argparse
import fcntl
import json
import logging
import math
import time
from urllib.request import build_opener, ProxyHandler
from database import FIELDS, initialize, save
from settings import load_settings
from charging import ChargingRecorder,latest_battery_discharge
from preferences import initialize_preferences, read_preferences

def validate(data):
    if not isinstance(data, dict) or data.get('errors') or data.get('code') or data.get('id') != 0:
        raise ValueError('Shelly meldet einen Fehler oder eine ungültige Antwort')
    result = {}
    for field in FIELDS:
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{field} fehlt oder ist ungültig')
        result[field] = float(value)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    config = load_settings(args.config)
    path, shelly = config['database_path'], config['shelly']
    initialize(path)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    # Prozessende gibt die Sperre automatisch frei; verhindert doppelte Sammler.
    with open(str(path) + '.collector.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.error('Für diese Datenbank läuft bereits ein Sammler.')
            return 1
        initialize_preferences(path)
        stored = read_preferences(path)
        rule_keys=('block_above_w','release_below_w','hold_seconds','max_gap_seconds','sustained_discharge_w','sustained_discharge_seconds')
        rule = {k:stored[k] for k in rule_keys}
        recorder = ChargingRecorder(path,rule)
        opener = build_opener(ProxyHandler({}))
        logging.info('Shelly-Erfassung gestartet: %s; Datenbank: %s', shelly['host'], path)
        try:
            while True:
                started = time.monotonic()
                stored = read_preferences(path)
                updated = {k:stored[k] for k in rule}
                if updated != rule:
                    rule = updated
                    recorder = ChargingRecorder(path,rule)
                    logging.info('Erkennungsparameter übernommen; Prüfzeit zurückgesetzt')
                try:
                    with opener.open(f"http://{shelly['host']}/rpc/EM.GetStatus?id=0", timeout=shelly['timeout_seconds']) as response:
                        values = validate(json.load(response))
                except (OSError, ValueError) as error:
                    ts=time.time()
                    save(path, ts, error=str(error))
                    recorder.update(None,ts,time.monotonic())
                    logging.warning('Messlücke: %s', error)
                    if args.once:
                        return 1
                else:
                    ts=time.time()
                    save(path, ts, values)
                    battery_discharge=latest_battery_discharge(path,ts)
                    event=recorder.update(values['total_act_power'],ts,time.monotonic(),battery_discharge)
                    if event:
                        logging.info('Autoladen-Schätzung: %s',event)
                    if args.once:
                        logging.info('Gespeichert: Netz=%+.1f W', values['total_act_power'])
                        return 0
                time.sleep(max(0, shelly['poll_seconds'] - (time.monotonic() - started)))
        except KeyboardInterrupt:
            logging.info('Sammler beendet')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
