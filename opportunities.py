"""Potentiell günstige Viertelstunden; keine Ladeplanung oder Steuerung."""
import math
from datetime import datetime, timedelta
from database import connect
from forecast import latest_day
from preferences import read_preferences
from solaredge import ZONE

BASE_LOAD_W = 160
EV_POWER_W = 3 * 230 * 5  # 5 A dreiphasig: 3450 W
FEED_IN_CT = 9


def interpolate(points, ts):
    for p in points:
        if p['ts'] == ts:
            return p['w']
    for a,b in zip(points,points[1:]):
        if a['ts'] < ts < b['ts'] and b['ts'] - a['ts'] <= 7500:
            return a['w'] + (b['w']-a['w']) * (ts-a['ts']) / (b['ts']-a['ts'])
    return None


def battery_thresholds(settings, grid_reference_ct=None):
    """Break-even prices per delivered battery kWh; model values, not measurements."""
    efficiency=settings['plan_efficiency']/100
    additions=settings['plan_wear_ct']+settings['plan_margin_ct']
    pv=settings['feed_in_ct']/efficiency+additions
    grid=None if grid_reference_ct is None else grid_reference_ct/efficiency+additions
    return pv,grid


def annotate(path, day, prices, now, grid_reference_ct=None):
    settings=read_preferences(path)
    feed_in_ct=settings['feed_in_ct']
    base_load=settings['base_load_w']
    ev_power=3*230*settings['ev_current_a']
    start=datetime.combine(day,datetime.min.time(),ZONE).timestamp()
    end=datetime.combine(day+timedelta(days=1),datetime.min.time(),ZONE).timestamp()
    with connect(path) as db:
        # Auch ältere Installationen ohne Prognosetabelle liefern weiterhin Preise.
        table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='forecast_days'").fetchone()
        forecast=latest_day(db,day.isoformat()) if table else None
    historical=day<datetime.fromtimestamp(now,ZONE).date()
    valid=forecast is not None and (historical or 0<=now-forecast['issued_at']<=14400)
    points=forecast['points'] if valid else []
    values=sorted(p['ct'] for p in prices)
    threshold=values[math.ceil(len(values)/4)-1] if values and values[-1]-values[0]>1e-9 else None
    pv_battery_ct,grid_battery_ct=battery_thresholds(settings,grid_reference_ct)
    by_start={p['start']:p for p in prices}
    slots=[]
    for ts in range(int(start),int(end),900):
        price=by_start.get(ts)
        # Konservativ: Die Schwelle muss während der ganzen Viertelstunde erreicht sein.
        samples=[interpolate(points,ts),interpolate(points,ts+900)]
        samples.extend(p['w'] for p in points if ts<p['ts']<ts+900)
        minimum=min(samples) if samples and all(p is not None for p in samples) else None
        midpoint=interpolate(points,ts+450)
        slots.append({'start':ts,'end':ts+900,'ct':price['ct'] if price else None,
                      'cheap':price is not None and threshold is not None and price['ct']<=threshold,
                      'below_feed_in':price is not None and price['ct']<feed_in_ct,
                      'pv_surplus_w':max(0,midpoint-base_load) if midpoint is not None else None,
                      'pv_good':minimum is not None and minimum-base_load>=ev_power})
    return {'slots':slots,'feed_in_ct':feed_in_ct,'base_load_w':base_load,'ev_current_a':settings['ev_current_a'],'ev_power_w':ev_power,
            'pv_threshold_w':base_load+ev_power,'cheap_threshold_ct':threshold,
            'battery_pv_threshold_ct':pv_battery_ct,'battery_grid_threshold_ct':grid_battery_ct,
            'battery_grid_reference_ct':grid_reference_ct,'battery_efficiency_percent':settings['plan_efficiency'],
            'battery_wear_ct':settings['plan_wear_ct'],'battery_margin_ct':settings['plan_margin_ct'],
            'pv_state':'archive' if valid and historical else 'available' if valid else 'stale' if forecast else 'missing',
            'pv_issued_at':forecast['issued_at'] if forecast else None}
