# EnergyPi - Monitor

Stand: Version 1.49.1, 24.10.2026. EnergyPi ist eine lokale Python-Anwendung für den Raspberry Pi mit SQLite und Browseroberfläche. Sie erfasst Netzwerte über einen Shelly Pro 3EM, liest und steuert einen Marstek Venus E V2 und ergänzt SolarEdge-, Forecast.Solar-, Tibber- und Wetterdaten. Ein Meross-Zwischenstecker kann den Badlüfter mit einstellbarer Abschaltfrist steuern. Messwerterfassung, Schutzlogik und zeitgesteuerte Dienste laufen unabhängig vom geöffneten Browser.

## Einstieg

- Dashboard im Heimnetz: http://RASPBERRY_PI_IP:8080
- Version im Dashboard anklicken: Bedienhinweise, Parameter und Versionsverlauf.
- Mac-Projekt: `/PFAD/ZU/marstek-control`
- Pi-Projekt: `/home/pi/marstek-control`
- Python mindestens 3.11; auf dem Pi eigene `.venv`, niemals die Mac-Umgebung kopieren.

## Lokale Konfiguration

Geräteadressen, das SSH-Ziel und Zugangsdaten werden nicht veröffentlicht. Nach dem
Klonen werden die mitgelieferten Beispiele einmal kopiert und lokal angepasst:

```sh
cp config.example.toml config.toml
cp marstek.example.toml marstek.toml
cp forecast.example.toml forecast.toml
cp deploy-local.example.env deploy-local.env
cp secrets.example.toml secrets.toml
```

`config.toml`, `marstek.toml`, `forecast.toml`, `deploy-local.env`, `secrets.toml` und `data/` sind
durch `.gitignore` geschützt. `deploy-common.sh` beendet Update- und
Installationsskripte mit einer verständlichen Meldung, falls `deploy-local.env` fehlt.
Die neutrale `forecast.example.toml` dokumentiert die benötigten Angaben. Der tatsächliche Standort und die PV-Anlagendaten werden ausschließlich in der ignorierten lokalen `forecast.toml` eingetragen.

## Dokumentation

| Anleitung | Inhalt |
|---|---|
| [WETTER_RADIO.md](WETTER_RADIO.md) | Anlagenstandort-Temperatur sowie NDR Info und NDR 2 |
| [BETRIEB.md](BETRIEB.md) | Anlagenübersicht, Dienste, Fehlersuche, Updates und Wiederherstellung |
| [PARAMETER.md](PARAMETER.md) | Alle neun Dashboard-Parameter, Grenzen und Wirkung |
| [TECHNIK.md](TECHNIK.md) | Module, Datenbank, API und Tests |
| [DASHBOARD.md](DASHBOARD.md) | Anzeigen, Diagramme, Energiebilanz und lokale Vorschau |
| [AUTOLADEN.md](AUTOLADEN.md) | Erkennungslogik und Grenzen |
| [AUFBEWAHRUNG.md](AUFBEWAHRUNG.md) | Verdichtung, Sicherungen und Speicherbedarf |
| [SOLAREDGE.md](SOLAREDGE.md), [PROGNOSE.md](PROGNOSE.md), [TIBBER.md](TIBBER.md) | Cloud-Datenquellen und Einrichtung |
| [MEROSS.md](MEROSS.md) | Lüftertimer, Wiederanlauf und DNS-Diagnose |

Zugangsdaten stehen auf dem Pi in `secrets.toml`, nicht in dieser Dokumentation. Datenbanksicherungen enthalten keine Zugangsdaten dieser Datei und keinen Programmcode. Beides muss für einen SD-Karten-Ausfall separat verfügbar sein.

## Entwicklung und Prüfung am Mac

```sh
cd /PFAD/ZU/marstek-control
source .venv/bin/activate
python -m unittest discover -s tests -q
python webapp.py
```

Vorschau: http://127.0.0.1:8080. Sie verwendet die lokale Datenbank, nicht automatisch die Pi-Datenbank. Bei Bedarf `python collector.py` in einem zweiten Terminal starten. Cloud- und Lüfterdienste laufen dadurch nicht automatisch am Mac.

## Alter Testmonitor

`main.py` ist der frühere reine Beobachtungsmonitor, kein Teil des Pi-Dashboard-Dauerbetriebs. Er liest `[high_load]` aus `config.toml` (derzeit 3000/2000 W), während der produktive Collector die Dashboard-Einstellungen aus SQLite nutzt (Vorgaben 2000/1000 W). `python main.py --once` liest einmal; `python main.py` läuft bis Ctrl+C. Beide senden keine Marstek-Befehle.

## Pflege

Bei Änderungen Version, Datum und Verlauf in `project_info.json` sowie betroffene Anleitungen pflegen. Vorherigen Code und geprüfte Datenbanksicherung behalten; eine ältere Programmversion ist nach Schemaänderungen nicht automatisch kompatibel.


## Marstek-Beobachtung (1.10.0)

Siehe [MARSTEK.md](MARSTEK.md): eigener Dienst `marstek-battery`, 30-Sekunden-Abfragen, Tabelle `marstek_samples`, lokaler Endpunkt `/api/marstek`. Ab 1.11.0 zusätzlich konfigurierbare Autolade-Entladegrenze (200 W), mit Wiederherstellung und Mindestabstand; siehe MARSTEK.md. Bei Wiederherstellung der Datenbank diesen zusätzlichen Schreiber ebenfalls stoppen. Installation vom Mac: `bash update-marstek.sh` (auf bestehender Version 1.9.0).


## Akku-Verlauf und Energieanteile (1.12.0)

`battery_history.py` liest die vorhandenen 30-Sekunden-Messungen in `marstek_samples`. `forecast_status` liefert zusätzlich `battery.segments` für die violette Ladestandskurve auf der rechten 0–100-%-Achse. Keine zusätzlichen Geräte- oder Cloud-Abfragen. Daten bleiben in SQLite und den Sicherungen erhalten. Messfehler und Abstände über 90 Sekunden unterbrechen die Linie und Energieintegration. Keine erfundenen historischen oder zukünftigen Werte.

Die Quellen sind PV + Netzbezug + Akku-Abgabe; Ziele sind berechneter Hausverbrauch + Einspeisung + Akku-Ladung. Positive/negative AC-Leistung wird getrennt trapezförmig mit linearem Nulldurchgang integriert. Keine doppelte Zuordnung als direkter PV-Verbrauch, kein Autarkiegrad. Akku-Ladung und spätere Abgabe tauchen als verschiedene Flüsse auf.

Heute richtet sich der gemeinsame Bilanzzeitraum nach dem Abruf des SolarEdge-Tagesertrags; dessen Cloud-Zeitversatz bleibt als Unsicherheit. Während des PV-Tages gilt der Wert nach zwei Stunden als veraltet. Nach dem lokalen Sonnenuntergang bleibt ein höchstens 30 Minuten vor Sonnenuntergang abgerufener Tageswert bis Mitternacht gültig. Die Bilanz endet weiterhin am tatsächlichen SolarEdge-Abrufzeitpunkt und ergänzt keine geschätzte Energie. Unter 95 % Netz- oder Akku-Abdeckung bleiben die Ringe grau und bekannte Akku-kWh sind ausdrücklich nur Teilmengen. Auch negative berechnete Hausenergie verhindert eine Aufteilung. Tage vor Beginn der Akku-Erfassung werden nicht nachträglich vervollständigt.

Installation auf dem bisherigen Projekt: `bash update-energy-flows.sh`.

Seit 1.24.0 stehen darunter zwei Geldringe. Netzbezug wird abschnittsweise mit
dem gespeicherten Tibber-Viertelstundenpreis bewertet. Der zweite Ring zeigt
Einspeiseerlös, geschätzten PV-Eigenverbrauchsvorteil und den Bruttowert der
Akku-Abgabe. Akkuladekosten, Verluste und Verschleiß lassen sich ohne sichere
Herkunftszuordnung nicht abziehen und werden deshalb nicht als Nettogewinn
ausgegeben. Fehlende Preis- oder Energiedaten bleiben sichtbar.

Ab 1.24.1 erklärt ein kurzer Satz die Beträge als Netzstromkosten, rechnerische
Ersparnis und zusätzliche Einspeisevergütung. Historische Tage werden mit Datum
bezeichnet; unvollständige Zeiträume erhalten keinen geschätzten Gesamttext.

Version 1.25.0 zeigt zusätzlich den gewichteten tatsächlichen Bezugspreis und
den effektiven Haushaltsstrompreis nach Einspeisevergütung. Die Grundgebühr sowie
Investitions-, Lade-, Verlust- und Verschleißkosten sind darin nicht enthalten.

Seit 1.30.0 öffnet „7 Tage“ am Nutzen-Ring einen lokalen Balkenvergleich des
effektiven Haushaltsstrompreises für eine Kalenderwoche von Montag bis Sonntag.
Vorherige, aktuelle und folgende Woche sind direkt wählbar. Wochentage, heutiger
Teilwert, negative Preise und Datenlücken sind unterscheidbar. Das Öffnen erzeugt keine Cloud-Abfrage.
Ab 1.27.1 hat die y-Achse feste 5-ct-Schritte und eine deutlich hervorgehobene
Nulllinie; mindestens −5 bis +5 ct/kWh bleiben immer sichtbar.
