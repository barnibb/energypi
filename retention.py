"""Read-only inventory for staged database retention."""
import time
from pathlib import Path
from database import connect


TIMED_TABLES = (
    ('measurements','Shelly-Rohwerte','ts'),
    ('minute_archive','Shelly-Minutenarchiv','minute'),
    ('marstek_samples','Marstek-Rohwerte','ts'),
    ('solaredge_samples','SolarEdge-Leistung','ts'),
    ('weather_samples','Wetterwerte','valid_at'),
    ('forecast_runs','PV-Prognoseläufe','ts'),
    ('tibber_prices','Tibber-Preise','starts_at'),
    ('observation_plans','Beobachtungspläne','ts'),
    ('finance_history_cache','Finanzcache','generated_at'),
)

COUNT_TABLES = (
    ('forecast_days','PV-Prognosetage'),
    ('solaredge_energy','SolarEdge-Tageserträge'),
)


def _exists(db, table):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone() is not None


def _sizes(db):
    try:
        return {row['name']:int(row['bytes'] or 0) for row in db.execute(
            'SELECT name,SUM(pgsize) AS bytes FROM dbstat GROUP BY name')}
    except Exception:
        return {}


def inventory(path, now=None):
    """Collect counts and ranges without creating archives or deleting data."""
    now=time.time() if now is None else now
    result={'version':1,'generated_at':now,'database_bytes':Path(path).stat().st_size,'tables':{}}
    with connect(path) as db:
        db.execute('BEGIN')
        sizes=_sizes(db)
        for table,label,column in TIMED_TABLES:
            if not _exists(db,table):
                result['tables'][table]={'label':label,'present':False,'rows':0,'bytes':0}
                continue
            row=db.execute(f'SELECT COUNT(*) AS rows,MIN("{column}") AS oldest,MAX("{column}") AS newest FROM "{table}"').fetchone()
            result['tables'][table]={'label':label,'present':True,'rows':int(row['rows']),
                                     'oldest':row['oldest'],'newest':row['newest'],'bytes':sizes.get(table)}
        for table,label in COUNT_TABLES:
            if not _exists(db,table):
                result['tables'][table]={'label':label,'present':False,'rows':0,'bytes':0}
                continue
            count=db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            result['tables'][table]={'label':label,'present':True,'rows':int(count),'bytes':sizes.get(table)}
    return result


def with_growth(current, previous):
    previous=previous if isinstance(previous,dict) and previous.get('version')==1 else None
    elapsed=current['generated_at']-previous['generated_at'] if previous else None
    for table,item in current['tables'].items():
        before=previous['tables'].get(table) if previous else None
        item['rows_since_previous']=item['rows']-before['rows'] if before and elapsed and elapsed>0 else None
    current['seconds_since_previous']=elapsed if elapsed and elapsed>0 else None
    return current
