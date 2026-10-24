"""SQLite-Speicher. Zeitstempel sind UTC Unix-Sekunden, Leistungen sind Watt."""
from contextlib import contextmanager
import sqlite3
import json
from pathlib import Path

FIELDS = ('total_act_power',) + tuple(f'{p}_{field}' for p in 'abc' for field in ('act_power', 'voltage', 'current'))

@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()

def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        columns = ', '.join(f'{field} REAL' for field in FIELDS)
        db.execute(f'CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY, ts REAL NOT NULL, {columns}, error TEXT)')
        db.execute('CREATE INDEX IF NOT EXISTS measurements_time ON measurements(ts)')
        db.execute('CREATE TABLE IF NOT EXISTS minute_archive (minute INTEGER PRIMARY KEY, payload TEXT NOT NULL)')

def save(path, ts, values=None, error=None):
    values = values or {}
    with connect(path) as db:
        db.execute(f"INSERT INTO measurements (ts,{','.join(FIELDS)},error) VALUES ({','.join('?' for _ in range(len(FIELDS)+2))})",
                   [ts, *(values.get(field) for field in FIELDS), error])

def latest(path):
    with connect(path) as db:
        sample = db.execute('SELECT * FROM measurements WHERE error IS NULL ORDER BY ts DESC LIMIT 1').fetchone()
        attempt = db.execute('SELECT ts,error FROM measurements ORDER BY ts DESC LIMIT 1').fetchone()
    return dict(sample) if sample else None, dict(attempt) if attempt else None

def recent_average(path, end, window_seconds=900, gap_seconds=15, minimum_coverage=0.8):
    """Zeitgewichteter Netzwert; Messluecken werden nicht als 0 W gewertet."""
    start = end - window_seconds
    with connect(path) as db:
        rows = db.execute(
            'SELECT ts,total_act_power,error FROM measurements '
            'WHERE ts>=? AND ts<=? ORDER BY ts',
            (start - gap_seconds, end),
        ).fetchall()
    area = coverage = 0.0
    previous = None
    for row in rows:
        if row['error'] or row['total_act_power'] is None:
            previous = None
            continue
        current = (float(row['ts']), float(row['total_act_power']))
        if previous:
            duration = current[0] - previous[0]
            if 0 < duration <= gap_seconds:
                left, right = max(start, previous[0]), min(end, current[0])
                if right > left:
                    left_ratio = (left - previous[0]) / duration
                    right_ratio = (right - previous[0]) / duration
                    left_value = previous[1] + (current[1] - previous[1]) * left_ratio
                    right_value = previous[1] + (current[1] - previous[1]) * right_ratio
                    span = right - left
                    area += (left_value + right_value) / 2 * span
                    coverage += span
        previous = current
    if previous and start <= previous[0] <= end and end - previous[0] <= gap_seconds:
        span = end - max(start, previous[0])
        area += previous[1] * span
        coverage += span
    ratio = min(1.0, coverage / window_seconds) if window_seconds > 0 else 0.0
    return {'watts': area / coverage if coverage else None, 'coverage': ratio,
            'seconds': coverage, 'complete': ratio >= minimum_coverage}

def summarize(rows, bucket_seconds=60, gap_seconds=15):
    """Zeitlich geordnete Punkte; Fehler bleiben explizite Trennmarken."""
    result, group = [], []

    def flush():
        if not group:
            return
        point = {'ts': sum(r['ts'] for r in group) / len(group),
                 'first': group[0]['ts'], 'last': group[-1]['ts'], 'count': len(group)}
        for field in FIELDS:
            values = [r[field] for r in group]
            point[field] = sum(values) / len(values)
            point[field + '_min'] = min(values)
            point[field + '_max'] = max(values)
        result.append(point)
        group.clear()

    for row in rows:
        if row['error']:
            flush()
            # Aufeinanderfolgende Fehler benötigen nur eine Trennmarke.
            if not result or not result[-1].get('error'):
                result.append({'ts': row['ts'], 'first': row['ts'], 'last': row['ts'], 'error': True})
            continue
        if group and (not bucket_seconds or int(row['ts'] // bucket_seconds) != int(group[0]['ts'] // bucket_seconds)
                      or row['ts'] - group[-1]['ts'] > gap_seconds):
            flush()
        group.append(row)
    flush()
    return result


def history(path, start, end, bucket_seconds=60, gap_seconds=15):
    with connect(path) as db:
        # Ein Lese-Snapshot verhindert Doppelungen während der Verdichtung.
        db.execute('BEGIN')
        archived = db.execute('SELECT payload FROM minute_archive WHERE minute>=? AND minute<? ORDER BY minute',
                              (int(start // 60) * 60, end)).fetchall()
        rows = db.execute('SELECT * FROM measurements WHERE ts>=? AND ts<? ORDER BY ts', (start, end)).fetchall()
    points = [p for row in archived for p in json.loads(row['payload']) if start <= p['ts'] < end]
    points.extend(summarize(rows, bucket_seconds, gap_seconds))
    points.sort(key=lambda p: p['first'])
    result, segment, previous = [], [], None
    for point in points:
        if point.get('error') or (previous is not None and point['first'] - previous > gap_seconds):
            if segment:
                result.append(segment)
            segment = []
        if not point.get('error'):
            segment.append(point)
        previous = point['last']
    if segment:
        result.append(segment)
    return result
