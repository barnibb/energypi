"""AC-Tagesbilanz mit Speicherflüssen; keine Herkunftszuordnung des Akkustroms."""
from database import connect
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from battery_history import day_data
from balance import estimate
from finance_summary import financial_summary
from sun_times import sun_times
from forecast import plant


SOLAR_DAY_CLOSE_TOLERANCE_SECONDS = 30 * 60


def solar_day_closed(selected, fetched_at, now):
    """Accept a final partial-day snapshot once local PV production has ended."""
    site=plant();sunset=sun_times(selected,site['latitude'],site['longitude'])['sunset']
    return (sunset is not None and now>=sunset and
            sunset-SOLAR_DAY_CLOSE_TOLERANCE_SECONDS<=fetched_at<=now)


def flow_summary(path,day,balance,now,feed_in_ct=9):
    zone=ZoneInfo('Europe/Berlin');selected=date.fromisoformat(day)
    start=datetime.combine(selected,time.min,zone).timestamp()
    end=datetime.combine(selected+timedelta(days=1),time.min,zone).timestamp()
    with connect(path) as db:
        row=db.execute('SELECT kwh,fetched_at FROM solaredge_energy WHERE day=?',(day,)).fetchone()
    today=day==datetime.fromtimestamp(now,zone).date().isoformat()
    # Today's PV total is only known up to its fetch time: align other integrations.
    until=min(end,now,row['fetched_at']) if today and row else min(end,now)
    until=max(start,until)
    grid=estimate(path,start,until) if today and row else balance
    battery=day_data(path,start,until)
    result=dict(pv_kwh=row['kwh'] if row else None,pv_fetched_at=row['fetched_at'] if row else None,
                import_kwh=grid['import_kwh'],export_kwh=grid['export_kwh'],
                retained_kwh=None,estimated_share=None,autarky_percent=None,house_kwh=None,
                battery_in_kwh=battery['charge_kwh'],battery_out_kwh=battery['discharge_kwh'],
                battery_start_soc=battery['start_soc'],battery_end_soc=battery['end_soc'],
                battery_coverage=battery['coverage'],valid=False,until=until)
    closed=today and row is not None and solar_day_closed(selected,row['fetched_at'],now)
    if row is None:reason='SolarEdge-Tagesertrag fehlt.'
    elif today and not 0<=now-row['fetched_at']<=7200 and not closed:reason='SolarEdge-Tagesertrag ist veraltet.'
    elif grid['coverage']<.95 or grid['import_kwh'] is None or grid['export_kwh'] is None:reason='Weniger als 95 % Netz-Messabdeckung; keine vollständige Tagesbilanz.'
    elif battery['coverage']<.95 or battery['charge_kwh'] is None:reason='Weniger als 95 % Akku-Messabdeckung; Akku-kWh sind nur erfasste Teilmengen. Keine vollständige Tagesbilanz.'
    elif row['kwh']<0:reason='Ungültiger PV-Tagesertrag.'
    else:
        house=row['kwh']+grid['import_kwh']+battery['discharge_kwh']-grid['export_kwh']-battery['charge_kwh']
        if house<0:reason='Zeitversatz oder Messabweichung: rechnerischer Hausverbrauch negativ; keine Aufteilung.'
        else:
            result.update(house_kwh=house,valid=True)
            reason='AC-Energiebilanz: Hausverbrauch rechnerisch, Akku-Flüsse aus Leistung integriert. SolarEdge kann verzögert sein; Prozentwerte zeigen Energieflüsse, keinen Autarkiegrad.'
            if closed:reason+=' PV-Tag nach Sonnenuntergang abgeschlossen.'
    if today and row:reason+=' Gemeinsamer Bilanzstand: '+datetime.fromtimestamp(until,zone).strftime('%H:%M')+' Uhr.'
    result['reason']=reason
    result['money']=financial_summary(path,start,until,result,feed_in_ct)
    return result
