"""Lokales Dashboard. Der separate collector.py erfasst die Messwerte."""
from datetime import date, datetime, time as daytime, timedelta
import time
import json
from collections import OrderedDict
from threading import Lock
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, render_template, request
from database import initialize, latest, recent_average, history, connect
from backup_status import initialize_backup
from flow_summary import flow_summary
from finance_history import history as finance_history
from balance import estimate, charging_periods
from system_status import SystemStatus
from preferences import initialize_preferences, read_preferences, save_preferences, save_ev_discharge_limit
from fan import initialize_fan, status as fan_status, request_action
from weather import (initialize_weather, weather_status, weather_history,
                     sevilla_weather_history, SEVILLA_LATITUDE, SEVILLA_LONGITUDE)
from sun_times import sun_times
from marstek import initialize_marstek, status as marstek_status
from marstek_actions import request_mode
from marstek_display import decision_log
from optimizer import initialize_optimizer, plan_status
from grid_charging import initialize_grid_charging, manual_plan as grid_charge_preview, request_status as grid_charge_status, request as request_grid_charge, cancel as cancel_grid_charge
from settings import load_settings
from solaredge import initialize_solar, solar_status
from energy import initialize_energy
from tibber import initialize_tibber, price_status
from charging import initialize_charging, charging_status
from forecast import initialize_forecast, forecast_status, plant

ZONE = ZoneInfo('Europe/Berlin')

def day_bounds(day):
    start = datetime.combine(day, daytime.min, ZONE)
    end = datetime.combine(day + timedelta(days=1), daytime.min, ZONE)
    return start.timestamp(), end.timestamp()

def create_app(config=None):
    config = config or load_settings()
    path = config['database_path']
    initialize_solar(path)
    initialize_energy(path)
    initialize_forecast(path)
    initialize_tibber(path)
    initialize_charging(path)
    initialize_backup(path)
    initialize_preferences(path)
    initialize_fan(path)
    initialize_weather(path)
    initialize_marstek(path)
    initialize_optimizer(path)
    initialize_grid_charging(path)
    app = Flask(__name__)
    info = json.loads(Path(__file__).with_name('project_info.json').read_text(encoding='utf-8'))

    system = SystemStatus(path, info['version'])
    # Bounded, short-lived cache of completed days; live values remain uncached.
    past_days = OrderedDict()
    past_days_lock = Lock()
    finance_days = OrderedDict()
    finance_days_lock = Lock()

    def day_measurements(day, start, end):
        with past_days_lock:
            cached = past_days.get(day)
            if cached and time.monotonic() - cached[0] < 60:
                past_days.move_to_end(day)
                return cached[1]
            value = (history(path, start, end, 60, max(15, config['shelly']['poll_seconds'] * 3)),
                     estimate(path, start, end))
            past_days[day] = (time.monotonic(), value)
            past_days.move_to_end(day)
            while len(past_days) > 8:
                past_days.popitem(last=False)
            return value

    @app.route('/api/preferences', methods=['GET','POST'])
    def preferences():
        if request.method == 'POST':
            # JSON + custom header prevent cross-origin form submissions; no CORS enabled.
            if not request.is_json or request.headers.get('X-EnergyPi') != 'settings':
                return jsonify(error='Ungültige Anfrage'),403
            try:
                save_preferences(path,request.get_json(),config['shelly']['poll_seconds'])
            except ValueError as error:
                return jsonify(error=str(error)),400
        return jsonify(values=read_preferences(path))

    @app.route('/api/fan', methods=['GET','POST'])
    def fan_endpoint():
        if request.method == 'POST':
            if not request.is_json or request.headers.get('X-EnergyPi')!='settings':
                return jsonify(error='Ungültige Anfrage'),403
            body=request.get_json()
            try:
                request_action(path,body.get('action') if isinstance(body,dict) else None)
            except ValueError as error:
                return jsonify(error=str(error)),400
        return jsonify(fan_status(path))

    @app.post('/api/marstek/self-consumption')
    def set_self_consumption():
        if not request.is_json or request.headers.get('X-EnergyPi') != 'settings':
            return jsonify(error='Ungültige Anfrage'),403
        return jsonify(action=request_mode(path)),202

    @app.post('/api/marstek/discharge-target')
    def set_discharge_target():
        if not request.is_json or request.headers.get('X-EnergyPi') != 'settings':
            return jsonify(error='Ungültige Anfrage'),403
        body=request.get_json()
        value=body.get('value_w') if isinstance(body,dict) else None
        previous=read_preferences(path)['ev_discharge_limit_w']
        try:
            saved=save_ev_discharge_limit(path,value,config['shelly']['poll_seconds'])
        except ValueError as error:
            return jsonify(error=str(error)),400
        if saved!=previous:
            detail=f'Autolade-Ziel von {previous:g} W auf {saved:g} W geändert'
            with connect(path) as db:
                db.execute('INSERT INTO marstek_control_events(ts,event,value_w,detail) VALUES (?,?,?,?)',
                           (time.time(),'TARGET_CHANGED',saved,detail))
        return jsonify(value_w=saved)

    @app.get('/api/observation-plan')
    def observation_plan():
        return jsonify(plan_status(path))

    @app.route('/api/grid-charge',methods=['GET','POST'])
    def grid_charge():
        if request.method=='POST':
            if not request.is_json or request.headers.get('X-EnergyPi')!='settings':return jsonify(error='Ungültige Anfrage'),403
            try:request_grid_charge(path,request.get_json())
            except ValueError as error:return jsonify(error=str(error)),409
        return jsonify(grid_charge_status(path))

    @app.post('/api/grid-charge/preview')
    def grid_charge_preview_api():
        if not request.is_json or request.headers.get('X-EnergyPi')!='settings':return jsonify(error='Ungültige Anfrage'),403
        try:return jsonify(grid_charge_preview(path,request.get_json()))
        except (TypeError,ValueError) as error:return jsonify(error=str(error)),400

    @app.post('/api/grid-charge/cancel')
    def grid_charge_cancel():
        if not request.is_json or request.headers.get('X-EnergyPi')!='settings':return jsonify(error='Ungültige Anfrage'),403
        try:return jsonify(cancel_grid_charge(path))
        except ValueError as error:return jsonify(error=str(error)),409

    @app.get('/api/marstek/decisions')
    def get_marstek_decisions():
        return jsonify(entries=decision_log(path))

    @app.get('/api/marstek')
    def get_marstek():
        result=marstek_status(path)
        result['discharge_target_w']=read_preferences(path)['ev_discharge_limit_w']
        return jsonify(result)

    @app.get('/api/weather/history')
    def get_weather_history():
        try:
            day=date.fromisoformat(request.args.get('date',datetime.now(ZONE).date().isoformat()))
            start,end=day_bounds(day)
        except (ValueError,OverflowError):
            return jsonify(error='Ungültiges Datum'),400
        sevilla=sevilla_weather_history(path,start,end)
        sevilla.update(sun_times(day,SEVILLA_LATITUDE,SEVILLA_LONGITUDE))
        site=plant()
        return jsonify(day=day.isoformat(),site_name=site['name'],**weather_history(path,start,end),
                       sevilla=sevilla,**sun_times(day,site['latitude'],site['longitude']))

    @app.get('/api/weather')
    def get_weather():
        return jsonify(weather_status(path))

    @app.get('/api/finance/history')
    def get_finance_history():
        try:
            days=int(request.args.get('days','7'))
            requested=date.fromisoformat(request.args['week']) if request.args.get('week') else datetime.now(ZONE).date()
            week_start=requested-timedelta(days=requested.weekday())
        except (TypeError,ValueError):
            return jsonify(error='Ungültige Tageszahl oder Kalenderwoche'),400
        if not 2<=days<=31:return jsonify(error='Tageszahl muss zwischen 2 und 31 liegen'),400
        with finance_days_lock:
            result=finance_history(path,time.time(),read_preferences(path)['feed_in_ct'],days,finance_days,week_start)
            while len(finance_days)>31:finance_days.popitem(last=False)
        return jsonify(result)

    @app.get('/api/system')
    def get_system():
        return jsonify(system.read())

    @app.after_request
    def no_cache(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def index():
        return render_template('design_preview.html', version=info['version'])

    @app.get('/design_alt')
    def legacy_design():
        return render_template('index.html', version=info['version'])

    @app.get('/design-preview')
    def design_preview():
        return render_template('design_preview.html', version=info['version'])

    @app.get('/energiefluss-preview')
    def energy_flow_preview():
        return render_template('energy_flow_preview.html', version=info['version'])

    @app.get('/dokumentation')
    def documentation():
        return render_template('documentation.html', info=info)

    @app.get('/api/status')
    def status():
        sample, attempt = latest(path)
        now = time.time()
        age = now - sample['ts'] if sample else None
        average_15m = recent_average(path, now, 15 * 60, max(15, config['shelly']['poll_seconds'] * 3))
        return jsonify(sample=sample, attempt=attempt, average_15m=average_15m, age_seconds=age,
                       stale=age is None or age < 0 or age > 20 or bool(attempt and attempt['error']),
                       today=datetime.now(ZONE).date().isoformat())

    @app.get('/api/solaredge')
    def get_solar():
        return jsonify(solar_status(path))

    @app.get('/api/forecast')
    def get_forecast():
        try:
            day=date.fromisoformat(request.args.get('date',datetime.now(ZONE).date().isoformat()))
            return jsonify(forecast_status(path,day.isoformat()))
        except (ValueError,OverflowError):
            return jsonify(error='Ungültiges Datum'),400

    @app.get('/api/tibber')
    def get_tibber():
        try:
            day=date.fromisoformat(request.args.get('date',datetime.now(ZONE).date().isoformat()))
            return jsonify(price_status(path,day))
        except (ValueError,OverflowError):
            return jsonify(error='Ungültiges Datum'),400

    @app.get('/api/charging')
    def get_charging():
        return jsonify(charging_status(path))

    @app.get('/api/history')
    def get_history():
        mode = request.args.get('mode', 'day')
        if mode not in ('day', 'hour'):
            return jsonify(error='Ungültige Ansicht'), 400
        try:
            day = date.fromisoformat(request.args.get('date', datetime.now(ZONE).date().isoformat()))
            start, end = day_bounds(day)
        except (ValueError, OverflowError):
            return jsonify(error='Ungültiges Datum'), 400
        if mode == 'hour':
            end = time.time()
            start = end - 3600
        balance_start, balance_end = day_bounds(day)
        balance_end = max(balance_start, min(balance_end, time.time()))
        if mode == 'day' and day < datetime.now(ZONE).date():
            segments, daily_balance = day_measurements(day, start, end)
        else:
            segments = history(path, start, end, 0 if mode == 'hour' else 60,
                               max(15, config['shelly']['poll_seconds'] * 3))
            daily_balance = estimate(path, balance_start, balance_end)
        return jsonify(start=start, end=end, segments=segments, mode=mode,
                       flows=flow_summary(path,day.isoformat(),daily_balance,time.time(),read_preferences(path)['feed_in_ct']),
                       balance=daily_balance,
                       balance_day=day.isoformat(),
                       charging_periods=charging_periods(path,start,min(end,time.time()),segments))
    return app

if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=8080, debug=False)
