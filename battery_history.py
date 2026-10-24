"""Akku-Verlauf und AC-Energieintegration; keine Ergänzung von Messlücken."""
from database import connect


def day_data(path, start, end):
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='marstek_samples'").fetchone():
            rows=[]
        else:
            rows=db.execute('SELECT ts,soc,ac_power_w,error FROM marstek_samples WHERE ts>=? AND ts<=? ORDER BY ts', (start-90,end)).fetchall()
    segments=[];segment=[];previous=None;charged=discharged=covered=0.0
    first_soc=last_soc=None
    for row in rows:
        if row['error']:
            if segment: segments.append(segment)
            segment=[];previous=None
            continue
        ts=row['ts']
        if previous is not None and 0<ts-previous['ts']<=90:
            a=max(start,previous['ts']);b=min(end,ts)
            if b>a:
                duration=ts-previous['ts']
                p0=previous['ac_power_w'];p1=row['ac_power_w']
                left=p0+(p1-p0)*(a-previous['ts'])/duration
                right=p0+(p1-p0)*(b-previous['ts'])/duration
                seconds=b-a
                if left*right<0:
                    fraction=abs(left)/(abs(left)+abs(right))
                    discharged+=(max(left,0)*fraction+max(right,0)*(1-fraction))*seconds/2
                    charged+=(max(-left,0)*fraction+max(-right,0)*(1-fraction))*seconds/2
                else:
                    discharged+=(max(left,0)+max(right,0))*seconds/2
                    charged+=(max(-left,0)+max(-right,0))*seconds/2
                covered+=seconds
        elif segment:
            segments.append(segment);segment=[]
        if start<=ts<=end:
            segment.append(dict(ts=ts,soc=row['soc']))
            if first_soc is None:first_soc=row['soc']
            last_soc=row['soc']
        previous=row
    if segment:segments.append(segment)
    return dict(segments=segments,charge_kwh=charged/3600000 if covered else None,
                discharge_kwh=discharged/3600000 if covered else None,
                coverage=covered/(end-start) if end>start else 0,
                covered_seconds=covered,start_soc=first_soc,end_soc=last_soc)
