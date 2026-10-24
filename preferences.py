"""Dauerhafte Dashboard-Einstellungen mit Änderungsverlauf."""
import json
import math
import time
from database import connect
from planning_defaults import PLAN_DEFAULTS

DEFAULTS=dict(block_above_w=2000,release_below_w=1000,hold_seconds=180,max_gap_seconds=15,
              sustained_discharge_w=750,sustained_discharge_seconds=600,
              marstek_interval_seconds=900,feed_in_ct=9,base_load_w=160,ev_current_a=5,
              fan_minutes=20,ev_discharge_limit_w=200,pv_sunshine_threshold_w=2000,frost_temperature_c=0,forecast_start_hour=5,forecast_end_hour=23,
              morning_enabled=1,morning_start_hour=5,morning_end_hour=10,
              morning_release_w=800,morning_min_soc=12,
              night_start_hour=22,night_energy_kwh=1.6,battery_loss_percent=10,
              forecast_reserve_margin_kwh=1.0,
              soc_high_threshold=60,soc_medium_threshold=40,soc_low_threshold=20,
              soc_high_w=800,soc_medium_w=300,soc_low_w=100,soc_reserve_w=100)

DEFAULTS.update(PLAN_DEFAULTS)

def initialize_preferences(path):
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS preferences(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS preference_changes(id INTEGER PRIMARY KEY,ts REAL NOT NULL,old_payload TEXT NOT NULL,new_payload TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO preferences VALUES(1,?)',(json.dumps(DEFAULTS),))

def read_preferences(path):
    with connect(path) as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='preferences'").fetchone()
        row=db.execute('SELECT payload FROM preferences WHERE id=1').fetchone() if exists else None
    stored=json.loads(row[0]) if row else {}
    # Alte, inzwischen ersetzte Parameter nicht wieder in POST-Nutzlasten tragen.
    return {**DEFAULTS, **{key:value for key,value in stored.items() if key in DEFAULTS}}

def save_preferences(path,values,poll):
    if not isinstance(values,dict) or set(values)!=set(DEFAULTS):raise ValueError('Alle Einstellungen sind erforderlich.')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values.values()):raise ValueError('Bitte gültige Zahlen eingeben.')
    if not 0<=values['release_below_w']<values['block_above_w']<=100000:raise ValueError('Startschwelle muss größer als Endschwelle sein (0–100.000 W).')
    if not 1<=values['hold_seconds']<=3600:raise ValueError('Bestätigungsdauer: 1–3.600 Sekunden.')
    if values['sustained_discharge_w']!=int(values['sustained_discharge_w']) or not 50<=values['sustained_discharge_w']<=800:raise ValueError('Dauerlastschutz-Leistung: ganze Watt von 50 bis 800.')
    if values['sustained_discharge_seconds']!=int(values['sustained_discharge_seconds']) or not 60<=values['sustained_discharge_seconds']<=3600:raise ValueError('Dauerlastschutz-Dauer: ganze Sekunden von 60 bis 3.600.')
    if not 2*poll<=values['max_gap_seconds']<=3600:raise ValueError(f'Messlücke: mindestens {2*poll:g}, höchstens 3.600 Sekunden.')
    if not 60<=values['marstek_interval_seconds']<=86400:raise ValueError('Marstek-Abstand: 1–1.440 Minuten.')
    if not 0<=values['feed_in_ct']<=100:raise ValueError('Einspeisevergütung: 0–100 ct/kWh.')
    if not 0<=values['base_load_w']<=10000:raise ValueError('Hausgrundlast: 0–10.000 W.')
    if not 1<=values['ev_current_a']<=32:raise ValueError('Ladestrom: 1–32 A.')
    if not 1<=values['fan_minutes']<=120 or values['fan_minutes']!=int(values['fan_minutes']):raise ValueError('Lüfterlaufzeit: ganze Minuten von 1 bis 120.')
    if values['pv_sunshine_threshold_w']!=int(values['pv_sunshine_threshold_w']) or not 500<=values['pv_sunshine_threshold_w']<=7000 or values['pv_sunshine_threshold_w']%100:raise ValueError('Sonnenstrahlen-Schwelle: 500–7.000 W in 100-W-Schritten.')
    if not -20<=values['frost_temperature_c']<=18 or values['frost_temperature_c']*2!=int(values['frost_temperature_c']*2):raise ValueError('Frostschwelle: −20 bis 18 °C in 0,5-Grad-Schritten.')
    if not 0<=values['ev_discharge_limit_w']<=800 or values['ev_discharge_limit_w']%50:raise ValueError('Akku-Grenze bei Autoladen: 0–800 W in 50-W-Schritten.')
    if any(values[k]!=int(values[k]) for k in ('forecast_start_hour','forecast_end_hour')) or not 0<=values['forecast_start_hour']<values['forecast_end_hour']<=24:raise ValueError('Diagrammzeit: ganze Stunden, 0 ≤ Beginn < Ende ≤ 24.')
    if values['morning_enabled'] not in (0,1):raise ValueError('Morgenkomfort-Schalter: 0 oder 1.')
    if any(values[k]!=int(values[k]) for k in ('morning_start_hour','morning_end_hour')) or not 0<=values['morning_start_hour']<values['morning_end_hour']<=24:raise ValueError('Morgenkomfort-Zeit: ganze Stunden, Beginn vor Ende.')
    if not 100<=values['morning_release_w']<=800 or values['morning_release_w']%50:raise ValueError('Morgenfreigabe: 100–800 W in 50-W-Schritten.')
    if not 11<=values['morning_min_soc']<=30:raise ValueError('Morgenkomfort-Untergrenze: 11–30 %.')
    if values['night_start_hour']!=int(values['night_start_hour']) or not values['morning_end_hour']<values['night_start_hour']<=23:raise ValueError('Nachtbeginn: ganze Stunde nach dem Morgenende, höchstens 23 Uhr.')
    if not 0<=values['night_energy_kwh']<=10:raise ValueError('Nachtbedarf: 0–10 kWh.')
    if not 0<=values['battery_loss_percent']<=30:raise ValueError('Akku-Verlustaufschlag: 0–30 %.')
    if not 0<=values['forecast_reserve_margin_kwh']<=10:raise ValueError('Prognose-Sicherheitsreserve: 0–10 kWh.')
    thresholds=(values['soc_low_threshold'],values['soc_medium_threshold'],values['soc_high_threshold'])
    if any(v!=int(v) for v in thresholds) or not values['morning_min_soc']<thresholds[0]<thresholds[1]<thresholds[2]<100:raise ValueError('SOC-Schwellen müssen ganzzahlig und aufsteigend über der Schutzgrenze liegen.')
    for key in ('soc_high_w','soc_medium_w','soc_low_w','soc_reserve_w'):
        if values[key]!=int(values[key]) or not 0<=values[key]<=800 or values[key]%50:raise ValueError('SOC-Leistungen: 0–800 W in 50-W-Schritten.')
    for key in ('plan_enabled','plan_grid_charge'):
        if values[key] not in (0,1):raise ValueError('Plan-Schalter: 0 oder 1.')
    if not 1<=values['plan_capacity_kwh']<=30:raise ValueError('Plan-Kapazität: 1–30 kWh.')
    if not 0<=values['plan_min_soc']<values['plan_max_soc']<=100 or not values['plan_min_soc']<=values['plan_end_soc']<=values['plan_max_soc']:raise ValueError('Plan-Ladestände: Minimum < Maximum; Endreserve dazwischen.')
    for key,low,high in (('plan_efficiency',50,100),('plan_wear_ct',0,50),('plan_margin_ct',0,50),('plan_pv_discount',0,100),('plan_house_w',0,10000),('plan_charge_w',0,2500),('plan_discharge_w',0,800),('plan_hours',1,36)):
        if not low<=values[key]<=high:raise ValueError(f'{key}: {low}–{high}.')
    if values['plan_hours']!=int(values['plan_hours']):raise ValueError('Planhorizont in ganzen Stunden.')
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT payload FROM preferences WHERE id=1').fetchone()[0]
        new=json.dumps(values,sort_keys=True)
        if json.loads(old)!=values:
            db.execute('INSERT INTO preference_changes(ts,old_payload,new_payload) VALUES(?,?,?)',(time.time(),old,new))
            db.execute('UPDATE preferences SET payload=? WHERE id=1',(new,))

def save_ev_discharge_limit(path,value,poll):
    values=read_preferences(path)
    values['ev_discharge_limit_w']=value
    save_preferences(path,values,poll)
    return read_preferences(path)['ev_discharge_limit_w']
