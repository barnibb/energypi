# EnergyPi-Dashboard

Lokale Beobachtungsanwendung mit SQLite, ohne Marstek-Steuerung.
Python 3.11 oder neuer. Die Diagramme werden lokal mit Canvas gezeichnet;
keine CDN-Abhängigkeiten oder externen Schriften für die Diagramme. Hintergrunddienste ergänzen Cloud-Daten; Windy lädt erst beim Öffnen.

## 15-Minuten-Durchschnitt am Netzanschluss

Die Kachel „Aktuell · Netzbezug“ zeigt zusätzlich den zeitgewichteten Netto-Durchschnitt der letzten 15 Minuten. Positive Werte werden als durchschnittlicher Netzbezug rot, negative Werte als durchschnittliche Einspeisung grün dargestellt. Bezug und Einspeisung innerhalb des Zeitfensters verrechnen sich miteinander.

Messlücken werden nicht als 0 W gerechnet. Ein Zahlenwert erscheint erst ab 80 Prozent Datenabdeckung; andernfalls steht dort „Ø noch nicht genügend Messwerte“. Die Beschriftung „Zeitlich gemittelter Nettowert“ unterscheidet den Durchschnitt deutlich vom großen aktuellen Messwert.

## Auf dem Mac starten

Im ersten Terminal:

```sh
cd /PFAD/ZU/marstek-control
source .venv/bin/activate
python -m pip install -r requirements.txt
python collector.py
```

Im zweiten Terminal:

```sh
cd /PFAD/ZU/marstek-control
source .venv/bin/activate
python webapp.py
```

Browser: http://127.0.0.1:8080. Beide Prozesse lassen sich mit Ctrl+C beenden.
Der Sammler benötigt für die Speicherung keinen geöffneten Browser.
Der Mac muss eingeschaltet und wach bleiben. Im eingerichteten Betrieb übernimmt der Pi diese Aufgaben.
Falls Port 8080 bereits verwendet wird, zuerst die vorhandene Vorschau beenden.

## Was angezeigt wird

- Gesamtwirkleistung und Leistungen, Spannungen und Ströme der drei Phasen.
- Gesamtwert als Betrag mit Bezug/Einspeisung; Phasen und Kurven mit Vorzeichen.
- Datumsauswahl, Heute/Gestern, Tagesansicht oder letzte rollende Stunde.
- Tagesansicht: Minutenmittel plus schattiertes Minimum/Maximum; Stunde: Rohwerte.
- Kurven lassen sich einzeln einschalten. Maus oder Berührung zeigt Einzelwerte.
- Anzeige wird alle fünf Sekunden abgefragt. Veraltete Messungen (>20 Sekunden)
  und zuletzt fehlgeschlagene Abfragen erhalten einen Hinweis.
- Messfehler und Lücken über 15 Sekunden trennen Kurven auch innerhalb einer Minute.
- Alle Anzeigezeiten Europe/Berlin; Speicherung als UTC Unix-Zeit.

Am Netzanschluss misst der Shelly den Netzfluss, nicht den vollständigen Hausverbrauch.
Messrichtung muss physisch korrekt sein. Es wird der Empfangszeitpunkt gespeichert:
ein intern eingefrorener Shelly-Messwert lässt sich damit nicht erkennen.
Ein vollständiger Tagesverlauf entsteht erst durch die entsprechende Sammeldauer.
Heute werden Tagesenergien geschätzt und der Meross-Lüfter geschaltet; Marstek bleibt ohne Steuerung.

## Dateien und Konfiguration

`config.toml`: Shelly-IP, Poll-Intervall, Timeout und Datenbankpfad.
`MARSTEK_CONFIG=/absoluter/pfad/config.toml` wählt für Sammler und Webserver
alternativ eine gemeinsame Konfiguration. Der Sammler versteht auch `--config`.
Relative Datenbankpfade beziehen sich immer auf den Ordner der TOML-Datei.
`data/measurements.db` enthält reale Messungen; Testdatenbanken sind temporär.
Ein separater Fehlerdatensatz markiert gescheiterte Abfragen; keine Nullwerte.
Eine Prozesssperre verhindert doppelte Sammler auf derselben Datenbank.
Keine Zugangsdaten-Unterstützung für einen passwortgeschützten Shelly in dieser Version.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Prüft bisherige Hochlastlogik, ungültige Werte, veraltete Daten,
Fehler-/Zeitlücken, Aggregation und 23-/25-Stunden-Tage bei Zeitumstellung.

## Dauerbetrieb auf dem Pi

Die Anlage ist auf dem Pi eingerichtet. Für eine Neuinstallation gelten folgende Hinweise.
Für Übertragungen `.venv/`, `.git/`, `__pycache__/` und `data/` ausschließen;
keine lokale Testdatenbank über die spätere Pi-Datenbank kopieren.
Zielordner für die neue Installation: `/home/pi/marstek-control`.
Virtuelle Umgebung auf dem Pi neu erstellen und requirements.txt installieren.
Dauerbetrieb-Webserver beispielsweise:

```sh
.venv/bin/gunicorn --workers 1 --threads 2 --bind 0.0.0.0:8080 'webapp:create_app()'
```

Nur für das vertrauenswürdige Heimnetz; ohne Anmeldung, keine Router-Portfreigabe.
Der Sammler bleibt ein eigener Dienst. Der Flask-Entwicklungsserver ist nur
für die lokale Vorschau gedacht (siehe Flask-Dokumentation).

## Datensicherung und Aufbewahrung

Das Update mit 30 Tagen Rohdaten, Minutenarchiv und täglichen Sicherungen
ist in [AUFBEWAHRUNG.md](AUFBEWAHRUNG.md) beschrieben. Es muss zusätzlich
zur Erstinstallation eingespielt werden.

## Vorbereitete Erstinstallation auf dem Pi

Im Mac-Terminal ausführen:

```sh
cd /PFAD/ZU/marstek-control
bash deploy-to-pi.sh
```

SSH- und gegebenenfalls sudo-Passwort direkt im Terminal eingeben.
Das Skript installiert python3-venv und Python-Abhängigkeiten, führt Tests aus,
richtet zwei systemd-Dienste ein und prüft aktuelle Shelly-Daten über HTTP.
Lokale Messdaten werden nicht übertragen; bestehende Pi-Messdaten bleiben erhalten.
Die Projektdateien einschließlich config.toml werden übertragen. Vor späteren
Updates gegebenenfalls direkt auf dem Pi vorgenommene Konfigurationsänderungen
zurück auf den Mac übernehmen. Dienstdefinitionen werden vor Ersatz gesichert.

Danach: http://RASPBERRY_PI_IP:8080 im Heimnetz öffnen.
Der Mac darf dann ausgeschaltet sein. In der FRITZ!Box die IP des Pi reservieren.

Kontrolle auf dem Pi:

```sh
systemctl status marstek-collector marstek-web --no-pager
journalctl -u marstek-collector -u marstek-web -n 50 --no-pager
```

Stoppen und Autostart deaktivieren (Messdaten bleiben erhalten):

```sh
sudo systemctl disable --now marstek-collector marstek-web
```

Der Pi-Dauerbetrieb wurde in der Einrichtung bestätigt; diese Anleitung ersetzt keine aktuelle Live-Prüfung. Datensicherung und Aufbewahrung werden separat mit update-retention.sh und
install-mac-backup.sh eingerichtet (siehe AUFBEWAHRUNG.md).

## Tagesbilanz und Ladephasen (1.3.0)

Unter dem Leistungsverlauf stehen geschätzter Netzbezug und Einspeisung in kWh für das ausgewählte Datum. Die Berechnung integriert Leistung zwischen verbundenen Messpunkten und trennt Vorzeichenwechsel linear. Fehler und größere Lücken werden nicht überbrückt. Einzelpunkte ohne Zeitspanne ergeben keine Energie. Die Datenabdeckung bezieht sich auf den Tag bis jetzt beziehungsweise bis Tagesende, einschließlich fehlender Zeit am Tagesanfang und -ende.

Archivierte Minutenmittel sind eine gröbere Näherung und können wechselnden Bezug/Einspeisung innerhalb einer Minute verdecken. Energiezähler des Shelly werden in dieser Version noch nicht zusätzlich abgefragt. Grüne Flächen im Diagramm markieren gespeicherte Ladeerkennungsphasen ab Bestätigung, ausgespart bei Messlücken. Die Berechnungen erfolgen aus bestehenden Daten, ohne neue Tabellen oder Gerätebefehle.

## Energieringe (1.7.0)

Unter dem Leistungsverlauf erscheinen zwei Ringe für das ausgewählte Datum. Hellgrün = PV-Ertrag minus Einspeisung (geschätzt genutzt/gespeichert), Dunkelgrün = Einspeisung. Orange = Netzbezug, Blau = geschätzte Eigenversorgung. Die Legenden zeigen kWh und verfügbare Anteile, der Ring-Titel zeigt die Werte auch als Tooltip. Ein gemessener Autarkiegrad wird ohne Speicherbilanz nicht ausgewiesen.

Fehlende Werte sind unbekannt, nicht null. Bei weniger als 95 % Datenabdeckung, fehlendem/Null-Ertrag oder Einspeisung über Ertrag bleiben die Ringe neutral. Heute gilt der SolarEdge-Ertrag nach zwei Stunden als veraltet. Die Rückgabe enthält vorbereitete, vorerst leere Felder für Akku-Ladung, Entladung und Ladezustände. Historische Energiezuordnung benötigt später zeitgleiche PV-/Akkuwerte und eine Bilanz für Netzladen. Der Einstellungen-Button steht nun rechts neben dem Messstatus.

## Systemstatus-Position (1.7.3)

Der aufklappbare Systemstatus steht am Ende des Dashboards unter den Energieringen, direkt vor der Fußzeile. Aktualisierung und Statusfunktionen bleiben unverändert.

## Lüfter Bad (1.8.0)

Button links neben Messwerte aktuell; einstellbare Laufzeit in Minuten. Einrichtung und Einschränkungen stehen in MEROSS.md. Der Timer läuft im separaten Pi-Dienst, nicht im Browser. Ein Ausfall kann die Abschaltung verzögern. Kein neuer Cloud-Zugriff durch Browser-Statuspolling; dort wird ausschließlich die lokale Datenbank gelesen.

## Tagesabfragen ab Version 1.8.3

Die Energiebilanz liest nur Zeitstempel, Gesamtleistung und Fehlerstatus. Die Integration behält Richtungswechsel und Messlücken bei; archivierte Minuten bleiben Näherungen. Der Server hält maximal acht abgeschlossene Tagesansichten für jeweils 60 Sekunden im Arbeitsspeicher. Laufende Tage werden nicht zwischengespeichert.

Der Browser lädt vergangene Tage bei Auswahl, ohne sie alle fünf Sekunden erneut abzufragen. Erneute Auswahl lädt erneut vom Server. Aktuelle Messwerte laufen unabhängig weiter. Überholte Verlaufsanfragen werden abgebrochen; bei Tageswechsel erscheint ein Ladehinweis. Das gelbe PV-Band bleibt aus gespeicherter Prognose und aktuellen Parametern berechnet; diese Änderung führt kein zusätzliches PV-Ereignisprotokoll ein.

Update vom Mac: `bash update-history-performance.sh`. Das Skript startet nur den Webdienst neu; die Erfassung läuft weiter.

## Eigenversorgung und Energiekosten · 7 Tage

Das Finanz-Popup lässt sich zwischen „Strompreis“ und „Eigenversorgung & Kosten“ umschalten. Die zweite Ansicht stellt je Tag den berechneten Nutzen der Eigenversorgung grün und die nach Einspeisevergütung verbleibenden Energiekosten orange gegenüber. Die Navigation arbeitet weiterhin wochenweise von Montag bis Sonntag.

Die Zusammenfassung nennt den Nutzen, die verbleibenden Kosten, einen rechnerischen Vergleichswert und den Eigenversorgungsanteil. Unvollständige Tage bleiben als Lücke sichtbar. Der Akku-Anteil ist ein Bruttowert; Ladeverluste, Ladekosten und Verschleiß sind nicht enthalten.

## Abrufintervalle und Hintergrundpause

Bei sichtbarer Seite werden aktuelle Netzwerte weiterhin alle fünf Sekunden geladen. Der größere Tagesverlauf wird alle 30 Sekunden aktualisiert. Im unsichtbaren Browser-Tab oder App-Hintergrund pausieren beide Abrufe. Beim Zurückkehren folgen die Livewerte sofort und der Tagesverlauf kurz danach; die Messwerterfassung auf dem Pi läuft unabhängig davon weiter.
