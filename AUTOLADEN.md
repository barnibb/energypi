# Autolade-Erkennung

Der Collector wertet alle fünf Sekunden den saldierten Netzbezug des Shelly aus und
addiert eine höchstens 90 Sekunden alte, positive Marstek-AC-Abgabe. Dadurch ergibt
sich die Erkennungsleistung:

`Erkennungsleistung = Netzbezug + Akku-Abgabe`

- Durchgehend über 2.000 W Erkennungsleistung für 180 Sekunden: Autoladen vermutet.
- Alternativ mindestens 750 W Akku-Abgabe für 600 Sekunden: Dauerlastschutz aktiv.
- Danach durchgehend unter 1.000 W Erkennungsleistung für 180 Sekunden: Schutz beendet.
- Dazwischen bleibt der bisherige Zustand erhalten. Die Grenzwerte selbst erfüllen die jeweilige Bedingung nicht.

Dies sind Vorgaben; die aktuellen Werte stehen in den Dashboard-Einstellungen (SQLite preferences). Fehlende Messwerte oder Lücken über 15 Sekunden setzen die laufende Prüfzeit zurück. Nach einem Neustart bleibt die letzte Einschätzung gespeichert, aber eine laufende Prüfzeit beginnt neu. Ohne gültige aktuelle Messung zeigt das Dashboard einen unbekannten Status; nach 20 Sekunden ohne Aktualisierung ebenfalls.

Das ist eine Schätzung, keine Messung des Ladeanschlusses. Andere große Verbraucher
können beide Wege auslösen. Die Addition der Akku-Abgabe verhindert, dass eine
Entladung von beispielsweise 800 W die Startschwelle verdeckt. PV-Erzeugung kann die
Erkennungsleistung weiterhin verringern; dafür dient der unabhängige Dauerlastschutz.
Fehlt ein aktueller Marstek-Wert, läuft die Lastregel nur mit dem Netzbezug weiter und
der Dauerlastschutz kann nicht neu auslösen.

SQLite enthält zusätzlich:
- charging_state: letzter Zustand, Auslösegrund, Netz-, Akku- und korrigierte Leistung, laufende Prüfung, Restfrist und verwendete Schwellen.
- charging_events: bestätigte Start-/Endwechsel mit Bestätigungszeit, Beginn und Grund der auslösenden Bedingung, korrigierter Leistung und verwendeten Schwellen.

Die vorhandenen Shelly-Messreihen bleiben erhalten. Ereignisse werden dauerhaft gespeichert und sind in der bestehenden Sicherung der gesamten Datenbank enthalten. /api/charging liefert den aktuellen Zustand und die letzten zehn Ereignisse. Eine eigene historische Ereignisansicht ist noch nicht enthalten. Erfasste Zeitpunkte sind Schätzungen; Messlücken beweisen keine durchgängige Ladung. Es werden keine Befehle an den Marstek oder das Auto gesendet.

Installation vom Mac: bash update-charging.sh. Danach das Dashboard neu laden. Beide Pi-Dienste werden beim Update neu gestartet.

## Einstellungen ab 1.5.0

Der Dashboard-Button Einstellungen speicherte zunächst sechs Parameter in SQLite: Start-/Endschwelle (Vorgabe 2.000/1.000 W), Bestätigungsdauer (180 s), Messlücke (15 s), vorbereiteter Marstek-Abstand (900 s) und Einspeisevergütung (9 ct/kWh). Diese Einstellungen haben im Collector Vorrang vor high_load in config.toml. Das alte main.py bleibt ein separater Konfigurations-basierter Testmonitor.

Erkennungsänderungen werden beim nächsten Messzyklus übernommen, mit neuer Prüfzeit und unverändertem bestätigtem Zustand. preferences speichert die Werte, preference_changes Zeitpunkt und alte/neue Werte. Die Sicherung enthält beide Tabellen. Die Marstek-Steuerung ist noch nicht angebunden; ihr Abstand wird nur vorbereitet. Die Vergütung wird auch auf historischen Diagrammen als aktueller Vergleichswert genutzt. Zugriff auf Einstellungen erfolgt über die lokale Oberfläche ohne Benutzeranmeldung.

Die beiden Parameter des Dauerlastschutzes stehen ebenfalls im Einstellungsdialog;
vollständige Referenz in [PARAMETER.md](PARAMETER.md).

Ab Version 1.23.0 haben Autolade- und Dauerlastschutz Vorrang vor Morgenfreigabe,
PV-Prognose und Nachtreserve. Eine neu erforderliche niedrigere Schutzgrenze darf
sofort geschrieben werden; Wiederherstellungen und Erhöhungen beachten weiterhin
den einstellbaren Marstek-Mindestabstand. Die Schutzarten verwenden gemeinsam
`ev_discharge_limit_w`.

Ab Version 1.20.0 kann die gemeinsame Zielgrenze zusätzlich über den Schieberegler
rechts neben dem Akku-Ladestand gewählt werden. Erst `Übernehmen` speichert den Wert.
Regler und Einstellungsdialog bearbeiten denselben Parameter; die tatsächlich am
Gerät gelesene Entladegrenze bleibt eine getrennte Anzeige.
