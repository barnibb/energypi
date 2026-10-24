"""Anzeigetexte und begrenztes Entscheidungsprotokoll aus lokalen Daten."""
from database import connect


def operating_status(control, sample, stale, now):
    checked=control.get('checked_at')
    old=stale or checked is None or not 0<=now-checked<=90
    mode=control.get('observed_mode');rs485=control.get('observed_rs485')
    if mode is None:label='Betriebsart noch nicht gelesen'
    elif rs485!=21947:label='Externe RS485-Steuerung'
    elif mode==0:
        watts=sample['ac_power_w'] if sample and not stale else None
        label='Manuelles Laden' if watts is not None and watts<-30 else 'Manuelle Entladung' if watts is not None and watts>30 else 'Manueller Modus · Pause'
    elif mode==1:
        capped=(control.get('baseline') is not None and not control.get('conflict')
                and control.get('applied')==control.get('observed_limit_w')
                and control['applied']<control['baseline'])
        if control.get('morning',{}).get('active') and control.get('effective_reason')=='morning':label='Morgenkomfort'
        elif capped and control.get('effective_reason')=='soc_safety':label='SOC-Sicherheitsbegrenzung'
        else:label=('Dauerlast-Begrenzung' if control.get('pending_reason')=='sustained_limit' else 'Autolade-Begrenzung') if capped else 'Eigenverbrauch'
    elif mode==2:label='Handelsmodus'
    else:label=f'Unbekannte Betriebsart ({mode})'
    return dict(label=label,limit_w=control.get('observed_limit_w'),stale=old,checked_at=checked)


def decision_log(path):
    with connect(path) as db:
        controls=db.execute('SELECT id,ts,event,value_w,detail FROM marstek_control_events ORDER BY id DESC LIMIT 60').fetchall()
        charging=db.execute('SELECT id,detected_at,event,reason FROM charging_events ORDER BY id DESC LIMIT 30').fetchall()
    entries=[]
    for r in controls:
        event=r['event'];value=r['value_w'];detail=r['detail'] or ''
        if event=='CONFIRMED':text=detail if '→' in detail else f'Entladegrenze {value} W bestätigt'
        elif event=='REQUEST':text=f'Entladegrenze {value} W angefordert (noch nicht bestätigt)'
        elif event=='SOC_BAND':text=f'SOC-Sicherheitsstufe gewechselt → maximal {value} W'
        elif event=='MORNING_START':text=detail or 'Morgenkomfort gestartet'
        elif event=='MORNING_END':text='Morgenkomfort beendet'
        elif event=='MODE_REQUEST':text='Wechsel auf Eigenverbrauch wird ausgeführt'
        elif event=='MODE_CONFIRMED':continue # action completion contains the same confirmation
        elif event=='USER_MODE_REQUEST':text='Eigenverbrauch per Button angefordert'
        elif event=='TARGET_CHANGED':text=detail or f'Autolade-Ziel auf {value} W geändert'
        elif event.startswith('ACTION_'):text=detail
        elif event=='ERROR':text='Entladebegrenzung nicht bestätigt · Verbindung oder Gerätestatus prüfen'
        else:continue
        entries.append(dict(ts=r['ts'],text=text,kind='error' if event in ('ERROR','ACTION_ERROR') else 'info',key='m'+str(r['id'])))
    for r in charging:
        duration=r['reason']=='sustained_discharge'
        text=('Dauerlastschutz aktiviert' if duration else 'Autoladen erkannt') if r['event']=='START_DETECTED' else ('Dauerlastschutz beendet' if duration else 'Autoladen beendet')
        entries.append(dict(ts=r['detected_at'],text=text,kind='info',key='c'+str(r['id'])))
    entries.sort(key=lambda x:(x['ts'],x['key']),reverse=True)
    return entries[:50]
