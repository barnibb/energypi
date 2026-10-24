# SolarEdge-Istwerte ergänzen

## Update auf den Pi

Im Mac-Terminal:

```sh
cd /PFAD/ZU/marstek-control
bash update-solaredge.sh
```

Das Update ergänzt die Dateien und den SolarEdge-Timer. Bestehende secrets.toml,
config.toml und Messdaten werden nicht übertragen oder überschrieben.

## Zugangsdaten separat eingeben

```sh
ssh pi@RASPBERRY_PI_IP
cd ~/marstek-control
nano secrets.toml
```

Inhalt (beide Werte in Anführungszeichen):

```toml
[solaredge]
site_id = "DEINE_STANDORT_ID"
api_key = "DEIN_API_SCHLUESSEL"
```

Speichern in nano: Ctrl+O, Enter; schließen: Ctrl+X.

```sh
chmod 600 secrets.toml
sudo systemctl start marstek-solaredge.service
journalctl -u marstek-solaredge.service -n 10 --no-pager
```

Die Datei wird bei jeder Abfrage neu gelesen; kein Dienstneustart für die
Zugangsdaten nötig. Niemals Schlüssel im Chat oder Terminalbefehl einfügen.
Zum lokalen Mac-Test secrets.example.toml nach secrets.toml kopieren, Werte
im Editor eintragen, chmod 600 anwenden und `.venv/bin/python solaredge.py`
starten. Schlüsseldatei ist von Git und Standarddeployment ausgeschlossen.

## Verhalten

- HTTPS-URL: https://monitoringapi.solaredge.com/site/{site_id}/currentPowerFlow.json
- API-Key als Queryparameter, keine URL oder Rohantwort im Log.
- 07:30 bis vor 21:00 Uhr, Europe/Berlin, pro Viertelstundenfenster höchstens
  eine Abfrage. Das sind maximal 54 Requests pro vollständigem Tag und Installation.
- Kein Cloud-Aufruf beim Öffnen/Aktualisieren der Webseite.
- Fehler werden erst im nächsten Zeitfenster erneut versucht. Fehlende Zugangsdaten
  führen zu keiner Anfrage. Gleichzeitige Starts reservieren ihren Slot atomar.
- Bestehende andere Programme mit demselben API-Zugang zählen zusätzlich; nach dem
  Umstieg die alte SolarEdge-Abfrageschleife beenden, falls sie noch läuft.
- Timeout 15 Sekunden, unabhängig von der Shelly-Erfassung.
- Außerhalb des Fensters Nachtpause, keine erfundenen Nullwerte.
- Ein Abruf liefert keinen bestätigten Zeitpunkt der tatsächlichen Cloud-Messung.
  Deshalb zeigt das Dashboard ausdrücklich den Abrufzeitpunkt; Daten können älter sein.

SQLite-Tabelle solaredge_samples in derselben measurements.db enthält UTC-Abrufzeit,
PV-Leistung, optional Last und vorzeichenbehafteten Netzfluss in Watt sowie bereinigte
Fehler. Netzrichtung wird aus connections bestimmt; ohne eindeutige Richtung bleibt
sie unbekannt. Kein Schlüssel und keine Standort-ID werden in SQLite gespeichert.
Die SQLite-Sicherungen enthalten diese Tabelle automatisch. SolarEdge-Werte werden
bei dieser geringen Frequenz dauerhaft aufbewahrt (maximal 19.710 Zeilen/Jahr).

Die Oberfläche zeigt zunächst die zuletzt abgerufene PV-Leistung und Status. LOAD
und GRID werden gespeichert, aber noch nicht zusätzlich im Dashboard angezeigt.
Der Shelly bleibt Quelle der aktuellen Netzleistung. SolarEdge wird nicht mit
zeitlich abweichenden Shelly-Werten zu einem vermeintlich exakten Hausverbrauch
verrechnet. Historische PV-Kurven und Tagesenergie sind noch nicht umgesetzt.

Dies ist eine Istwertabfrage, keine Forecast-API. Sie kann später beim Vergleich
mit einer separat einzurichtenden Prognose helfen. Für genaue Tageserträge sollte
zusätzlich die SolarEdge-Energie-API genutzt werden, statt aus seltenen
Momentanleistungswerten eine exakte Tagesenergie abzuleiten.

Quelle zum Antwortformat:
https://knowledge-center.solaredge.com/sites/kc/files/se_monitoring_api.pdf

## Kontrolle

```sh
systemctl list-timers marstek-solaredge.timer --no-pager
journalctl -u marstek-solaredge.service -n 20 --no-pager
```

Bei HTTP 401/403 Zugangsdaten und Freigabe prüfen, bei 429 das gemeinsame
Abfragebudget anderer Programme prüfen. Live-Verifikation erst nach Eintragen
der persönlichen Zugangsdaten möglich.
