"""Read-only snapshot of control and schedule registers of a Venus E V2."""
import argparse
import json
import socket
import struct
import time
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from marstek import read_registers

CONFIG = Path(__file__).with_name('marstek.toml')
ZONE = ZoneInfo('Europe/Berlin')
CONTROL_REGISTERS = (
    (42000, 'rs485_control'), (42010, 'force_mode'),
    (42011, 'charge_to_soc_pct'), (42020, 'charge_power_w'),
    (42021, 'discharge_power_w'), (43000, 'user_work_mode'),
    (44000, 'charge_cutoff_raw'), (44002, 'max_charge_power_w'),
    (44003, 'max_discharge_power_w'),
)


def signed16(value):
    return value - 65536 if value >= 32768 else value


def explain(address, value):
    mappings = {
        42000: {21930: 'RS485-Steuerung aktiv', 21947: 'RS485-Steuerung freigegeben'},
        42010: {0: 'Bereitschaft', 1: 'erzwungenes Laden', 2: 'erzwungenes Entladen'},
        43000: {0: 'manuell', 1: 'Eigenverbrauch', 2: 'Handels-/AI-Modus'},
    }
    if address in mappings:
        return mappings[address].get(value, 'unbekannter Wert')
    if address == 42011:
        return f'{value} % Ziel-SOC'
    if address in (42020, 42021, 44002, 44003):
        return f'{value} W'
    if address == 44000:
        return f'Rohwert {value}; Skalierung wird nicht vorausgesetzt'
    return None


def read_snapshot(config, pause_seconds=0.05):
    result = {'measured_at': datetime.now(ZONE).isoformat(timespec='seconds'), 'registers': {}, 'schedules': []}
    transaction = 1
    with socket.create_connection((config['host'], config['port']), timeout=3) as sock:
        sock.settimeout(3)

        def read(address, count=1):
            nonlocal transaction
            raw = read_registers(sock, transaction, config['unit'], address, count)
            transaction = transaction % 65535 + 1
            time.sleep(pause_seconds)
            return struct.unpack('>' + 'H' * count, raw)

        soc = read(32104)[0]
        ac_words = read(32202, 2)
        result['measurements'] = {
            'soc_pct': soc,
            'ac_power_w': struct.unpack('>i', struct.pack('>HH', *ac_words))[0],
        }
        for address, name in CONTROL_REGISTERS:
            value = read(address)[0]
            result['registers'][str(address)] = {
                'name': name, 'raw': value, 'meaning': explain(address, value),
            }
        for slot in range(1, 7):
            start = 43100 + (slot - 1) * 5
            days, start_raw, end_raw, power_raw, enabled = read(start, 5)
            result['schedules'].append({
                'slot': slot, 'start_register': start, 'days_raw': days,
                'start_time_raw': start_raw, 'end_time_raw': end_raw,
                'power_raw': power_raw, 'power_signed_w': signed16(power_raw),
                'enabled_raw': enabled,
            })
    return result


def format_text(snapshot, label):
    lines = [f'Marstek-Diagnose: {label}', f'Zeit: {snapshot["measured_at"]}',
             f'SOC: {snapshot["measurements"]["soc_pct"]} %',
             f'AC-Leistung: {snapshot["measurements"]["ac_power_w"]:+d} W', '', 'Steuerregister:']
    for address, item in snapshot['registers'].items():
        lines.append(f'  {address}  {item["name"]}: {item["raw"]}  ({item["meaning"]})')
    lines.extend(['', 'Zeitpläne (Rohwerte):'])
    for slot in snapshot['schedules']:
        lines.append('  Slot {slot}: Tage={days_raw}, Start={start_time_raw}, Ende={end_time_raw}, '
                     'Leistung={power_signed_w:+d} W (raw {power_raw}), Aktiv={enabled_raw}'.format(**slot))
    lines.append('\nNur gelesen: Modbus-Funktion 03; keine Register wurden geschrieben.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='Momentaufnahme', help='Bezeichnung für den Vergleich')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).with_name('data') / 'diagnostics')
    parser.add_argument('--no-file', action='store_true', help='keine JSON-Datei speichern')
    args = parser.parse_args()
    config = tomllib.loads(CONFIG.read_text())
    snapshot = read_snapshot(config)
    snapshot['label'] = args.label
    print(format_text(snapshot, args.label))
    if not args.no_file:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(ZONE).strftime('%Y%m%d-%H%M%S')
        safe_label = ''.join(c if c.isalnum() or c in '-_' else '-' for c in args.label).strip('-') or 'snapshot'
        path = args.output_dir / f'{stamp}-{safe_label}.json'
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
        print(f'\nGespeichert: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
