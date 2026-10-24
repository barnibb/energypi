"""Zeit-, Reserve- und prognoseabhängige Freigabe der Entladeleistung."""
from datetime import datetime
import json
import math
from zoneinfo import ZoneInfo
from database import connect

ZONE=ZoneInfo('Europe/Berlin')


def market_context(path,prefs,now):
    local=datetime.fromtimestamp(now,ZONE);day=local.date().isoformat()
    price=pv=None
    with connect(path) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if {'tibber_prices','tibber_meta'}<=tables:
            meta=db.execute('SELECT home_id FROM tibber_meta WHERE id=1').fetchone()
            if meta:
                row=db.execute('SELECT total FROM tibber_prices WHERE home_id=? AND starts_at<=? AND ends_at>?',(meta[0],now,now)).fetchone()
                price=row[0]*100 if row else None
        if {'forecast_runs','forecast_days'}<=tables:
            row=db.execute('''SELECT r.ts,d.payload FROM forecast_days d JOIN forecast_runs r ON r.id=d.run_id
                              WHERE d.day=? AND r.error IS NULL ORDER BY r.ts DESC LIMIT 1''',(day,)).fetchone()
            if row and 0<=now-row['ts']<=14400:
                data=json.loads(row['payload']);curve=data.get('cumulative') or []
                if curve:
                    if now<=curve[0]['ts']:pv=float(data['total_kwh'])
                    elif now>=curve[-1]['ts']:pv=0.0
                    else:
                        for a,b in zip(curve,curve[1:]):
                            if a['ts']<=now<b['ts']:
                                used=a['wh']+(b['wh']-a['wh'])*(now-a['ts'])/(b['ts']-a['ts'])
                                pv=max(0,float(data['total_kwh'])-used/1000);break
    threshold=prefs['feed_in_ct']/(prefs['plan_efficiency']/100)+prefs['plan_wear_ct']+prefs['plan_margin_ct']
    return dict(price_ct=price,pv_remaining_kwh=pv,threshold_ct=threshold)


def night_target_soc(prefs):
    usable=prefs['night_energy_kwh']*(1+prefs['battery_loss_percent']/100)
    return min(100.0,prefs['morning_min_soc']+100*usable/prefs['plan_capacity_kwh'])


def update_morning(path,state,prefs,charging,soc,battery_power_w,now):
    local=datetime.fromtimestamp(now,ZONE);hour=local.hour
    previous=bool((state.get('morning') or {}).get('active'))
    in_window=bool(prefs['morning_enabled']) and prefs['morning_start_hour']<=hour<prefs['morning_end_hour']
    active=in_window and soc is not None and soc>prefs['morning_min_soc']
    context=market_context(path,prefs,now)
    target=night_target_soc(prefs)
    night_hours=(24-prefs['night_start_hour'])+prefs['morning_start_hour']
    night_limit=min(800,int(math.ceil((prefs['night_energy_kwh']*1000/max(1,night_hours))/50)*50))
    missing=max(0.0,(target-(soc or 0))*prefs['plan_capacity_kwh']/100)
    required=missing+prefs['forecast_reserve_margin_kwh']
    forecast_good=context['pv_remaining_kwh'] is not None and context['pv_remaining_kwh']>=required
    m=dict(active=active,window_start_hour=prefs['morning_start_hour'],window_end_hour=prefs['morning_end_hour'],
           min_soc=prefs['morning_min_soc'],release_w=prefs['morning_release_w'],night_start_hour=prefs['night_start_hour'],
           night_energy_kwh=prefs['night_energy_kwh'],night_target_soc=round(target,1),night_limit_w=night_limit,forecast_good=forecast_good,
           pv_remaining_kwh=context['pv_remaining_kwh'],forecast_required_kwh=round(required,2),reason='durchgehende Morgenfreigabe')
    state['morning']=m
    changed='START' if active and not previous else 'END' if previous and not active else None
    return (int(prefs['morning_release_w']) if active else None),changed
