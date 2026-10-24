"""Autolade-Grenze und ausdrücklich angeforderter Eigenverbrauchsmodus."""
import json
import socket
import struct
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from database import connect
from preferences import read_preferences
from charging import charging_status
from morning import update_morning

ZONE=ZoneInfo('Europe/Berlin')

def initialize_control(path):
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS marstek_control_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS marstek_control_events (id INTEGER PRIMARY KEY, ts REAL NOT NULL, event TEXT NOT NULL, value_w INTEGER, detail TEXT)')
        db.execute('INSERT OR IGNORE INTO marstek_control_state VALUES (1,?)', (json.dumps(dict(baseline=None, applied=None, pending=None, last_attempt=None, message='Noch nicht geprüft', conflict=False)),))


def control_status(path):
    with connect(path) as db:
        row = db.execute('SELECT payload FROM marstek_control_state WHERE id=1').fetchone()
    return json.loads(row[0]) if row else {}


def persist(path, state, now, event=None, value=None):
    with connect(path) as db:
        db.execute('UPDATE marstek_control_state SET payload=? WHERE id=1', (json.dumps(state),))
        if event:
            db.execute('INSERT INTO marstek_control_events(ts,event,value_w,detail) VALUES (?,?,?,?)',
                       (now, event, value, state['message']))


def observe(state, current, mode, rs485, now):
    state.update(observed_limit_w=current, observed_mode=mode, observed_rs485=rs485, checked_at=now)


def confirmed_message(state, value):
    reason=state.get('pending_reason')
    if reason=='ev_limit':return f'Autoladen erkannt → Entladegrenze auf {value} W bestätigt'
    if reason=='sustained_limit':return f'Dauerlastschutz → Entladegrenze auf {value} W bestätigt'
    if reason=='soc_limit':return f'SOC-Sicherheit → Entladegrenze auf {value} W bestätigt'
    if reason=='night_reserve':return f'Nachtreserve → Entladegrenze auf {value} W bestätigt'
    if reason=='night_supply':return f'Nachtversorgung → Entladegrenze auf {value} W bestätigt'
    if reason=='morning':return f'Morgenkomfort → Entladegrenze auf {value} W bestätigt'
    if reason=='restore':return f'Schutz beendet → vorherige Entladegrenze {value} W wiederhergestellt'
    return f'Entladegrenze {value} W bestätigt'


def latest_soc(path, now, max_age=90):
    with connect(path) as db:
        row=db.execute('SELECT ts,soc,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone()
    if not row or row['error'] or row['soc'] is None or not 0<=now-row['ts']<=max_age or not 0<=row['soc']<=100:
        return None
    return float(row['soc'])


def latest_battery_power(path,now,max_age=90):
    with connect(path) as db:
        row=db.execute('SELECT ts,ac_power_w,error FROM marstek_samples ORDER BY ts DESC LIMIT 1').fetchone()
    if not row or row['error'] or row['ac_power_w'] is None or not 0<=now-row['ts']<=max_age:return None
    return float(row['ac_power_w'])


def soc_rules(prefs):
    return {
        'high':int(prefs['soc_high_w']),'medium':int(prefs['soc_medium_w']),
        'low':int(prefs['soc_low_w']),'reserve':int(prefs['soc_reserve_w']),'critical':0,
    }


def soc_label(band,prefs):
    labels={'high':f'> {int(prefs["soc_high_threshold"])} %',
            'medium':f'{int(prefs["soc_medium_threshold"])+1}–{int(prefs["soc_high_threshold"])} %',
            'low':f'{int(prefs["soc_low_threshold"])+1}–{int(prefs["soc_medium_threshold"])} %',
            'reserve':f'{int(prefs["morning_min_soc"])+1}–{int(prefs["soc_low_threshold"])} %',
            'critical':f'≤ {int(prefs["morning_min_soc"])} %'}
    return labels.get(band,'unbekannt')


def update_soc_safety(state, soc, now, prefs):
    """Return the retained SOC cap. Upward transitions need 3 percentage points."""
    previous=state.get('soc_band')
    band=previous
    limits=soc_rules(prefs);floor=prefs['morning_min_soc'];low=prefs['soc_low_threshold'];medium=prefs['soc_medium_threshold'];high=prefs['soc_high_threshold']
    if soc is not None:
        if band not in limits:
            band='critical' if soc<=floor else 'reserve' if soc<=low else 'low' if soc<=medium else 'medium' if soc<=high else 'high'
        else:
            if soc<=floor:band='critical'
            else:
                if band=='high' and soc<=high:band='medium'
                if band=='medium' and soc<=medium:band='low'
                if band=='low' and soc<=low:band='reserve'
            # Rising transitions require three percentage points of hysteresis.
            if band=='critical' and soc>=floor+3:band='reserve'
            if band=='reserve' and soc>=low+3:band='low'
            if band=='low' and soc>=medium+3:band='medium'
            if band=='medium' and soc>=high+3:band='high'
        state.update(soc_value=soc,soc_band=band,soc_label=soc_label(band,prefs),soc_limit_w=limits[band],soc_checked_at=now,soc_stale=False)
    else:
        state['soc_stale']=True
    return state.get('soc_limit_w'), band!=previous


class Device:
    def __init__(self, config):
        self.config = config

    def read(self):
        from marstek import read_registers
        with socket.create_connection((self.config['host'], self.config['port']), timeout=3) as sock:
            sock.settimeout(3)
            limit = struct.unpack('>H',read_registers(sock,1,self.config['unit'],44003,1))[0]
            mode = struct.unpack('>H',read_registers(sock,2,self.config['unit'],43000,1))[0]
            control = struct.unpack('>H',read_registers(sock,3,self.config['unit'],42000,1))[0]
        if not 0 <= limit <= 2500:
            raise ValueError('Unplausible Entladegrenze')
        return limit, mode, control

    def write_limit(self, value):
        from marstek import receive
        if type(value) is not int or not 0 <= value <= 2500:
            raise ValueError('Ungültige Entladegrenze')
        self._write(44003, value)

    def set_self_consumption(self):
        self._write(43000, 1)

    def set_manual(self):
        self._write(43000, 0)

    def read_schedule(self, slot):
        from marstek import read_registers
        if slot not in range(1,7):raise ValueError('Ungültiger Zeitplanplatz')
        address=43100+(slot-1)*5
        with socket.create_connection((self.config['host'],self.config['port']),timeout=3) as sock:
            sock.settimeout(3)
            return struct.unpack('>HHHHH',read_registers(sock,10+slot,self.config['unit'],address,5))

    def write_schedule_six(self, days, start, end, power_w, enabled):
        if not 0<=days<=127 or not 0<=start<=2359 or not 0<=end<=2359 or not -2500<=power_w<=2500 or enabled not in (0,1):
            raise ValueError('Ungültiger Zeitplan')
        values=(days,start,end,power_w & 0xffff,enabled)
        self._write(43129,0)
        for address,value in zip(range(43125,43129),values[:4]):
            time.sleep(.05);self._write(address,value)
        time.sleep(.05);self._write(43129,enabled)
        if self.read_schedule(6)!=values:raise ValueError('Zeitplan nicht bestätigt')

    def disable_schedule_six(self):
        self._write(43129,0)
        if self.read_schedule(6)[4]!=0:raise ValueError('Zeitplan nicht deaktiviert')

    def clear_schedule_six(self):
        self.write_schedule_six(0,0,0,0,0)

    def _write(self, register, value):
        from marstek import receive
        schedule_register=43125<=register<=43129
        if register not in (44003,43000) and not schedule_register:
            raise ValueError('Nicht erlaubter Schreibzugriff')
        if register==43000 and value not in (0,1):raise ValueError('Nicht erlaubter Modus')
        packet = struct.pack('>HHHBBHH',4,0,6,self.config['unit'],6,register,value)
        with socket.create_connection((self.config['host'],self.config['port']),timeout=3) as sock:
            sock.settimeout(3); sock.sendall(packet)
            header = receive(sock,7)
            tid, proto, length, unit = struct.unpack('>HHHB',header)
            if (tid,proto,unit)!=(4,0,self.config['unit']) or not 2<=length<=254:
                raise ValueError('Ungültige Schreibantwort')
            if header+receive(sock,length-1) != packet:
                raise ValueError('Entladegrenze nicht bestätigt')


def step(path, device, now=None):
    now = time.time() if now is None else now
    state = control_status(path)
    prefs = read_preferences(path)
    charging = charging_status(path,now)
    soc=latest_soc(path,now)
    soc_limit,band_changed=update_soc_safety(state,soc,now,prefs)
    morning_limit,morning_changed=update_morning(path,state,prefs,charging,soc,latest_battery_power(path,now),now)
    try:
        current, mode, rs485 = device.read()
        observe(state,current,mode,rs485,now)
        if state['conflict']:
            state['message'] = 'Manuelle/externe Vorgabe aktiv · Automatik pausiert bis zur erneuten Freigabe.'
        elif mode != 1 or rs485 != 21947:
            state['message'] = 'Manuelle/externe Vorgabe aktiv · Automatik pausiert während dieser Betriebsart.'
        else:
            # Reconcile a possibly delivered command after disconnect or process restart.
            if state['pending'] is not None and current == state['pending']:
                state['applied'] = current
                state['pending'] = None
                state['message'] = confirmed_message(state,current)
                persist(path,state,now,'CONFIRMED',current)
            if state['baseline'] is not None and current != state['applied']:
                state['conflict'] = True
                state['message'] = 'Manuelle/externe Vorgabe aktiv · Automatik pausiert bis zur erneuten Freigabe.'
            else:
                active = bool(charging['state']['active']) if not charging['stale'] else None
                active_reason=charging['state'].get('reason')
                base=state['baseline'] if state['baseline'] is not None else current
                candidates=[base]
                if morning_limit is not None:candidates.append(morning_limit)
                hour=datetime.fromtimestamp(now,ZONE).hour
                in_night=hour>=prefs['night_start_hour'] or hour<prefs['morning_start_hour']
                profile_limit=(max(int(soc_limit),int(state['morning']['night_limit_w']))
                               if in_night and soc is not None and soc>prefs['morning_min_soc'] and soc_limit is not None
                               else int(soc_limit) if soc_limit is not None else None)
                if morning_limit is None and profile_limit is not None:candidates.append(profile_limit)
                reserve_binding=(morning_limit is None and prefs['morning_end_hour']<=hour<prefs['night_start_hour']
                                 and soc is not None and soc<=state['morning']['night_target_soc']
                                 and not state['morning']['forecast_good'])
                if reserve_binding:candidates.append(int(prefs['soc_reserve_w']))
                if active is True:candidates.append(int(prefs['ev_discharge_limit_w']))
                elif active is None and state['baseline'] is not None:candidates.append(current)
                target=min(candidates)
                morning_binding=morning_limit is not None and target==morning_limit and morning_limit<=base
                night_binding=in_night and morning_limit is None and profile_limit is not None and profile_limit>int(soc_limit or 0) and target==profile_limit
                soc_binding=morning_limit is None and profile_limit is not None and target==profile_limit and profile_limit<base and not reserve_binding and not night_binding
                active_binding=active is True and target==int(prefs['ev_discharge_limit_w']) and target<base
                state['effective_target_w']=target
                state['effective_reason']='soc_safety' if soc_binding else ('sustained_limit' if active_binding and active_reason=='sustained_discharge' else 'ev_limit' if active_binding else 'night_reserve' if reserve_binding else 'night_supply' if night_binding else 'morning' if morning_binding else 'normal')
                release=(target==base and active is False and not charging['stale'] and not soc_binding)
                if target == current:
                    if release and state['baseline'] is not None:
                        state['baseline'] = state['applied'] = None
                    state['pending'] = None
                    if charging['stale']:
                        state['message']='Autolade-Erkennung veraltet · keine Erhöhung; Grenze '+str(current)+' W'
                    elif soc_binding:
                        state['message']=f'SOC-Sicherheit {soc_label(state["soc_band"],prefs)} · Grenze {current} W'
                    elif reserve_binding:
                        state['message']=f'Nachtreserve bis {state["morning"]["night_target_soc"]:.1f} % · Grenze {current} W'
                    elif night_binding:
                        state['message']=f'Nachtversorgung für {state["morning"]["night_energy_kwh"]:.1f} kWh · Grenze {current} W'
                    elif morning_binding:
                        state['message']=f'Morgenkomfort aktiv · Grenze {current} W'
                    else:
                        state['message'] = (('Dauerlastschutz aktiv' if active_reason=='sustained_discharge' else 'Autoladen erkannt')+' · Grenze '+str(current)+' W') if active else 'Normalbetrieb · Grenze '+str(current)+' W'
                elif (state['last_attempt'] is not None and now-state['last_attempt'] < prefs['marstek_interval_seconds']
                      and not (target<current and (soc_binding or active_binding or reserve_binding))):
                    state['message'] = f'Warte auf Mindestabstand · Ziel {target} W'
                else:
                    if state['baseline'] is None:
                        state['baseline'] = state['applied'] = current
                    state['pending_reason'] = 'soc_limit' if soc_binding else (('sustained_limit' if active_reason=='sustained_discharge' else 'ev_limit') if active else 'night_reserve' if reserve_binding else 'night_supply' if night_binding else 'morning' if morning_binding else 'restore')
                    state['pending'] = target
                    state['last_attempt'] = now
                    state['message'] = f'Entladegrenze auf {target} W angefordert'
                    # Durable intent BEFORE the network write, even if the response is lost.
                    persist(path,state,now,'REQUEST',target)
                    device.write_limit(target)
                    confirmed, mode2, rs4852 = device.read()
                    if confirmed != target:
                        raise ValueError('Entladegrenze beim Zurücklesen abweichend')
                    state['applied'] = confirmed
                    state['observed_limit_w'] = confirmed
                    state['pending'] = None
                    if release and confirmed == state['baseline']:
                        state['baseline'] = state['applied'] = None
                    state['message'] = confirmed_message(state,confirmed)
                    observe(state,confirmed,mode2,rs4852,now)
                    persist(path,state,now,'CONFIRMED',confirmed)
    except (OSError, ValueError) as exc:
        state['message'] = f'Begrenzung nicht bestätigt: {type(exc).__name__}; erneute Prüfung folgt.'
        persist(path,state,now,'ERROR',state.get('pending'))
    if band_changed:
        state['message']=state.get('message','')
        persist(path,state,now,'SOC_BAND',state.get('soc_limit_w'))
    if morning_changed:
        m=state['morning'];actual_message=state.get('message','')
        state['message']=('Morgenkomfort gestartet · '+str(m.get('reason')) if morning_changed=='START' else 'Morgenkomfort beendet')
        persist(path,state,now,'MORNING_'+morning_changed,m.get('release_w'))
        state['message']=actual_message
    persist(path,state,now)
    return state
