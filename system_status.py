"""Lokaler Systemstatus ohne Geräte- oder Cloud-Abfragen."""
import json
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import connect, latest
from backup_status import status as backup_status
from solaredge import solar_status
from tibber import complete
from marstek import status as marstek_status

ZONE = ZoneInfo('Europe/Berlin')

class SystemStatus:
    def __init__(self, path, version):
        self.path = Path(path)
        self.version = version
        self.storage = None
        self.checked = None

    def read(self, now=None):
        now = time.time() if now is None else now
        local = datetime.fromtimestamp(now, ZONE)
        sample, attempt = latest(self.path)
        fresh = lambda ts, limit: ts is not None and 0 <= now-ts <= limit
        sample_ts = sample['ts'] if sample else None
        attempt_ts = attempt['ts'] if attempt else None
        ok = fresh(sample_ts,20) and not (attempt and attempt['error'])
        items = []
        def add(name, level, label, success=None, error=None):
            items.append(dict(name=name,level=level,label=label,last_success=success,error=error))
        # Raw exception text may contain URLs or credentials; publish only safe summaries.
        add('Shelly','ok' if ok else 'error','Aktuell' if ok else 'Messwerte fehlen',sample_ts,
            'Letzte Messabfrage fehlgeschlagen' if attempt and attempt['error'] else None)
        active = fresh(attempt_ts,20)
        add('Datenerfassung','ok' if active else 'error','Aktiv · Schreibaktivität erkannt' if active else 'Keine aktuelle Schreibaktivität',attempt_ts)
        solar = solar_status(self.path,now)
        solar_ts = solar['sample']['ts'] if solar['sample'] else None
        pause = solar['scheduled_pause']
        add('SolarEdge','warn' if solar['message'] else 'neutral' if pause or solar_ts is None else 'warn' if solar['stale'] else 'ok',
            'Abruffehler' if solar['message'] else 'Abrufpause' if pause and solar_ts is not None else 'Noch keine Daten' if solar_ts is None else 'Veraltet' if solar['stale'] else 'Aktuell',solar_ts,
            'Letzter SolarEdge-Abruf fehlgeschlagen' if solar['message'] else None)
        with connect(self.path) as db:
            forecast = db.execute('SELECT ts FROM forecast_runs WHERE error IS NULL ORDER BY ts DESC LIMIT 1').fetchone()
            fa = db.execute('SELECT error FROM forecast_runs ORDER BY ts DESC LIMIT 1').fetchone()
            meta = db.execute('SELECT home_id FROM tibber_meta WHERE id=1').fetchone()
            home = meta[0] if meta else ''
            today = complete(db,home,local.date())
            tomorrow = complete(db,home,local.date()+timedelta(days=1))
            tibber_ts = db.execute('SELECT MAX(fetched_at) FROM tibber_prices WHERE home_id=?',(home,)).fetchone()[0]
            ta = db.execute('SELECT error FROM tibber_attempts ORDER BY ts DESC LIMIT 1').fetchone()
        ft = forecast['ts'] if forecast else None
        fpause = local.hour < 6 or local.hour >= 22
        ferr = bool(fa and fa['error'])
        add('PV-Prognose','warn' if ferr else 'neutral' if ft is None else 'ok' if fresh(ft,14400) else 'neutral' if fpause else 'warn',
            'Abruffehler' if ferr else 'Noch keine Daten' if ft is None else 'Aktuell' if fresh(ft,14400) else 'Abrufpause' if fpause else 'Veraltet',ft,
            'Letzter Prognoseabruf fehlgeschlagen' if ferr else None)
        terr = bool(ta and ta['error'])
        add('Tibber','warn' if terr else 'ok' if today and tomorrow else 'neutral' if tibber_ts is None else 'warn',
            'Heute vollständig · Morgen verfügbar' if today and tomorrow else 'Heute vollständig · Morgen fehlt noch' if today else 'Noch keine Daten' if tibber_ts is None else 'Heute unvollständig',tibber_ts,
            'Letzter Tibber-Abruf fehlgeschlagen' if terr else None)
        backup = backup_status(self.path,now)
        add('Mac-Sicherung',backup['level'],backup['label'],backup['display_time'],backup['error'])
        with connect(self.path) as db:
            has_maintenance=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='maintenance_status'").fetchone()
            maintenance=db.execute('SELECT ts,payload FROM maintenance_status WHERE id=1').fetchone() if has_maintenance else None
        if maintenance:
            try:
                cleanup=json.loads(maintenance['payload'])
                if cleanup.get('version') == 2:
                    outcome=cleanup.get('outcome')
                    if outcome == 'success':
                        duration=round(float(cleanup.get('duration_seconds',0)))
                        archived=int(cleanup.get('archived_minutes',0));remaining=int(cleanup.get('remaining_old_measurements',0))
                        deleted=int(cleanup.get('journal_deleted',0));pending=int(cleanup.get('journal_remaining',0))
                        label=f'Aktuell · {duration} s · {archived} Minuten archiviert · {deleted} alte Datensätze bereinigt'
                        if remaining or pending:label+=f' · Rückstand {remaining} Rohzeilen / {pending} alte Datensätze'
                        add('Datenpflege','ok' if fresh(cleanup.get('last_success'),36*3600) and not (remaining or pending) else 'warn',
                            label if fresh(cleanup.get('last_success'),36*3600) else 'Überfällig',cleanup.get('last_success'),
                            None if fresh(cleanup.get('last_success'),36*3600) else 'Letzte erfolgreiche Datenpflege liegt mehr als 36 Stunden zurück')
                    elif outcome == 'running':
                        add('Datenpflege','neutral',f'Läuft · {cleanup.get("phase","Wartung")}',cleanup.get('last_success'))
                    else:
                        add('Datenpflege','warn',f'Fehlgeschlagen · {cleanup.get("phase","Wartung")}',cleanup.get('last_success'),
                            cleanup.get('error','Wartung wurde nicht abgeschlossen'))
                    retention=cleanup.get('retention')
                    if isinstance(retention,dict) and retention.get('version')==1:
                        tables=retention.get('tables',{})
                        number=lambda name: f'{int(tables.get(name,{}).get("rows",0)):,}'.replace(',','.')
                        label=(f'Bestand erfasst · Shelly roh {number("measurements")} · '
                               f'Minuten {number("minute_archive")} · Marstek roh {number("marstek_samples")}')
                        changes=[int(item.get('rows_since_previous') or 0) for item in tables.values()]
                        if retention.get('seconds_since_previous') and any(changes):
                            label+=f' · Veränderung seit letztem Lauf {sum(changes):+d} Zeilen'
                        add('Datenaufbewahrung','neutral',label,retention.get('generated_at'),
                            'Analysephase · Originaldaten bleiben vollständig erhalten')
                else:
                    deleted=sum(int(value.get('deleted',0)) for value in cleanup.values())
                    pending=sum(int(value.get('remaining_old',0)) for value in cleanup.values())
                    maintenance_label=(f'Aktuell · {deleted} Journalzeilen bereinigt'
                                       if not pending else f'Fortsetzung geplant · noch {pending} alte Journalzeilen')
                    add('Datenpflege','ok' if fresh(maintenance['ts'],36*3600) and not pending else 'warn',
                        maintenance_label if fresh(maintenance['ts'],36*3600) else 'Überfällig',maintenance['ts'],
                        None if fresh(maintenance['ts'],36*3600) else 'Letzte erfolgreiche Datenpflege liegt mehr als 36 Stunden zurück')
            except (TypeError,ValueError,json.JSONDecodeError):
                add('Datenpflege','warn','Status unlesbar',maintenance['ts'],'Gespeicherter Wartungsstatus ist ungültig')
        else:
            add('Datenpflege','neutral','Noch kein begrenzter Bereinigungslauf',None)
        battery = marstek_status(self.path,now)
        bsample, battempt = battery['sample'], battery['attempt']
        berror = bool(battempt and battempt['error'])
        control = battery.get('control',{})
        label = ('Abruffehler' if berror else 'Noch keine Messdaten' if bsample is None
                 else 'Messwerte veraltet' if battery['stale'] else 'Verbunden · Messwerte aktuell')
        control_warning = control.get('message','').startswith('Begrenzung nicht bestätigt')
        manual = bool(control.get('conflict')) or control.get('message','').startswith(('Automatik pausiert', 'Manuelle/externe Vorgabe'))
        if not battery['stale'] and manual and not control_warning:
            label += ' · Manuelle Vorgabe aktiv · Automatik pausiert'
        if not battery['stale'] and control_warning:
            label += ' · Begrenzung prüfen'
        add('Marstek','error' if berror else 'neutral' if bsample is None else 'warn' if battery['stale'] or control_warning else 'neutral' if manual else 'ok',
            label,bsample['ts'] if bsample else None,
            'Letzte Marstek-Abfrage fehlgeschlagen' if berror else 'Automatische Begrenzung benötigt Prüfung' if control_warning else None)
        tick = time.monotonic()
        if self.checked is None or tick-self.checked >= 60:
            try:
                self.storage = dict(database_bytes=self.path.stat().st_size,
                    wal_bytes=Path(str(self.path)+'-wal').stat().st_size if Path(str(self.path)+'-wal').exists() else 0,
                    free_bytes=shutil.disk_usage(self.path.parent).free, checked_at=now)
            except OSError:
                self.storage = dict(error='Speicherinformationen nicht verfügbar')
            self.checked = tick
        return dict(version=self.version,items=items,storage=self.storage,checked_at=now)
