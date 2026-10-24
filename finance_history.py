"""Historische Tageswerte des effektiven Haushaltsstrompreises."""
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from balance import estimate
from flow_summary import flow_summary

ZONE=ZoneInfo('Europe/Berlin')
CACHE_VERSION=2


def initialize_cache(path):
    from database import connect
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS finance_history_cache (
            day TEXT NOT NULL, feed_in_ct REAL NOT NULL, pv_fetched_at REAL,
            generated_at REAL NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(day,feed_in_ct))''')


def persistent_point(path,day,feed_in_ct):
    """Return a completed past day while its SolarEdge source is unchanged."""
    from database import connect
    initialize_cache(path)
    with connect(path) as db:
        cached=db.execute('SELECT pv_fetched_at,payload FROM finance_history_cache WHERE day=? AND feed_in_ct=?',
                          (day.isoformat(),float(feed_in_ct))).fetchone()
        source=db.execute('SELECT fetched_at FROM solaredge_energy WHERE day=?',(day.isoformat(),)).fetchone()
    if not cached or not source or cached['pv_fetched_at'] != source['fetched_at']:
        return None
    try:
        point=json.loads(cached['payload'])
    except (TypeError,ValueError):
        return None
    return point if point.get('complete') and point.get('cache_version')==CACHE_VERSION else None


def store_point(path,point,feed_in_ct,now):
    from database import connect
    if not point.get('complete') or point.get('today'):
        return
    point={**point,'cache_version':CACHE_VERSION}
    initialize_cache(path)
    with connect(path) as db:
        source=db.execute('SELECT fetched_at FROM solaredge_energy WHERE day=?',(point['day'],)).fetchone()
        if source:
            db.execute('''INSERT INTO finance_history_cache(day,feed_in_ct,pv_fetched_at,generated_at,payload)
                VALUES(?,?,?,?,?) ON CONFLICT(day,feed_in_ct) DO UPDATE SET
                pv_fetched_at=excluded.pv_fetched_at,generated_at=excluded.generated_at,payload=excluded.payload''',
                (point['day'],float(feed_in_ct),source['fetched_at'],now,
                 json.dumps(point,ensure_ascii=False,separators=(',',':'))))


def bounds(day):
    start=datetime.combine(day,time.min,ZONE)
    end=datetime.combine(day+timedelta(days=1),time.min,ZONE)
    return start.timestamp(),end.timestamp()


def daily_point(path,day,now,feed_in_ct):
    start,end=bounds(day)
    balance=estimate(path,start,min(end,now))
    flows=flow_summary(path,day.isoformat(),balance,now,feed_in_ct)
    money=flows['money'];price=money.get('effective_house_price_ct')
    complete=bool(money.get('complete') and price is not None)
    benefit=money.get('benefit_eur') if complete else None
    net_cost=(money['import_cost_eur']-money['feed_revenue_eur']) if complete else None
    pv_direct=money.get('pv_direct_kwh') if complete else None
    battery_out=flows.get('battery_out_kwh') if complete else None
    house=flows.get('house_kwh') if complete else None
    self_supply=(pv_direct+battery_out if pv_direct is not None and battery_out is not None else None)
    return {'cache_version':CACHE_VERSION,'day':day.isoformat(),'today':day==datetime.fromtimestamp(now,ZONE).date(),
            'complete':complete,'effective_house_price_ct':price if complete else None,
            'import_cost_eur':money.get('import_cost_eur') if complete else None,
            'feed_revenue_eur':money.get('feed_revenue_eur') if complete else None,
            'net_cost_eur':net_cost,'benefit_eur':benefit,
            'cost_without_self_supply_eur':net_cost+benefit if complete and benefit is not None else None,
            'pv_benefit_eur':money.get('pv_benefit_eur') if complete else None,
            'battery_value_eur':money.get('battery_value_eur') if complete else None,
            'self_supply_kwh':self_supply,
            'self_supply_percent':self_supply/house*100 if self_supply is not None and house and house>0 else None,
            'house_kwh':house,
            'reason':None if complete else flows.get('reason','Tageswert nicht vollständig.')}


def history(path,now,feed_in_ct,days=10,cache=None,start_day=None):
    today=datetime.fromtimestamp(now,ZONE).date();points=[]
    selected_days=([start_day+timedelta(days=offset) for offset in range(days)] if start_day
                   else [today-timedelta(days=offset) for offset in range(days-1,-1,-1)])
    for day in selected_days:
        key=(day.isoformat(),float(feed_in_ct))
        stored=cache.get(key) if cache is not None and day<today else None
        point=stored[1] if stored else persistent_point(path,day,feed_in_ct) if day<today else None
        if point is None and day>today:
            point={'day':day.isoformat(),'today':False,'complete':False,
                   'effective_house_price_ct':None,'import_cost_eur':None,
                   'feed_revenue_eur':None,'net_cost_eur':None,'house_kwh':None,
                   'benefit_eur':None,'cost_without_self_supply_eur':None,
                   'reason':'Tag liegt in der Zukunft.'}
        elif point is None:
            point=daily_point(path,day,now,feed_in_ct)
            if day<today and point['complete']:
                store_point(path,point,feed_in_ct,now)
        if cache is not None and day<today and point['complete']:cache[key]=(now,point)
        points.append(point)
    first=selected_days[0];iso=first.isocalendar()
    complete=[point for point in points if point.get('complete')]
    def total(field):
        values=[point.get(field) for point in complete]
        return sum(values) if values and all(value is not None for value in values) else None
    house_total=total('house_kwh');self_supply_total=total('self_supply_kwh')
    return {'days':days,'generated_at':now,'points':points,
            'week_start':first.isoformat(),'week_end':selected_days[-1].isoformat(),
            'week_year':iso.year,'week_number':iso.week,
            'summary':{'complete_days':len(complete),'benefit_eur':total('benefit_eur'),
                       'net_cost_eur':total('net_cost_eur'),
                       'cost_without_self_supply_eur':total('cost_without_self_supply_eur'),
                       'house_kwh':house_total,'self_supply_kwh':self_supply_total,
                       'self_supply_percent':self_supply_total/house_total*100 if house_total and self_supply_total is not None else None},
            'formula':'(Netzbezugskosten − Einspeisevergütung) ÷ Hausverbrauch'}
