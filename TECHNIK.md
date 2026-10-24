# Technischer Aufbau

## Portable lokale Konfiguration (1.49.0)

Geräteadressen und das SSH-Ziel liegen ausschließlich in den nicht versionierten
Dateien `config.toml`, `marstek.toml`, `forecast.toml` und `deploy-local.env`. Öffentliche Beispiele
mit Platzhaltern tragen die Endung `.example.toml` beziehungsweise `.example.env`.
Alle Update-Skripte laden ihr Ziel über `deploy-common.sh`; fehlt die lokale Datei,
brechen sie vor einer Netzwerkverbindung mit einer verständlichen Meldung ab.

Das vollständige Deployment überträgt keine lokale Konfiguration und keine
Laufzeitdaten. Vor jedem Lauf entsteht auf dem Pi eine Code-Sicherung; drei Stände
bleiben erhalten. Der Installer übernimmt das konfigurierte Zielverzeichnis in die
systemd-Definitionen, testet den übertragenen Stand vor dem Neustart und startet
alle zuvor aktiven EnergyPi-Dienste kontrolliert gemeinsam neu.

Die automatische Mac-Sicherung kopiert `deploy-local.env` mit Rechten 0600 in ihren
Laufzeitordner. Ihr allgemeiner launchd-Name lautet `local.energypi.mac-backup`.
Ein optionaler früherer Name kann ausschließlich in der lokalen Umgebungsdatei für
eine einmalige Ablösung angegeben werden. Der Systemmonitor-Link verwendet den
Hostnamen der geöffneten Dashboard-Adresse und enthält keine feste Geräte-IP.

Stand 1.30.1. Die Beschreibung bezieht sich auf den lokalen Quellcode; installierte Pi-Version über die Dashboard-Versionsnummer prüfen.

Das Updatepaket der Version 1.23.1 überträgt `marstek_actions.py` zusammen mit
`marstek_control.py`. Beide Module verwenden dieselbe Signatur der
SOC-Sicherheitslogik. Die Tests laufen vor dem Neustart der Dienste und verhindern
bei einer unvollständigen Übertragung die Aktivierung des neuen Stands.

## Projektstruktur

```text
marstek-control/
├── webapp.py                 Webserver und lokale API
├── collector.py              Shelly-Erfassung alle 5 Sekunden
├── marstek.py                Akku-Erfassung und Steuerungsablauf
├── marstek_control.py        Entladebegrenzung beim Autoladen
├── marstek_actions.py        Manuell angeforderter Eigenverbrauch
├── marstek_display.py        Betriebsart und Entscheidungsprotokoll
├── charging.py, controller.py  Autolade-Erkennung
├── optimizer.py              Kostenplan: ausschließlich Beobachtung
├── planning_defaults.py      Vorgaben für das Kostenmodell
├── solaredge.py, energy.py    PV-Leistung und Tagesertrag
├── forecast.py, tibber.py     PV-Prognose und Strompreise
├── weather.py                Außentemperatur als Wettermodellwert
├── fan.py, fan_worker.py      Badlüfter und Abschaltfrist
├── database.py               SQLite-Zugriff und Shelly-Messungen
├── balance.py                Netzenergie aus Leistungswerten
├── battery_history.py        Akku-Verlauf und Lade-/Entladeenergie
├── flow_summary.py           Energiequellen und Energieziele
├── finance_summary.py        Tageskosten und Wert der Eigenversorgung
├── finance_history.py        Wochenverlauf des effektiven Strompreises
├── preferences.py            Einstellungswerte und Validierung
├── settings.py               TOML-Konfiguration laden
├── system_status.py          Zustand aus gespeicherten Daten
├── maintenance.py            Archivierung und Pi-Sicherungen
├── backup_status.py          Rückmeldung der Mac-Sicherung
├── config.toml               Shelly, Datenbank, alter Testmonitor
├── marstek.toml              Elfin-Adresse, Port und Geräteadresse
├── forecast.example.toml     Neutrale Vorlage für Standort und PV-Anlage
├── secrets.toml              Zugangsdaten: privat, nicht verteilen
├── project_info.json         Dokumentation und Versionsverlauf
├── templates/                HTML-Seiten
├── static/                   JavaScript, Diagramme und Gestaltung
├── data/                     Laufzeitdaten auf dem Pi
│   ├── measurements.db       Gemeinsame SQLite-Datenbank
│   └── backups/              Pi-Datenbanksicherungen
├── deploy/                   systemd-Dienste, Timer und Installer
├── tests/                    Tests mit temporären Daten und Geräten
├── update-*.sh               Gezielte Übertragung vom Mac zum Pi
├── .venv/                    Lokale Python-Umgebung je Rechner
└── *.md                      Betrieb, Parameter und technische Details
```

## Datenwege und Module

```text
Shelly → collector.py → SQLite
                         └→ charging.py → Autolade-Zustand

Marstek ↔ Elfin ↔ marstek.py ↔ SQLite
                    ├→ marstek_control.py: Entladegrenze
                    └→ marstek_actions.py: Eigenverbrauch auf Klick

SolarEdge / Forecast.Solar / Tibber / Open-Meteo
          → jeweiliger Sammler → SQLite

SQLite → optimizer.py → gespeicherter Beobachtungsplan
         (kein Pfad zum Akku; keine Gerätebefehle)

SQLite → webapp.py → Browser / Dashboard
Browser → lokale POST-Anfrage → gespeicherter Auftrag / Einstellungen
          → zuständiger Hintergrunddienst → Gerät

Browser → NDR-Livestream / Windy direkt
Pi-Datenbank → geprüfte Sicherung → Mac
```

| Dateien | Zuständigkeit |
|---|---|
| settings.py, config.toml | Konfiguration und Datenbankpfad |
| collector.py, database.py | Messprüfung, Prozesssperre, Speichern und Verlaufsverdichtung |
| controller.py, charging.py | Zustandsmaschine und gespeicherte Ladeerkennung |
| preferences.py | Validierte Einstellungen mit Änderungsprotokoll |
| balance.py, flow_summary.py | Integration von Leistung und AC-Energiebilanz mit Akku-Flüssen |
| solaredge.py, energy.py | PV-Leistung und Tagesertrag; Energieabruf wird von solaredge.py aufgerufen |
| forecast.py, opportunities.py, tibber.py | Prognose, PV-Zeitfenster und Preise |
| fan.py, fan_worker.py, meross_dns.py | Aufträge, Timer, Geräteauswahl und System-DNS |
| maintenance.py, backup_status.py, system_status.py | Archiv, konsistente Sicherung und Status |
| webapp.py, templates/, static/ | Lokale API, HTML und Canvas-Diagramme |
| marstek.py, marstek_control.py, marstek_actions.py, marstek_display.py | Akku-Erfassung, Entladebegrenzung, Buttonauftrag, Betriebsart und Entscheidungsprotokoll |
| optimizer.py, planning_defaults.py | Kosten-Beobachtung aus SQLite, keine Gerätebefehle |
| battery_history.py | Akku-Ladestandsverlauf und AC-Energieintegration |
| project_info.json | Zentrale Dashboard-Dokumentation und Versionsverlauf |
| deploy/, update-*.sh | Dienste, Installer und gezielte Updates |

## Datenbank

Standard: `/home/pi/marstek-control/data/measurements.db`, SQLite mit WAL-Schreibjournal. Zeitstempel grundsätzlich Unix-Sekunden in UTC; Tageszuordnung/Anzeige Europe/Berlin. Tage bei Zeitumstellung haben 23 oder 25 Stunden. Positive Shelly-Wirkleistung = Bezug, negative = Einspeisung. Leistung W, Spannung V, Strom A, Energie kWh, Tibber-API total intern EUR/kWh, Dashboard ct/kWh.

| Tabellen | Inhalt und Grenzen |
|---|---|
| measurements | Empfangszeit, Gesamtwirkleistung, je Phase Wirkleistung/Spannung/Strom, Fehler; kein vollständiger Hausverbrauch und kein separater Akkuzähler |
| minute_archive | JSON mit Mittelwert, Min/Max, Anzahl, erstem/letztem Zeitpunkt und Lückentrennung nach 30 Tagen |
| charging_state, charging_events | Letzte Einschätzung und bestätigte Zustandswechsel; keine tatsächliche Fahrzeugmessung |
| preferences, preference_changes | Einstellungen und alte/neue Werte mit Änderungszeit |
| solaredge_samples | Cloud-Leistungswerte und Abruffehler; Abrufzeit ist nicht zwingend Messzeit |
| solaredge_energy, energy_attempts | Tagesertrag mit letztem Abruf; Tageswerte können aktualisiert werden, kein vollständiges Revisionsarchiv |
| forecast_runs, forecast_days | Abrufversuche und versionierte Tagesprognosen als JSON |
| tibber_prices, tibber_attempts, tibber_meta | Preise je Home/Intervall, Abrufe und gewähltes Home |
| fan_state, fan_events | Gerätebindung, Auftrag, Abschaltfrist, beobachteter Status und Ereignisse |
| backup_status | Zuletzt gemeldeter Sicherungserfolg und letzter Versuch; keine laufende Dateiprüfung am Mac |

Shelly-Energiezähler werden derzeit nicht gespeichert. kWh für Netzbezug/Einspeisung entstehen durch zeitliche Integration der Gesamtleistung. Lücken werden nicht überbrückt; verdichtete Minuten können Richtungswechsel verdecken. Andere Tabellen haben derzeit keine allgemeine automatische Löschfrist. Kein festes Größenlimit der Anwendung; Datenträger und Sicherungskopien begrenzen die Kapazität praktisch.

## Lokale HTTP-Endpunkte

GET: `/api/status`, `/api/history?date=YYYY-MM-DD&mode=day`, `/api/charging`, `/api/solaredge`, `/api/forecast?date=YYYY-MM-DD`, `/api/tibber?date=YYYY-MM-DD`, `/api/system`, `/api/preferences`, `/api/fan`. `mode=hour` zeigt die rollende letzte Stunde; die Tagesbilanz bezieht sich weiterhin auf das gewählte Datum.

POST `/api/preferences` und `/api/fan` erwarten JSON und Header `X-EnergyPi: settings`. Kein Benutzerlogin: ausschließlich vertrauenswürdiges Heimnetz, keine Router-Portfreigabe. Der Header verhindert keine Zugriffe durch andere Geräte im Heimnetz. Statusabfragen lesen lokale Daten; kein Cloud-Abruf bei jedem Browser-Poll.

## Prüfung vor Auslieferung

Im Projekt `.venv/bin/python -m unittest discover -s tests -q`; für Tibber-Datumswechsel zusätzlich `node tests/test_tibber_ui.cjs` mit verfügbarem Node.js. Tests nutzen temporäre Datenbanken und simulierte Geräte. Kein Testnachweis echter Meross-Schaltung, Pi-Laufzeit oder Marstek-Verkabelung. Auf dem Pi nach Update Versionsnummer, aktuelle Messung, betroffene Anzeige und Dienstlogs prüfen. Gezielte Updates installieren nur ihre angegebenen Dateien; vollständiges Deployment ist kein Ersatz für fehlende Zusatzdienst-Installer.

## Wetter und Radio ab 1.9.0

weather.py erfasst Open-Meteo alle 15 Minuten; weather_samples speichert Wetterzeit, Abrufzeit, °C, Standort und Quelle, weather_attempts Abrufversuche. GET /api/weather liefert letzten Wert, Fehler und Veraltung. Tabellen sind in DB-Sicherung enthalten, keine eigene Löschfrist. static/weather.js liest lokal jede Minute. static/radio.js steuert ein gemeinsames HTML-Audioelement für NDR Info und seit 1.26.0 NDR 2 Schleswig-Holstein direkt vom Browser zum Sender. Ein Senderwechsel stoppt zuerst die laufende Verbindung. Keine Radio-Tabellen, kein Stream über Pi.


## Marstek-Beobachtung (1.10.0)

Siehe [MARSTEK.md](MARSTEK.md): eigener Dienst `marstek-battery`, 30-Sekunden-Abfragen, Tabelle `marstek_samples`, lokaler Endpunkt `/api/marstek`. Ab 1.11.0 zusätzlich konfigurierbare Autolade-Entladegrenze (200 W), mit Wiederherstellung und Mindestabstand; siehe MARSTEK.md. Bei Wiederherstellung der Datenbank diesen zusätzlichen Schreiber ebenfalls stoppen. Installation vom Mac: `bash update-marstek.sh` (auf bestehender Version 1.9.0).


## Akku-Verlauf und Energieanteile (1.12.0)

`battery_history.py` liest die vorhandenen 30-Sekunden-Messungen in `marstek_samples`. `forecast_status` liefert zusätzlich `battery.segments` für die violette Ladestandskurve auf der rechten 0–100-%-Achse. Keine zusätzlichen Geräte- oder Cloud-Abfragen. Daten bleiben in SQLite und den Sicherungen erhalten. Messfehler und Abstände über 90 Sekunden unterbrechen die Linie und Energieintegration. Keine erfundenen historischen oder zukünftigen Werte.

Die Quellen sind PV + Netzbezug + Akku-Abgabe; Ziele sind berechneter Hausverbrauch + Einspeisung + Akku-Ladung. Positive/negative AC-Leistung wird getrennt trapezförmig mit linearem Nulldurchgang integriert. Keine doppelte Zuordnung als direkter PV-Verbrauch, kein Autarkiegrad. Akku-Ladung und spätere Abgabe tauchen als verschiedene Flüsse auf.

Heute richtet sich der gemeinsame Bilanzzeitraum nach dem Abruf des SolarEdge-Tagesertrags; dessen Cloud-Zeitversatz bleibt als Unsicherheit. Während des PV-Tages gilt der Wert nach zwei Stunden als veraltet. Nach dem lokalen Sonnenuntergang bleibt ein höchstens 30 Minuten vor Sonnenuntergang abgerufener Tageswert bis Mitternacht gültig. Die Bilanz endet weiterhin am tatsächlichen SolarEdge-Abrufzeitpunkt und ergänzt keine geschätzte Energie. Unter 95 % Netz- oder Akku-Abdeckung bleiben die Ringe grau und bekannte Akku-kWh sind ausdrücklich nur Teilmengen. Auch negative berechnete Hausenergie verhindert eine Aufteilung. Tage vor Beginn der Akku-Erfassung werden nicht nachträglich vervollständigt.

Installation auf dem bisherigen Projekt: `bash update-energy-flows.sh`.

## Geldwerte der Tagesenergie (1.24.0)

`finance_summary.py` ordnet jedem erfassten Netzbezugsabschnitt den überlappenden
Tibber-Viertelstundenpreis zu. Das Ergebnis ist der tatsächliche variable
Netzbezugspreis ohne monatliche Grundgebühr. Mindestens 95 % der von der
Netzintegration erfassten Zeit müssen einen Preis besitzen; andernfalls bleiben
beide Geldringe als unvollständig markiert.

Der zweite Ring zeigt drei Rechenwerte: Einspeisung zum einstellbaren
Vergütungssatz, Vorteil des direkten PV-Verbrauchs gegenüber Einspeisung und
Bruttowert der Akku-Abgabe zum zeitgewichteten Tibber-Preis. Direkter
PV-Verbrauch wird näherungsweise als PV-Erzeugung minus Einspeisung und
Akku-Ladung berechnet. Herkunft, Ladekosten, Verluste und Verschleiß des
Akkustroms sind in diesem Ring nicht bestimmbar und deshalb ausdrücklich nicht
vom Bruttowert abgezogen. Die Berechnung erzeugt keine Gerätesteuerung und keine
zusätzliche Cloud-Abfrage.

Seit 1.24.1 fasst ein Satz unter den Ringen die Netzstromkosten, die rechnerische
Ersparnis aus PV-Eigenverbrauch und Akku-Abgabe sowie die Einspeisevergütung
getrennt zusammen. Historische Ansichten nennen das ausgewählte Datum. Bei
unvollständigen Daten werden keine Teilbeträge als Tagesergebnis ausgegeben.

Version 1.25.0 ergänzt zwei Preise. Der tatsächliche Bezugspreis ist die Summe
der intervallgenauen Netzbezugskosten geteilt durch den gleichzeitig bewerteten
Netzbezug. Der effektive Haushaltsstrompreis ist `(Netzbezugskosten minus
Einspeisevergütung) / Hausverbrauch`. Er kann bei hohen Einspeiseerlösen negativ
werden. Monatliche Grundgebühr, Anlagenanschaffung, Akkuladekosten, Verluste und
Verschleiß gehören nicht zu diesem Wert. Bei null Kilowattstunden oder
unvollständiger Preis-/Energiedeckung erscheint kein Preis.

## Wochenverlauf des effektiven Strompreises (1.30.0)

`GET /api/finance/history?days=7&week=2026-10-05` berechnet die sieben Tage der
Kalenderwoche von Montag bis Sonntag. `finance_history.py` verwendet dieselbe Formel
und dieselben Vollständigkeitsregeln wie die Geldringe. Abgeschlossene vollständige
Tage liegen dauerhaft in SQLite; der heutige Tag wird bei jedem Öffnen neu berechnet.
Unvollständige und zukünftige Tage erscheinen als Lücke. Der Endpunkt liest nur
SQLite und löst keine Cloud-Abfrage aus.

Das Dialogfenster zeigt Kalenderwoche und Datumsbereich sowie Schaltflächen für die
vorherige, aktuelle und folgende Woche. Positive Werte erscheinen blau, negative
grün, der laufende Tag heller und Datenlücken gestrichelt. Wochentag und Datum stehen unter jedem Balken. Tooltip,
Formeltext und Legende nennen Kosten, Vergütung, verbleibende Kosten und
Hausverbrauch. Grundgebühr, Anlagenanschaffung und Akkuverschleiß bleiben außerhalb
der Kennzahl.

Seit 1.27.1 verwendet die Preisachse feste Rasterlinien in Schritten von 5 ct/kWh.
Sie enthält immer mindestens −5, 0 und +5 ct/kWh und erweitert sich bei größeren
Werten auf das nächste Vielfache von fünf. Die Nulllinie ist dunkler und doppelt so
stark wie die übrigen Rasterlinien.

## Ring-Summen und Bilanzzeitstempel (1.16.2)

Die Ringmitten zeigen bei gültiger Bilanz die jeweilige Summe mit genau einer Nachkommastelle (auch 0,0 kWh). Ungültige oder unvollständige Bilanzen bleiben „Nicht bestimmbar“. `flows.until` wird in Europe/Berlin als Ende des Bilanzzeitraums angezeigt; bei abgeschlossenen Tagen ist dies Mitternacht des Folgetags. Der Zeitstempel ist kein Browserabruf und keine Garantie für den tatsächlichen SolarEdge-Messzeitpunkt.

## Akku-Grenzen im Tibber-Diagramm (1.17.0)

`opportunities.battery_thresholds` berechnet die PV- und Netzlade-Grenze aus
Gesamtwirkungsgrad, Verschleiß, Vorteilspuffer sowie Einspeisevergütung oder dem
aktuellen Tibber-Preis. `/api/tibber` liefert Werte und Rechenparameter. Die
Browsergrafik bezieht beide Grenzen in ihre y-Skalierung ein und zeichnet sie als
gestrichelte Vergleichslinien. Es handelt sich um Modellwerte ohne Gerätebefehl.

Seit 1.44.0 zeigt die Tibber-Kachel in der Live-Übersicht zusätzlich einen kompakten
Verlauf der bereits geladenen heutigen Viertelstundenpreise. Das aktuelle Viertel wird durch
einen hellen Punkt markiert. Der Miniaturverlauf löst keinen weiteren API-Abruf aus;
sein Link springt zur ausführlichen Preisgrafik im Bereich „Prognose und Preise“.
Seit 1.44.1 verändert die Datumsauswahl der großen Grafik den Miniaturverlauf nicht.

## Phasen-Popup (1.45.0)

Die Live-Übersicht zeigt die drei Phasenkacheln nicht mehr dauerhaft. Der Link in
„Aktuelle Netzleistung“ öffnet sie als Dialog. `dashboard.js` schreibt weiterhin in
dieselben Elemente für Phase A, B und C; Abruf und Messintervall ändern sich nicht.
`phases.js` steuert ausschließlich Öffnen und Schließen des Dialogs.

## Korrigierte Lasterkennung und Dauerlastschutz (1.18.0)

Der Shelly-Sammler liest zur Netzleistung den letzten gültigen Marstek-AC-Wert aus
SQLite. Ist dieser höchstens 90 Sekunden alt, wird eine positive Akku-Abgabe zur
Netzleistung addiert. Diese korrigierte Leistung steuert die bestehende
Start-/Endehysterese. Parallel qualifiziert `Controller` eine durchgängige hohe
Akku-Abgabe mit eigener Schwelle und Frist. Beide Wege setzen denselben gespeicherten
Schutzzustand und verwenden dieselbe Marstek-Entladegrenze. Messlücken setzen laufende
Fristen zurück; ohne frischen Akkuwert kann der Dauerlastweg nicht neu auslösen.

`charging_state` wurde abwärtskompatibel um Auslösegrund, Netz-, Akku- und korrigierte
Leistung sowie Schutzparameter ergänzt. `charging_events.reason` unterscheidet
Lastregel und Dauerlastschutz. Bestehende Ereignisse bleiben erhalten und haben dort
keinen Auslösegrund.

## Akku-Ladestandsring (1.19.0)

Die Marstek-Karte stellt den aus Register 32104 gelesenen Ladestand zusätzlich als
CSS-Kreisring dar. Der Winkel entspricht 0–100 %, die Zahl bleibt in der Ringmitte.
Über 50 % ist der Ring grün, bis 50 % gelb und bis 20 % rot. Veraltete Werte werden
abgeblendet; fehlende oder unplausible Werte ergeben einen grauen Ring ohne
Prozentangabe. `aria-label` und Titel enthalten denselben Ladestand als Text.

## Entlade-Zielregler (1.20.0)

`GET /api/marstek` liefert zusätzlich den gespeicherten Wert
`discharge_target_w`. Der Regler führt während des Ziehens ausschließlich lokalen
Browserzustand. `POST /api/marstek/discharge-target` akzeptiert nach JSON- und
`X-EnergyPi: settings`-Prüfung genau einen Zielwert. Die gemeinsame
`save_preferences`-Validierung erzwingt 0–800 W in 50-W-Schritten und führt das
vorhandene Änderungsjournal weiter.

Eine tatsächliche Modbus-Änderung erfolgt nicht im Webprozess. Bei aktivem Schutz
erkennt `marstek_control.step` den geänderten Zielwert beim nächsten Worker-Lauf und
wendet weiterhin Mindestabstand, Schreibjournal und Rücklesekontrolle an. Das
Entscheidungsprotokoll erhält beim Speichern einen Eintrag `TARGET_CHANGED`.
## SOC-Sicherheitssteuerung ab 1.21.0

`marstek_control.py` liest den jüngsten gültigen Ladestand aus `marstek_samples`.
Ein Messwert gilt 90 Sekunden. Die Zustandsmaschine speichert `soc_band`,
`soc_limit_w`, `soc_checked_at`, `soc_stale`, `effective_target_w` und
`effective_reason` im vorhandenen JSON-Zustand `marstek_control_state`; eine
Schemaänderung ist dafür nicht nötig.

Die Stufen sind `high` 800 W, `medium` 300 W, `low` 100 W und `reserve` vorläufig
100 W. Fallende Übergänge liegen bei 60/40/20 %, steigende wegen der Hysterese bei
63/43/23 %. `min(Ausgangsgrenze, SOC-Grenze, aktives Schutzziel)` bestimmt den
Zielwert. SOC-bedingte Absenkungen dürfen sofort geschrieben werden. Alle anderen
Änderungen beachten `marstek_interval_seconds`. Ein veralteter SOC hält die letzte
Stufe und sperrt Erhöhungen, bis wieder ein aktueller Wert vorliegt.

## Morgenkomfort-Zustandsmaschine (historischer Stand 1.22.0, ersetzt)

Die frühere einmalige Budget-Zustandsmaschine wurde in 1.23.0 durch eine
durchgehende Zeitfreigabe und die Nachtreserve-Regel ersetzt.

## Zeit- und Reserveregel (1.23.0)

`morning.py` berechnet ohne Gerätezugriff den aktiven Morgenstatus, den Ziel-SOC
zum Nachtbeginn und die Eignung der verbleibenden PV-Prognose. Grundlage sind
`preferences`, der aktuelle SOC sowie die jüngste höchstens vier Stunden alte
Forecast.Solar-Version in SQLite. Das Ergebnis wird im vorhandenen JSON-Feld
`morning` von `marstek_control_state` gespeichert; eine Schemaänderung ist nicht
nötig.

`marstek_control.step` bildet das Minimum aus Ausgangsgrenze, zeitabhängiger
SOC-/Reserveregel und Autolade- beziehungsweise Dauerlastziel. Die Schutzgrenze hat
0 W. Eine neue niedrigere Grenze wegen SOC, Autoladen oder Dauerlast umgeht den
15-Minuten-Abstand; Erhöhungen, Wiederherstellungen und prognosebedingte Freigaben
halten ihn ein. Alle Schreibvorgänge verwenden weiterhin persistente Absicht,
Modbus-Rücklesen und Konflikterkennung.

## Kompakte Tagesbilanz in der Live-Übersicht (1.46.0)

Die sechste Kachel der Live-Übersicht fasst die aktuelle Tagesbilanz zusammen. Zwei
kompakte Balken zeigen die Quellen PV, Netzbezug und Akku-Abgabe sowie die Ziele
Hausverbrauch, Netzeinspeisung und Akku-Ladung. Ergänzend erscheinen Netzstromkosten,
Nutzen der Eigenversorgung, effektiver Haushaltsstrompreis und der SOC-Verlauf. Ein
Link führt zur ausführlichen Ansicht „Energieanteile“.

Die Kachel verwendet ausschließlich die bereits von `/api/history` geladene Bilanz.
Sie erzeugt keinen zusätzlichen Abruf und übernimmt nur Antworten für den lokalen
heutigen Kalendertag. Wird unten ein anderer Tag gewählt, bleibt die Live-Kachel daher
auf dem letzten heutigen Stand. Unvollständige Bilanz- oder Preisdaten werden sichtbar
als unvollständig markiert und nicht durch Schätzwerte ersetzt.

Die Live-Übersicht ordnet ihre sechs Kacheln auf breiten Bildschirmen und im iPad-
Querformat in drei Spalten und zwei Zeilen an. Im schmaleren Hochformat folgen zwei
Spalten, auf kleinen Telefonen eine Spalte.

Seit Version 1.46.1 wird der effektive Haushaltsstrompreis in der kompakten
Tagesbilanz größer und gelb dargestellt, damit er sich von den ergänzenden Geldwerten
abhebt.

## Manueller Ladeauftrag (1.47.0)

Der automatische Netzladevorschlag und sein Bestätigungsbutton wurden aus Oberfläche
und regelmäßigem Statusabruf entfernt. Die Marstek-Kachel öffnet stattdessen über
„Laden“ einen Dialog für einen ausdrücklich eingegebenen Auftrag. Als Start sind das
nächste Viertel, eine Verzögerung von 0,25 bis 24 Stunden oder ein konkretes lokales
Datum mit Uhrzeit möglich. Das Ladeziel wird als gewünschte gespeicherte Energie oder
als Laufzeit angegeben; die Leistung ist in 50-W-Schritten von 50 bis 2.500 W wählbar.

`POST /api/grid-charge/preview` prüft den Auftrag und berechnet Start, Ende,
Netzenergie, gespeicherte Energie, Ziel-SOC sowie – bei ausreichender Preisabdeckung –
den mittleren Tibber-Preis und die Kosten. Erst `POST /api/grid-charge` speichert den
Auftrag. Beide Schreibzugriffe verlangen weiterhin den lokalen Schutzheader. Der
Auftrag muss wegen des einzelnen geräteseitigen Zeitplans vor Mitternacht enden.

Der vorhandene Worker und Zeitplan 6 bleiben unverändert das Sicherheitsgerüst:
Eigenverbrauch bis zum Start, Prüfung auf belegte oder überschneidende Zeitpläne,
manueller Modus erst ab Start sowie Rückkehr zum Eigenverbrauch nach Endzeit,
Ziel-SOC oder Abbruch. Bereits gespeicherte Aufträge der vorherigen Version werden
weiter verarbeitet. Die früheren Vorschlagsparameter werden beim Lesen alter
Einstellungen verworfen und nicht mehr im Einstellungsdialog angeboten.

Seit Version 1.47.1 setzt „Jetzt“ den Beginn auf die laufende Minute. Der Worker
richtet den Auftrag beim nächsten 30-Sekunden-Durchlauf ein und schaltet unmittelbar
in den manuellen Modus. Die Viertelstundenrundung bleibt ausschließlich für verzögerte
Starts bestehen. Nicht ausgewählte Eingabevarianten erzwingen über `[hidden]` die
Ausblendung, auch innerhalb des CSS-Grids.

## Worker-Aktualisierung (1.47.2)

Das Dashboard-Update startet nun `marstek-battery` gemeinsam mit `marstek-web` neu.
Der dauerhaft laufende Python-Prozess lädt `grid_charging.py` nur beim Start; ohne
Neustart kann er das neue Steuerformat 2 als alten Testauftrag verwerfen. Das sichere
Verwerfen hat keine Register geschrieben und keine Ladung ausgelöst.

## Touch-Eingabe im Ladedialog (1.47.3)

Dauer und Ladeleistung besitzen große Minus- und Plus-Tasten mit 15 Minuten bzw.
250 W Schrittweite. Für die Ladeleistung stehen zusätzlich Direktwahlen von 500 bis
2.500 W bereit. Jede Änderung verwirft die vorherige Vorschau, sodass nur mit den
sichtbaren aktuellen Werten ein Auftrag erzeugt werden kann. Die Zahlenfelder bleiben
für freie Eingaben in den serverseitig validierten Grenzen erhalten.

## Tibber-Tagesbereich und Ladezeiten (1.48.0)

Die Tibber-Live-Kachel zeigt Minimum und Maximum des bereits geladenen heutigen
Preisdatensatzes. Die Werte bleiben wie der Miniaturverlauf vom Datum der großen
Grafik getrennt und erzeugen keinen zusätzlichen Abruf. `complete` kennzeichnet, ob
alle heutigen Viertelstunden veröffentlicht wurden.

Der Ladedialog liest den bestehenden Auftragsstatus weiterhin alle 30 Sekunden. Bei
einem geplanten Auftrag zeigt die Marstek-Kachel den vorgesehenen Zeitraum und den
Eigenverbrauch bis zum Start. Bei aktiver Ladung gilt der Zeitpunkt des bestätigten
Statuswechsels als tatsächlicher Start; aus der gespeicherten Endzeit wird die
verbleibende Zeit berechnet. Diese Anzeige löst keinen zusätzlichen Modbus-Abruf aus.

## Bedienung der Energiemenge (1.48.1)

Die Energiemenge im Ladedialog lässt sich über große Minus- und Plus-Tasten in
0,1-kWh-Schritten ändern. Direkte Vorgabetasten gibt es für dieses Feld nicht. Der
Ladebutton in der Marstek-Kachel nutzt dieselbe gerahmte, touchgerechte Darstellung
wie der Button für die Windy-Wolkenkarte; Status und Funktion bleiben unverändert.
