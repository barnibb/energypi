# Marstek-Messwerte und Begrenzung

Venus E V2 über Elfin EW11A; Adresse aus der lokalen `marstek.toml`, Port 502, Unit 1.
Elfin: TCP Server, Route UART; UART 115200 8N1, Half Duplex, Protocol Modbus.
Anschlussdaten liegen in marstek.toml (keine Zugangsdaten). In der FRITZ!Box eine feste DHCP-Zuordnung vorsehen.

## Betrieb

Ein eigener Dienst marstek-battery.service liest alle 30 Sekunden zwei Registerblöcke.
Messwerte über Modbus-Funktion 03: 32100–32104 und 32200–32204. Zusätzlich liest die Automatik 44003, 43000 und 42000; sie schreibt ausschließlich Register 44003 mit Funktion 06. Keine Moduswechsel oder RS485-Zwangssteuerung.
Ein Ausfall des Elfin blockiert nicht die Shelly-Erfassung. Ein Dateilock verhindert zwei Sammler für dieselbe Datenbank.
Pro Verbindung gelten drei Sekunden Socket-Timeout. Kein unmittelbarer Wiederholungsversuch.

Registerquelle: https://github.com/ViperRNMC/marstek_venus_modbus/blob/main/custom_components/marstek_modbus/registers/e_v12.yaml
32-Bit-Werte werden mit dem höherwertigen Wort zuerst gelesen.
Am 18.09.2026 live geprüft: SOC 91 %, AC +797 W, Batterie −888 W.
Positive AC-Leistung bedeutet Abgabe ins Haus, negative AC-Leistung Laden.
Die interne Batterieleistung hat die entgegengesetzte Richtung; ihre Differenz zur AC-Leistung enthält Verluste und Eigenverbrauch.

## Speicherung und Anzeige

In der bestehenden data/measurements.db liegt marstek_samples:
- ts: UTC Unix-Sekunden nach der Abfrage
- soc: Prozent
- ac_power_w: signierte AC-Leistung in Watt
- battery_power_w: signierte interne Batterieleistung in Watt
- battery_voltage_v und ac_voltage_v: Volt
- error: Fehlertext; bei Fehler sind alle Messwerte NULL, niemals künstlich null Watt

Zeitindex und zusätzlicher Index gültiger Messungen halten die Statusabfrage klein.
30 Sekunden ergeben etwa 2.880 Zeilen pro Tag. Diese neue Tabelle wird vorerst dauerhaft aufbewahrt; die vorhandene 30-Tage-Verdichtung der Shelly-Tabelle gilt hier nicht.
SQLite-Sicherungen enthalten automatisch die neue Tabelle. Keine historischen Akkuwerte werden rekonstruiert.

GET /api/marstek liest ausschließlich SQLite, ohne Gerätezugriff. Die Browser-Karte wird alle zehn Sekunden erneuert.
Bei einer Fehlmessung oder Messwertalter über 90 Sekunden wird der letzte Wert ausdrücklich als veraltet markiert.
Die Karte zeigt Ladestand, AC-Leistung, Richtung und Messzeit. Ab 1.12.0 sind historische Ladestandskurve und AC-Energiebilanz ergänzt. Die Auto-Erkennung nutzt weiterhin den Netzbezug.

## Installation vom Mac

Voraussetzung: EnergyPi 1.9.0 mit Wetter/Radio bereits installiert.

```sh
bash update-marstek.sh
```

Das Skript überträgt Code ohne secrets.toml oder Datenbanken. Vorhandene marstek.toml bleibt erhalten.
Der Installer testet, erweitert das Schema ohne vorhandene Daten zu löschen und aktiviert den separaten Dienst.

Auf dem Pi prüfen:

```sh
systemctl status marstek-battery --no-pager
journalctl -u marstek-battery -n 20 --no-pager
curl --silent http://127.0.0.1:8080/api/marstek
```

Bei Datenbank-Wiederherstellung zusätzlich marstek-battery stoppen und danach starten.
Bei vollständigem Neuaufbau marstek.toml und den Dienst wieder einrichten.
Zum Abschalten dieser Erfassung: sudo systemctl disable --now marstek-battery.

## Schreibfreie Registerdiagnose

`marstek_diagnose.py` erstellt eine beschriftete Momentaufnahme der Steuerregister
42000, 42010, 42011, 42020, 42021, 43000, 44000, 44002 und 44003 sowie der sechs
Zeitplanblöcke 43100–43129. Zusätzlich werden SOC und AC-Leistung aufgenommen.
Das Werkzeug verwendet ausschließlich Modbus-Funktion 03 und besitzt keinen
Schreibpfad. Die Zeitplanwerte bleiben als Rohwerte erhalten; nur die signierte
Leistung wird zusätzlich dekodiert.

Für einen Vergleich zuerst im Eigenverbrauch messen, anschließend in der
Marstek-App manuelles Laden einstellen und erneut messen:

```sh
cd /home/pi/marstek-control
.venv/bin/python marstek_diagnose.py --label eigenverbrauch
.venv/bin/python marstek_diagnose.py --label manuelles-laden
```

Die lesbaren Ausgaben erscheinen im Terminal. JSON-Dateien liegen unter
`data/diagnostics/` und enthalten keine Zugangsdaten. Während der kurzen Diagnose
sollte die App nicht weiter umgeschaltet werden. Das Ergebnis belegt Registerwerte
der installierten Firmware, aber noch nicht die Wirkung eines eigenen Schreibbefehls.


## Autolade-Begrenzung (1.11.0)

Einstellungen: `ev_discharge_limit_w` standardmäßig 200 W, 0–800 W in 50-W-Schritten.
Bei gültiger bestätigter Ladeerkennung wird die vorherige Grenze dauerhaft gespeichert und höchstens der eingestellte Wert angefordert. Bereits niedrigere Grenzen werden nicht erhöht. Nach bestätigtem Ende wird der vorherige Wert wiederhergestellt, niemals pauschal 2.500 W.
`marstek_interval_seconds` gilt nun für jeden Schreibversuch, auch Rücksetzung, Fehler und Neustarts. Vorgabe 900 Sekunden. Dadurch kann eine Begrenzung nach neuem Ladebeginn verzögert sein. Die erste Änderung kann sofort nach bestätigter Erkennung erfolgen.
Die Automatik läuft im selben gesperrten Prozess wie der Sammler. `--once` bleibt ausschließlich lesend.
Nur Eigenverbrauchsmodus (43000=1) ohne RS485-Zwangssteuerung (42000=21947) wird unterstützt.

`marstek_control_state` speichert Ausgangsgrenze, bestätigten Wert, offenen Schreibauftrag, Zeitpunkt des letzten Versuchs und Status. `marstek_control_events` protokolliert REQUEST vor dem Senden, CONFIRMED nach Zurücklesen und ERROR bei Problemen. Nach verlorener Antwort wird zuerst gelesen, nicht sofort wieder geschrieben. Die Bestätigung belegt den Registerwert; die physische Leistungsbegrenzung ist nach Installation zusätzlich anhand des Leistungsverlaufs zu prüfen.

Bei veralteter Ladeerkennung keine Änderungen. Bei Verbindungs-/Pi-Ausfall kann die letzte Grenze bestehen bleiben. Stoppen des Dienstes stellt die Grenze nicht automatisch zurück. Externe Änderungen während einer verwalteten Begrenzung pausieren die Automatik dauerhaft, damit App-Einstellungen nicht überschrieben werden. Nach manueller Prüfung: Dienst stoppen, gewünschte Grenze in der App setzen, gesicherten Zustand durch einen Administrator zurücksetzen und Dienst starten. Kein automatisches Übernehmen fremder Änderungen.
Bei Wiederherstellung alter Datenbanksicherungen zuerst die tatsächliche Gerätegrenze und den gespeicherten Steuerzustand prüfen, bevor dieser Dienst gestartet wird.

Die Registerzuordnung wurde recherchiert und die vorhandene Grenze von 800 W live gelesen. Die Begrenzung wurde am Gerät bestätigt: Registerwert 200 W, tatsächliche Abgabe 199 W bei erkanntem Autoladen. Die Logik ist zusätzlich mit simulierten Geräten getestet.


### Zielwert-Regler (1.20.0)

Rechts neben dem Ladestandsring liegt ein Regler für `ev_discharge_limit_w` von
0 bis 800 W in 50-W-Schritten. Verschieben allein schreibt weder SQLite noch das
Gerät; erst `Übernehmen` sendet einen geschützten JSON-Aufruf an
`POST /api/marstek/discharge-target`. Der Endpunkt verwendet denselben Parameter
wie das Zahlenfeld unter Einstellungen, validiert ihn serverseitig und schreibt die
Änderung in `preference_changes` sowie als `TARGET_CHANGED` ins Entscheidungsprotokoll.

Ohne aktiven Autolade- oder Dauerlastschutz bleibt die tatsächliche Gerätegrenze
unverändert. Während eines aktiven Schutzes verarbeitet ausschließlich der
Marstek-Worker das neue Ziel unter Beachtung des Mindestabstands und mit der bereits
vorhandenen Rücklesekontrolle. Die Karte unterscheidet deshalb „Maximale
Entladeleistung bei Schutz“ von der separat aus Register 44003 gelesenen aktuellen
„Entladegrenze“.


## Akku-Verlauf und Energieanteile (1.12.0)

`battery_history.py` liest die vorhandenen 30-Sekunden-Messungen in `marstek_samples`. `forecast_status` liefert zusätzlich `battery.segments` für die violette Ladestandskurve auf der rechten 0–100-%-Achse. Keine zusätzlichen Geräte- oder Cloud-Abfragen. Daten bleiben in SQLite und den Sicherungen erhalten. Messfehler und Abstände über 90 Sekunden unterbrechen die Linie und Energieintegration. Keine erfundenen historischen oder zukünftigen Werte.

Die Quellen sind PV + Netzbezug + Akku-Abgabe; Ziele sind berechneter Hausverbrauch + Einspeisung + Akku-Ladung. Positive/negative AC-Leistung wird getrennt trapezförmig mit linearem Nulldurchgang integriert. Keine doppelte Zuordnung als direkter PV-Verbrauch, kein Autarkiegrad. Akku-Ladung und spätere Abgabe tauchen als verschiedene Flüsse auf.

Heute richtet sich der gemeinsame Bilanzzeitraum nach dem Abruf des SolarEdge-Tagesertrags; dessen Cloud-Zeitversatz bleibt als Unsicherheit. Unter 95 % Netz- oder Akku-Abdeckung bleiben die Ringe grau und bekannte Akku-kWh sind ausdrücklich nur Teilmengen. Auch negative berechnete Hausenergie verhindert eine Aufteilung. Tage vor Beginn der Akku-Erfassung werden nicht nachträglich vervollständigt.

Installation auf dem bisherigen Projekt: `bash update-energy-flows.sh`.


### Korrektur 1.12.1

Die Akku-Zeile unter den Ringen zeigt erfasste Lade-/Entladeenergie und den ersten/letzten gespeicherten Ladestand im Bilanzzeitraum. Bei unvollständiger Erfassung sind dies keine Ladestände exakt um Mitternacht. Der alte Platzhalter wurde entfernt.


### Systemstatus 1.12.2

Die Marstek-Kachel nutzt reale SQLite-Messwerte: aktuell, veraltet (über 90 Sekunden), fehlende Messdaten oder Abruffehler. Letzte erfolgreiche Aktualisierung ist der Zeitstempel der letzten gültigen Messung. Begrenzungskonflikte und gemeldete Steuerfehler werden als Prüfhinweis angezeigt. Es erfolgt keine zusätzliche Geräteabfrage aus dem Browser.


### Manuelle Vorgaben (1.12.3)

Manuelle/externe Betriebsarten und Änderungen der Entladegrenze erscheinen neutral als „Manuelle Vorgabe aktiv · Automatik pausiert“, ohne Fehlerhinweis. Die bestehende Steuerlogik bleibt unverändert: abweichende Betriebsarten pausieren vorübergehend; eine erkannte externe Änderung der verwalteten Grenze pausiert bis zur erneuten Freigabe. Verbindungsfehler und nicht bestätigte Schreibvorgänge bleiben Warnungen/Fehler.


## Eigenverbrauch-Button (1.13.0)

Rechts neben dem Ladestand. POST `/api/marstek/self-consumption` benötigt JSON und X-EnergyPi: settings. Erzeugt nur einen SQLite-Auftrag, keinen Gerätezugriff im Webprozess. `marstek_actions` speichert Zeitpunkt, Status und Rückmeldung. Mehrfachklicks erzeugen während eines offenen Auftrags keinen zweiten Auftrag. Alle Gerätezugriffe bleiben im exklusiven Marstek-Worker.

Der Worker wartet auf eine aktuelle Ladeerkennung. Dann wird Register 43000 = 1 (Eigenverbrauch/anti_feed) mit FC06 geschrieben und zurückgelesen. Eine aktive RS485-Zwangssteuerung wird nicht aufgehoben. Eine zuvor von EnergyPi abgesenkte Entladegrenze wird beim ausdrücklichen Benutzerauftrag sofort bis zur bekannten Ausgangsgrenze wieder freigegeben; SOC-, Autolade- und Dauerlastschutz begrenzen sie weiterhin. Nur ein tatsächlicher Grenzwert-Schreibvorgang erneuert den 15-Minuten-Abstand der Automatik. Die Entladegrenze wird vor dem Moduswechsel bestätigt, damit Eigenverbrauch nicht mit 0 W im Standby verbleibt.

Aufträge laufen nach zweimal Mindestabstand plus zwei Minuten ab. Nach Prozessabbruch während des Schreibens nur Rücklesen, kein automatisches Wiederholen des Modusbefehls. Bei nicht bestätigtem Wechsel Status prüfen und neu anfordern. Der Button ist bei veralteten Daten oder offenem Auftrag gesperrt. Es gibt keine automatische Umschaltung bei 0 W. Der reale Moduswechsel wurde nicht testweise ausgelöst; er erfolgt erst auf Nutzerklick nach Installation.

Installation: `bash update-self-consumption.sh`.


## Betriebsart und Entscheidungsprotokoll (1.14.0)

Keine zusätzlichen Modbus-Abfragen: Die ohnehin gelesenen Register 43000 und 42000 werden mit Zeitstempel in marstek_control_state gespeichert. Anzeige über `operating` im bestehenden Statusendpunkt. Manueller Modus + AC-Leistung unter −30 W bedeutet „Manuelles Laden“, über +30 W „Manuelle Entladung“, dazwischen Pause. Es wird kein manueller Lade-Sollwert behauptet. Die angezeigte Grenze ist stets die maximale Entladeleistung, nicht eine Ladeleistungsgrenze. Nach 90 Sekunden bzw. veralteter Leistungsmessung Kennzeichnung als zuletzt/veraltet.

Autolade-Begrenzung wird nur bei Eigenverbrauch ohne externe Steuerung und einer bestätigten verwalteten Grenze unterhalb des Ausgangswertes angezeigt; auch wenn nach Ladeende noch auf den Mindestabstand gewartet wird.

GET /api/marstek/decisions liest nur SQLite: letzte 50 Einträge aus Ladeerkennung und Steuerjournal, neueste zuerst. Browserabruf alle 15 Sekunden. Neue Bestätigungen nennen den gespeicherten Grund (Autoladen oder Wiederherstellung). Historische Einträge ohne Grund bleiben allgemein. Buttonanforderungen und geänderte Auftragszustände werden zusätzlich protokolliert; unveränderte Wartezustände erzeugen keine neuen Einträge. Fehlertexte werden für die Anzeige auf neutrale Meldungen reduziert.

Installation: `bash update-mode-log.sh`. Die Steuerregeln bleiben unverändert.

## SOC-Sicherheitsgrenze (1.21.0)

Die Entladegrenze wird zusätzlich vom aktuellen Ladestand begrenzt: über 60 %
maximal 800 W, 41–60 % maximal 300 W und bis 40 % maximal 100 W. Die gewünschte
Stufe bis 20 % verwendet vorläufig ebenfalls 100 W. Erst nachdem 0 W am realen
Marstek als wirksame Entladesperre geprüft wurde, sollte diese Stufe auf 0 W
geändert werden.

Beim fallenden Ladestand greifen die Grenzen 60, 40 und 20 % sofort. Beim Anstieg
werden die höheren Stufen erst bei 63, 43 beziehungsweise 23 % freigegeben. Eine
nötige Sicherheitsabsenkung darf den sonst geltenden 15-Minuten-Abstand
unterschreiten; jede Erhöhung hält ihn weiterhin ein. Fehlt ein höchstens 90
Sekunden alter SOC-Wert, bleibt die letzte Sicherheitsgrenze erhalten und die
Automatik erhöht die Entladeleistung nicht.

Wirksam ist immer der kleinste Wert aus Ausgangsgrenze, SOC-Sicherheitsgrenze und
gegebenenfalls Autolade-/Dauerlastziel. Dashboard und Entscheidungsprotokoll nennen
Sicherheitsstufe, wirksames Ziel und bestätigte Änderungen. Manuelle Betriebsarten
werden weiterhin nicht übernommen; dort pausiert die Automatik.

## Morgenkomfort für den Wasserkocher (historischer Stand 1.22.0, ersetzt)

Die frühere einmalige Freigabe mit Energie- und Zeitbudget wird seit 1.23.0 nicht
mehr verwendet. Die aktuelle Regel steht im folgenden Abschnitt.

## Zeit-, Prognose- und Nachtreserve-Regel (1.23.0)

Die Morgenfreigabe gilt im einstellbaren Fenster 05:00–10:00 Uhr durchgehend bis
800 W. Sie benötigt keine Lastschwelle, kein Zeitbudget und kein Energiebudget.
Bei Erreichen der einstellbaren SOC-Schutzgrenze, standardmäßig 12 %, fordert die
Automatik 0 W an. Autolade- und Dauerlastschutz bilden weiterhin das Minimum mit
der Morgenfreigabe und dürfen eine neu erforderliche Absenkung sofort schreiben.

Der Ziel-SOC für 22:00 Uhr wird berechnet als
`Schutz-SOC + Nachtbedarf × (1 + Verlustaufschlag) / Kapazität × 100`.
Mit 12 %, 1,6 kWh, 10 % und 5,12 kWh ergibt das 46,4 %. Zwischen Morgenende und
Nachtbeginn gilt unterhalb dieses Ziels höchstens die Reserveleistung. Diese
vorsichtige Grenze entfällt, wenn die verbleibende Forecast.Solar-Prognose die bis
zum Nachtziel fehlende Energie plus den einstellbaren Prognosepuffer deckt.
Fehlende oder über vier Stunden alte Prognosedaten gelten nicht als ausreichend.

SOC-Schwellen und alle vier Stufenleistungen sind einstellbar. Absenkungen folgen
den Schwellen sofort; Erhöhungen benötigen weiterhin drei Prozentpunkte Hysterese.
Manuelle/externe Betriebsarten, Konflikterkennung und Rücklesekontrolle bleiben
unverändert.

Für das Nachtfenster wird außerdem `Nachtbedarf / Nachtstunden` auf die nächste
50-W-Stufe aufgerundet. Aus 1,6 kWh und sieben Stunden entstehen 250 W. Oberhalb
der Schutzgrenze gilt nachts der größere Wert aus dieser Mindestfreigabe und der
normalen SOC-Stufe. Autolade-/Dauerlastziel und eine bereits niedrigere manuelle
Ausgangsgrenze bleiben als Minimum wirksam.

## Eigenverbrauch bis zum Ladebeginn (1.35.1)

Nach Bestätigung wird Zeitplan 6 zunächst nur eingerichtet. Bis zur gespeicherten Startzeit bleibt `user_work_mode=1` und damit der Eigenverbrauch aktiv. Erst der erste Worker-Lauf ab Start schaltet auf manuell, liest die Betriebsart zurück und kennzeichnet die Netzladung als aktiv. Das kann wegen des 30-Sekunden-Intervalls bis zu 30 Sekunden nach der geplanten Startzeit erfolgen.

Wurde das Ziel-SOC vor dem Start bereits erreicht oder ist das Zeitfenster beim nächsten Worker-Lauf vorbei, wird nicht mehr auf manuell geschaltet. Abbruch, Neustartwiederaufnahme und Fremdänderungsprüfung berücksichtigen auch den neuen Zustand `scheduled`.

## Wirtschaftlicher Netzladevorschlag mit Rest-PV (1.35.0)

Das Netzladeziel ist jetzt der kleinere Wert aus einstellbarem Maximalziel und berechneter Nachtreserve. Von der dafür fehlenden Akkuenergie werden die frische Rest-PV-Prognose abzüglich Hausgrundlast bis zum Nachtbeginn und Prognose-Sicherheitsreserve abgezogen. Deckt die Rest-PV die Reserve, entsteht kein Netzladevorschlag.

Als Vergleichswert dienen die teuren verbleibenden Tibber-Viertelstunden bis zum Ende des Morgenfensters. Aus diesem vermiedenen Bezugspreis werden Wirkungsgrad, Verschleiß und Vorteilspuffer herausgerechnet. Nur zusammenhängende Ladeviertelstunden unter dieser Wirtschaftsgrenze sind zulässig. Das Dashboard zeigt Wirtschaftsgrenze, Rest-PV und den Grund für das Ende des Fensters. Fehlende oder über vier Stunden alte Prognosedaten werden nicht als PV-Gutschrift verwendet.

## Deaktivierten Zeitplan wiederverwenden (1.34.2)

Ein deaktivierter Zeitplan 6 darf alte Werte für Wochentag, Zeit und Leistung enthalten. Für die Freigabe eines neuen Auftrags ist sein Aktivkennzeichen maßgeblich. Ein noch aktiver Zeitplan bleibt gesperrt. Vor dem Start muss der Marstek weiterhin im bestätigten Eigenverbrauch stehen.

## Fremdänderungen am Netzladeauftrag (1.34.1)

Während einer aktiven Netzladung werden Zeitplan 6 und die manuelle Betriebsart alle 30 Sekunden mit dem bestätigten Auftrag verglichen. Bei abweichender Zeit, Leistung, Aktivierung oder Betriebsart endet der Softwareauftrag mit einem Hinweis. Die Software schreibt und löscht dann nichts mehr, damit eine in der Marstek-App vorgenommene Einstellung nicht unbemerkt überschrieben wird.

## Netzladeanzeige am Akku (1.34.0)

Netzladevorschlag und Bedienung stehen unmittelbar unter dem aktuellen Akku-Status. Die Anzeige unterscheidet Vorschlag, Vorbereitung, aktive Ladung, Abbruch, Abschluss und Fehler. Während eines laufenden Auftrags wird keine zweite Bestätigung angeboten; sichtbar bleiben Ladeleistung, Ziel-SOC, Endzeit und der reservierte Zeitplan 6. Das Kostenmodell darunter bleibt eine reine Beobachtungsanzeige.

## Fehlerkorrektur 1.33.1

Die Zeitplan-Abfrage importiert den Modbus-Leser jetzt im Gerätepfad. Version 1.33.0 konnte deshalb nach dem Aufruf der Netzladeverarbeitung wiederholt neu starten. Ein eigener Test prüft die vollständige Abfrage von Zeitplan 6.

## Bestätigte Netzladung über Zeitplan 6 (1.33.0)

`grid_charging.py` sucht unabhängig vom End-SOC des Beobachtungsplans das günstigste zusammenhängende,
noch heute liegende Tibber-Netzladefenster, sofern der aktuelle SOC unter der einstellbaren
Schwelle liegt. Das Dashboard zeigt Zeitraum, Ladeleistung, mittleren Preis und
Ziel-SOC. Eine ausdrückliche Bestätigung wird mit dem vollständigen Vorschlag in
`grid_charge_requests` gespeichert.

Nur nach einer neuen ausdrücklichen Bestätigung schreibt der exklusive Marstek-Worker Zeitplan 6 und wechselt in den manuellen Modus. Alte Testbestätigungen werden nie ausgeführt. Vorher werden Leerzustand, Eigenverbrauch, freigegebene RS485-Steuerung und Überschneidungen mit den App-Zeitplänen 1 bis 5 geprüft. Jeder Wert wird zurückgelesen. Am Ziel-SOC, an der Endzeit oder nach Abbruch wird zuerst Eigenverbrauch bestätigt und danach Zeitplan 6 vollständig geleert. Bei Pi- oder WLAN-Ausfall beendet die im Gerät gespeicherte Endzeit die Ladung; die Rückkehr zum Eigenverbrauch wird nach Wiederkehr nachgeholt.

Die voreingestellten 500 W sind eine vorsichtige Leistung für den ersten
beaufsichtigten Schreibtest. Unter Einstellungen kann die spätere Ladeleistung in
50-W-Schritten bis 2.500 W geändert werden. Bestätigungszustand und berechneter
Vorschlag werden im Dashboard gleichzeitig angezeigt.

## Manueller Ladeauftrag (1.47.0)

Der Button „Laden“ in der Marstek-Kachel ersetzt den früher automatisch berechneten
Netzladevorschlag. Der Benutzer wählt Start, Energiemenge oder Dauer und Ladeleistung.
Eine serverseitige Vorschau zeigt den erwarteten SOC, die Netz- und Akkuenergie sowie
verfügbare Tibber-Kosten. Ohne anschließenden ausdrücklichen Auftrag wird nichts am
Gerät verändert.

„Jetzt“ bedeutet den nächsten sicheren Viertelstundenbeginn. Alternativ sind eine
Verzögerung oder ein konkretes Datum mit Uhrzeit innerhalb der nächsten 24 Stunden
möglich. Zeitplan 6, Startprüfung, Rücklesen, Abbruch und Rückkehr zum Eigenverbrauch
bleiben erhalten. Ein bereits vor dem Update laufender Auftrag wird regulär beendet.

Seit Version 1.47.1 beginnt „Jetzt“ beim nächsten Worker-Durchlauf statt am nächsten
Viertel. Der Start kann dadurch bis zu etwa 30 Sekunden nach dem Tastendruck erfolgen.

Version 1.47.2 ergänzt den Neustart von `marstek-battery` im Dashboard-Update. Damit
wird das Steuerformat manueller Ladeaufträge nach der Installation sofort geladen.

Version 1.47.3 vergrößert die Bedienziele für Dauer und Leistung. Große Schritttasten
und fünf Leistungsstufen erleichtern die Bedienung auf iPad und Smartphone.

## Sichtbare Ladezeiten (1.48.0)

Die Marstek-Kachel und der Ladedialog zeigen bei geplanten Aufträgen Start und Ende.
Nach bestätigtem Wechsel in den manuellen Modus erscheinen tatsächlicher Start,
voraussichtliches Ende und Restzeit. Der Ladebutton bildet den Auftragszustand ab und
öffnet in jedem Zustand denselben Dialog mit Abbruchmöglichkeit.

## Energiemenge per Schritttaste (1.48.1)

Für das Ladeziel „Energiemenge“ stehen große Minus- und Plus-Tasten mit 0,1 kWh
Schrittweite bereit. Das Zahlenfeld bleibt frei editierbar. Der Ladebutton in der
Marstek-Kachel besitzt dieselbe gerahmte Touch-Darstellung wie der Wolkenkartenbutton.
