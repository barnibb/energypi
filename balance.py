"""Geschätzte Energie aus Leistung; Messlücken werden nicht überbrückt."""
import json
from database import history, connect


def estimate(path, start, end):
    # Only the total power is needed here. Avoid building full chart statistics
    # for every individual sample (ten channels, min/max/mean).
    with connect(path) as db:
        db.execute('BEGIN')
        archived = db.execute(
            'SELECT payload FROM minute_archive WHERE minute>=? AND minute<? ORDER BY minute',
            (int(start // 60) * 60, end)).fetchall()
        rows = db.execute(
            'SELECT ts,total_act_power,error FROM measurements WHERE ts>=? AND ts<? ORDER BY ts',
            (start, end)).fetchall()
    points = [(p['first'], p['last'], p.get('total_act_power'), bool(p.get('error')))
              for row in archived for p in json.loads(row['payload']) if start <= p['ts'] < end]
    points.extend((r['ts'], r['ts'], r['total_act_power'], bool(r['error'])) for r in rows)
    points.sort(key=lambda p: p[0])
    imported = exported = covered = 0.0
    def integrate(a,b,seconds):
        if a*b < 0:
            fraction=abs(a)/(abs(a)+abs(b))
            positive=(max(a,0)*fraction+max(b,0)*(1-fraction))*seconds/2
            negative=(max(-a,0)*fraction+max(-b,0)*(1-fraction))*seconds/2
            return positive,negative
        return (max(a,0)+max(b,0))*seconds/2,(max(-a,0)+max(-b,0))*seconds/2
    previous = None
    for first, last, power, error in points:
        if error:
            previous = None
            continue
        if previous is not None and first - previous[0] <= 15:
            duration = first - previous[0]
            i, e = integrate(previous[1], power, duration)
            imported += i; exported += e; covered += duration
        if last > first:
            duration = last - first
            i, e = integrate(power, power, duration)
            imported += i; exported += e; covered += duration
        previous = (last, power)
    return dict(import_kwh=imported/3600000 if covered else None,
                export_kwh=exported/3600000 if covered else None,
                covered_seconds=covered,missing_seconds=max(0,end-start-covered),
                coverage=covered/(end-start) if end>start else 0)


def charging_periods(path,start,end,segments):
    with connect(path) as db:
        previous=db.execute('SELECT detected_at,event FROM charging_events WHERE detected_at<? ORDER BY detected_at DESC,id DESC LIMIT 1',(start,)).fetchone()
        events=db.execute('SELECT detected_at,event FROM charging_events WHERE detected_at>=? AND detected_at<? ORDER BY detected_at,id',(start,end)).fetchall()
    active=start if previous and previous['event']=='START_DETECTED' else None
    periods=[]
    for event in events:
        if event['event']=='START_DETECTED':active=event['detected_at']
        elif active is not None:
            periods.append((active,event['detected_at']));active=None
    if active is not None:periods.append((active,end))
    # Nur beobachtete Abschnitte markieren, keine Messlücken oder Zukunft.
    return [dict(start=max(a,s[0]['first']),end=min(b,s[-1]['last']))
            for a,b in periods for s in segments
            if max(a,s[0]['first'])<min(b,s[-1]['last'])]
