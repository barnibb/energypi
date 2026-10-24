"""Kosten-Beobachtungsplan. Keine Gerätebefehle, keine externen API-Abfragen."""
import json
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from database import connect, initialize
from preferences import read_preferences, initialize_preferences
from forecast import latest_day
from settings import load_settings

ZONE=ZoneInfo('Europe/Berlin')



def initialize_optimizer(path):
    initialize(path)
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS observation_plans (id INTEGER PRIMARY KEY, ts REAL NOT NULL, payload TEXT NOT NULL)')


def interpolate(points, stamp):
    if stamp<=points[0]['ts']:return points[0]['wh']
    if stamp>=points[-1]['ts']:return points[-1]['wh']
    for a,b in zip(points,points[1:]):
        if a['ts']<=stamp<=b['ts']:
            return a['wh']+(b['wh']-a['wh'])*(stamp-a['ts'])/(b['ts']-a['ts'])


def solve(slots, prefs, soc, allow_grid):
    """Discrete dynamic programming; end inventory >= start/reserve, no battery export."""
    capacity=prefs['plan_capacity_kwh'];eta=math.sqrt(prefs['plan_efficiency']/100)
    initial=capacity*soc/100;minimum=min(initial,capacity*prefs['plan_min_soc']/100)
    maximum=capacity*prefs['plan_max_soc']/100
    terminal=max(initial,capacity*prefs['plan_end_soc']/100)
    levels=sorted(set([initial,minimum,maximum,terminal]+[round(i*.02,6) for i in range(math.ceil(minimum/.02),math.floor(maximum/.02)+1)]))
    start=levels.index(initial);costs={start:0.0};paths=[]
    for slot in slots:
        duration=(slot['end']-slot['start'])/3600
        deficit=slot['load_kwh']-slot['pv_kwh'];new={};links={}
        for i,cost in costs.items():
            for j,energy in enumerate(levels):
                delta=energy-levels[i]
                if delta>1e-9 and energy>maximum+1e-9:continue
                if delta>prefs['plan_charge_w']/1000*duration*eta+1e-9:continue
                if delta < -1e-9 and energy < capacity*prefs['plan_min_soc']/100-1e-9:continue
                discharge=max(0,-delta)*eta
                if discharge>prefs['plan_discharge_w']/1000*duration+1e-9 or discharge>max(0,deficit)+1e-9:continue
                charge=max(0,delta)/eta
                if not allow_grid and charge>max(0,-deficit)+1e-9:continue
                grid=deficit+charge-discharge
                money=max(0,grid)*slot['price_ct']-max(0,-grid)*prefs['feed_in_ct']
                objective=cost+money+discharge*(prefs['plan_wear_ct']+prefs['plan_margin_ct'])
                if j not in new or objective<new[j]-1e-9:
                    new[j]=objective;links[j]=(i,charge,discharge,grid,money)
        if not new:return None
        costs=new;paths.append(links)
    candidates=[j for j in costs if levels[j]>=terminal-1e-9]
    if not candidates:return None
    j=min(candidates,key=lambda key:costs[key]);objective=costs[j];rows=[]
    for slot,links in reversed(list(zip(slots,paths))):
        i,charge,discharge,grid,money=links[j]
        rows.append(dict(**slot,soc=levels[j]/capacity*100,charge_kwh=charge,discharge_kwh=discharge,
                         grid_kwh=grid,cost_ct=money,
                         action='Netzladen' if charge>0 and grid>0 else 'PV laden' if charge>0 else 'Haus versorgen' if discharge>0 else 'Akku halten'))
        j=i
    rows.reverse()
    return dict(slots=rows,cost_eur=sum(r['cost_ct']+r['discharge_kwh']*prefs['plan_wear_ct'] for r in rows)/100,
                objective_ct=objective,end_soc=rows[-1]['soc'])


def build_plan(path,now=None):
    now=time.time() if now is None else now;prefs=read_preferences(path)
    result=dict(created=now,parameters=prefs,status='unavailable',message='',slots=[],warnings=[])
    if not prefs['plan_enabled']:
        result.update(status='disabled',message='Beobachtungsplanung ausgeschaltet.');return result
    with connect(path) as db:
        sample=db.execute('SELECT ts,soc,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone()
        if not sample or sample['error'] or not 0<=now-sample['ts']<=90:
            result['message']='Aktueller Akku-Ladestand fehlt.';return result
        meta=db.execute('SELECT home_id FROM tibber_meta WHERE id=1').fetchone()
        start=math.ceil(now/900)*900
        prices=db.execute('SELECT starts_at,ends_at,total,currency FROM tibber_prices WHERE home_id=? AND starts_at>=? AND starts_at<? ORDER BY starts_at',
            (meta['home_id'] if meta else '',start,start+prefs['plan_hours']*3600)).fetchall()
        charging=db.execute('SELECT active,valid,updated_at FROM charging_state WHERE id=1').fetchone()
        days={};slots=[];cursor=start
        for row in prices:
            if row['starts_at']!=cursor or row['ends_at']-cursor!=900 or row['currency']!='EUR':break
            day=datetime.fromtimestamp(cursor,ZONE).date().isoformat()
            if day not in days:days[day]=latest_day(db,day)
            forecast=days[day]
            if not forecast or not 0<=now-forecast['issued_at']<=86400:break
            curve=forecast['cumulative']
            pv=max(0,interpolate(curve,cursor+900)-interpolate(curve,cursor))/1000*(1-prefs['plan_pv_discount']/100)
            slots.append(dict(start=cursor,end=cursor+900,price_ct=row['total']*100,pv_kwh=pv,load_kwh=prefs['plan_house_w']/4000))
            cursor+=900
    if len(slots)<4:
        result['message']='Mindestens eine Stunde lückenlose Tibber-Preise und PV-Prognose erforderlich.';return result
    result['warnings']=['Hausbedarf als konstanter Einstellwert; noch kein gelerntes Verbrauchsprofil.','Kapazität, Wirkungsgrad und Verschleiß sind einstellbare Modellannahmen. Keine garantierte Ersparnis.','Endladestand mindestens Startladestand bzw. Endreserve: kein künstlicher Vorteil durch Leerrechnen des Akkus.']
    if cursor<start+prefs['plan_hours']*3600:result['warnings'].append('Horizont wegen fehlender Preise oder Prognose verkürzt.')
    if any(now-d['issued_at']>21600 for d in days.values() if d):result['warnings'].append('PV-Prognose älter als sechs Stunden; erhöhte Unsicherheit.')
    effective=prefs.copy()
    if charging and charging['active'] and charging['valid'] and 0<=now-charging['updated_at']<=20:
        effective['plan_discharge_w']=min(prefs['plan_discharge_w'],prefs['ev_discharge_limit_w'])
        result['warnings'].append('Aktuell Autoladen oder Dauerlastschutz erkannt: Entladegrenze vorsorglich im gesamten Plan berücksichtigt. Zusätzlicher Verbrauch selbst ist nicht vorhergesagt.')
    if prefs['marstek_interval_seconds']>900:result['warnings'].append('Planraster 15 Minuten; längerer Steuer-Mindestabstand ist noch nicht als Schaltbedingung modelliert.')
    result['effective_discharge_w']=effective['plan_discharge_w']
    result['forecast_issued_at']={day:value['issued_at'] for day,value in days.items() if value}
    best=solve(slots,effective,sample['soc'],bool(prefs['plan_grid_charge']))
    if not best:
        result['message']='Mit Reserve, Leistungsgrenzen und Datenhorizont kein gültiger Plan gefunden.';return result
    result.update(best,status='ready',message='Kostenplan zur Beobachtung · keine Steuerbefehle',start=start,end=cursor,start_soc=sample['soc'],soc_measured_at=sample['ts'])
    return result


def collect_plan(path,now=None):
    now=time.time() if now is None else now
    result=build_plan(path,now)
    with connect(path) as db:
        db.execute('INSERT INTO observation_plans(ts,payload) VALUES (?,?)',(now,json.dumps(result,ensure_ascii=False)))
    return result


def plan_status(path,now=None):
    now=time.time() if now is None else now
    if not read_preferences(path)['plan_enabled']:
        return dict(status='disabled',message='Beobachtungsplanung ausgeschaltet.',slots=[],stale=False)
    with connect(path) as db:row=db.execute('SELECT ts,payload FROM observation_plans ORDER BY id DESC LIMIT 1').fetchone()
    if not row:return dict(status='pending',message='Erster Beobachtungsplan steht noch aus.',slots=[],stale=True)
    result=json.loads(row['payload']);result['stale']=not 0<=now-row['ts']<=1200
    result['settings_changed']=result['parameters']!=read_preferences(path)
    return result


if __name__=='__main__':
    path=load_settings()['database_path'];initialize_optimizer(path);initialize_preferences(path)
    print(collect_plan(path)['message'])
