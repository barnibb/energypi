"""Meross-Cloud-Anbindung. Kein verifizierter geräteinterner Timer verfügbar."""
import asyncio
import fcntl
import logging
import os
import time
import tomllib
from pathlib import Path
from settings import ROOT, load_settings
from preferences import initialize_preferences
from fan import initialize_fan, state, select_device, expire, observe, acknowledge, failure


async def reconcile(path,device):
    expire(path,time.time())
    s=state(path)
    await asyncio.wait_for(device.async_update(),20)
    # Während einer Netzwerkabfrage können neue Anforderungen eintreffen.
    expire(path,time.time())
    s=state(path)
    on=device.is_on(channel=0)
    if not isinstance(on,bool):raise RuntimeError('Schaltzustand unbekannt')
    if s['desired'] is not None and on!=bool(s['desired']):
        command=device.async_turn_on if s['desired'] else device.async_turn_off
        await asyncio.wait_for(command(channel=0),20)
        await asyncio.wait_for(device.async_update(),20)
        on=device.is_on(channel=0)
        if not isinstance(on,bool):raise RuntimeError('Schaltzustand unbekannt')
        if on!=bool(s['desired']):raise RuntimeError('Schaltzustand nicht bestätigt')
    observe(path,on,time.time())
    if not on:acknowledge(path,s['revision'])


class FanDiagnosticError(Exception):
    pass


def safe_error(stage,error):
    # Never expose str(error), args, URLs, account identifiers or tokens.
    name=type(error).__name__
    known={'TimeoutError','ValueError','RuntimeError','TypeError','AttributeError',
           'FileNotFoundError','PermissionError','TOMLDecodeError','ModuleNotFoundError',
           'ClientConnectorDNSError','MissingMFA','WrongMFA','BadDomainException',
           'UnauthorizedException','HttpApiError','CommandTimeoutError','ClientConnectorError',
           'TooManyTokensException','BadLoginException','MFARequiredException'}
    return f'{stage}: {name if name in known else "Bibliotheks-/Verbindungsfehler"}'


async def session(path):
    stage=['Bibliothek laden']
    try:
        await session_impl(path,stage)
    except Exception as error:
        raise FanDiagnosticError(safe_error(stage[0],error)) from None


async def session_impl(path,stage):
    from meross_iot.http_api import MerossHttpClient
    from meross_iot.manager import MerossManager
    from meross_dns import configure_meross_dns
    configure_meross_dns()
    stage[0]='Konfiguration lesen'
    secret=Path(os.environ.get('MARSTEK_SECRETS',ROOT/'secrets.toml'))
    with secret.open('rb') as f:config=tomllib.load(f).get('meross',{})
    if not config.get('email') or not config.get('password') or config['password']=='HIER_EINTRAGEN':
        raise ValueError('Zugangsdaten fehlen')
    client=None;manager=None
    stage[0]='Meross-Anmeldung (EU)'
    try:
        client=await asyncio.wait_for(MerossHttpClient.async_from_user_password(
            api_base_url='https://iotx-eu.meross.com',email=config['email'],password=config['password']),30)
        stage[0]='MQTT-Verbindung starten'
        manager=MerossManager(http_client=client)
        await asyncio.wait_for(manager.async_init(),30)
        stage[0]='Geräteliste abrufen'
        await asyncio.wait_for(manager.async_device_discovery(),30)
        stage[0]='Geräteauswahl'
        devices=manager.find_devices(device_type='mss210')
        saved=state(path)['uuid']
        matches=[d for d in devices if (d.uuid==saved if saved else d.name=='Lüfter Bad')]
        print(f'Meross-Diagnose: MSS210-Geräte={len(devices)}, passende Treffer={len(matches)}, Gerätebindung={bool(saved)}',flush=True)
        device=select_device(path,devices)
        stage[0]='Gerätestatus abfragen / Schaltung bestätigen'
        last_revision=None;next_poll=0
        while True:
            expire(path,time.time())
            revision=state(path)['revision']
            if revision!=last_revision or time.monotonic()>=next_poll:
                try:
                    await reconcile(path,device)
                    last_revision=revision
                    next_poll=time.monotonic()+30
                except Exception:
                    failure(path,'Meross nicht erreichbar oder Schaltung nicht bestätigt; erneuter Versuch folgt.')
                    # Keine neuen Einschaltanforderungen bei veralteten Daten.
                    await asyncio.sleep(15)
                    raise
            await asyncio.sleep(2)
    finally:
        if manager:
            try:manager.close()
            except Exception:pass
        if client:
            try:await asyncio.wait_for(client.async_logout(),10)
            except Exception:pass


async def run(path):
    while True:
        try:await session(path)
        except Exception as error:
            message=str(error) if isinstance(error,FanDiagnosticError) else safe_error('Lüfterdienst',error)
            failure(path,message)
            print(message+'; neuer Verbindungsversuch in 60 Sekunden.',flush=True)
            await asyncio.sleep(60)


def main():
    path=load_settings()['database_path']
    initialize_preferences(path);initialize_fan(path)
    # Bibliothekslogs nicht mit Kontodaten in systemd übernehmen.
    logging.disable(logging.CRITICAL)
    with open(str(path)+'.fan.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        asyncio.run(run(path))

if __name__=='__main__':main()
