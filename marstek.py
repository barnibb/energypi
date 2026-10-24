"""Venus E V1/V2 collection and optional EV discharge limit."""
import argparse
import fcntl
import logging
import socket
import struct
import time
import tomllib
from pathlib import Path
from database import initialize, connect
from settings import load_settings
from marstek_control import initialize_control, control_status, step, Device
from preferences import initialize_preferences
from charging import initialize_charging
from marstek_actions import initialize_actions, action_status, process
from marstek_display import operating_status
from grid_charging import initialize_grid_charging, process as process_grid_charge

CONFIG = Path(__file__).with_name('marstek.toml')
FIELDS = ('soc', 'ac_power_w', 'battery_power_w', 'battery_voltage_v', 'ac_voltage_v')


def initialize_marstek(path):
    initialize(path)
    initialize_control(path)
    initialize_actions(path)
    initialize_grid_charging(path)
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS marstek_samples (
            ts REAL PRIMARY KEY, soc REAL, ac_power_w REAL, battery_power_w REAL,
            battery_voltage_v REAL, ac_voltage_v REAL, error TEXT)''')
        db.execute('CREATE INDEX IF NOT EXISTS marstek_valid_time ON marstek_samples(ts) WHERE error IS NULL')


def receive(sock, length):
    data = b''
    while len(data) < length:
        chunk = sock.recv(length-len(data))
        if not chunk:
            raise ConnectionError('Elfin hat die Verbindung geschlossen')
        data += chunk
    return data


def read_registers(sock, transaction, unit, address, count):
    # Deliberately no generic function code or write API.
    sock.sendall(struct.pack('>HHHBBHH', transaction, 0, 6, unit, 3, address, count))
    tid, protocol, length, response_unit = struct.unpack('>HHHB', receive(sock, 7))
    if (tid, protocol, response_unit) != (transaction, 0, unit) or not 2 <= length <= 254:
        raise ValueError('Ungültiger Modbus-Antwortkopf')
    body = receive(sock, length-1)
    if body[0] == 0x83:
        raise ValueError('Marstek meldet Modbus-Fehler')
    if len(body) != 2+2*count or body[:2] != bytes((3, 2*count)):
        raise ValueError('Ungültige Modbus-Nutzdaten')
    return body[2:]


def fetch(config):
    with socket.create_connection((config['host'], config['port']), timeout=3) as sock:
        sock.settimeout(3)
        battery = read_registers(sock, 1, config['unit'], 32100, 5)
        ac = read_registers(sock, 2, config['unit'], 32200, 5)
    volts, current, power, soc = struct.unpack('>HhiH', battery)
    ac_volts, ac_current, ac_power, frequency = struct.unpack('>HhiH', ac)
    if not (0 <= soc <= 100 and 0 < volts <= 10000 and ac_volts <= 3000
            and abs(power) <= 10000 and abs(ac_power) <= 10000):
        raise ValueError('Unplausible Marstek-Messwerte')
    return dict(soc=soc, ac_power_w=ac_power, battery_power_w=power,
                battery_voltage_v=volts/100, ac_voltage_v=ac_volts/10)


def collect(path, config, fetcher=fetch, now=None):
    values, error = {}, None
    try:
        values = fetcher(config)
    except (OSError, ValueError) as exc:
        error = f'{type(exc).__name__}: {exc}'
    stamp = time.time() if now is None else now
    with connect(path) as db:
        db.execute('INSERT INTO marstek_samples VALUES (?,?,?,?,?,?,?)',
                   (stamp, *(values.get(key) for key in FIELDS), error))
    return error


def status(path, now=None):
    now = time.time() if now is None else now
    with connect(path) as db:
        sample = db.execute('SELECT * FROM marstek_samples WHERE error IS NULL ORDER BY ts DESC LIMIT 1').fetchone()
        attempt = db.execute('SELECT ts,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone()
    sample, attempt = dict(sample) if sample else None, dict(attempt) if attempt else None
    stale = sample is None or not 0 <= now-sample['ts'] <= 90 or bool(attempt and attempt['error'])
    control=control_status(path)
    return dict(sample=sample, attempt=attempt, stale=stale, control=control, action=action_status(path),
                operating=operating_status(control,sample,stale,now))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    config = tomllib.loads(CONFIG.read_text())
    if not isinstance(config.get('host'), str) or not config['host'] or not 1 <= config['port'] <= 65535 or not 1 <= config['unit'] <= 247:
        raise ValueError('Ungültige Marstek-Konfiguration')
    path = load_settings()['database_path']
    initialize_marstek(path)
    initialize_preferences(path)
    initialize_charging(path)
    with open(str(path)+'.marstek.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.error('Marstek-Sammler läuft bereits')
            return 1
        logging.info('Marstek gestartet; Messintervall 30 Sekunden, Autolade-Entladegrenze aktiv')
        while True:
            started = time.monotonic()
            error = collect(path, config)
            if error:
                logging.warning('Marstek-Messlücke: %s', error)
            if args.once:
                return int(bool(error))
            if not error:
                device=Device(config)
                if not process_grid_charge(path,device) and not process(path, device):
                    step(path, device)
            time.sleep(max(0, 30-(time.monotonic()-started)))


if __name__ == '__main__':
    raise SystemExit(main())
