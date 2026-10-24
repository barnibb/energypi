# PV-Prognose und SolarEdge-Tagesertrag

## Update auf dem Mac starten

```sh
cd /PFAD/ZU/marstek-control
bash update-forecast.sh
```

Passwörter direkt im Terminal eingeben. Das Update überträgt keine Datenbanken
oder Zugangsdaten. Bestehende secrets.toml und config.toml bleiben erhalten.
forecast.toml enthält die neue Anlagenkonfiguration. Webdienst wird neu gestartet,
SolarEdge- und Forecast-Timer werden eingerichtet bzw. aktiviert.

Dashboard: http://RASPBERRY_PI_IP:8080 — anschließend Seite neu laden.
SolarEdge-Key und Standort-ID bleiben in secrets.toml auf dem Pi (siehe SOLAREDGE.md).
Forecast.Solar benötigt keinen Schlüssel. Ohne SolarEdge-Zugang zeigt die Prognose
bereits Werte, der Tagesertrag bleibt ausdrücklich unbekannt.

## Anlage

Name, Koordinaten, Spitzenleistung, Neigung und Kompassazimut stammen aus der lokalen `forecast.toml` und werden nicht veröffentlicht. Forecast.Solar verwendet Süd=0°; die Anwendung rechnet deshalb das eingetragene Kompassazimut intern um. Die Ortskoordinaten müssen keine genaue Dachposition sein und können später in `forecast.toml` angepasst werden.
Verschattung und besondere Wechselrichterbegrenzungen sind nicht individuell
modelliert. Daher zunächst beobachten, noch keine Akkusteuerung aus Prognosen.

## Darstellung

- Karten: Prognose heute, ab jetzt verbleibende Erzeugung, Prognose morgen (kWh).
- Datumsauswahl mit Heute/Morgen und archivierten Tagen.
- Gestrichelte PV-Prognose und durchgezogene SolarEdge-Istleistung (kW).
- Maus/Berührung zeigt Zeit und Wert; Messlücken bleiben sichtbar.
- Tagesertrag für das ausgewählte Datum aus SolarEdge /energy?timeUnit=DAY.
- Heutiger Ertrag ist der bisher gemeldete, nicht der abgeschlossene Tageswert.
- Abrufzeitpunkte und veraltete/fehlende Daten werden gekennzeichnet.

Die Karten bleiben auf heute/morgen bezogen, auch wenn im Diagramm ein historischer
Tag ausgewählt wird. Alte Prognosestände werden gespeichert; im Diagramm wird
jeweils der zuletzt erfolgreich gespeicherte Stand für den Tag gezeigt. Auswahl
eines bestimmten Vorabend-Prognosestands ist noch nicht Teil der Oberfläche.

Verbleibende Energie wird aus der kumulierten Forecast.Solar-Energie durch zeitliche
Interpolation bestimmt, nicht durch Abziehen des SolarEdge-Ertrags. Sie bezeichnet
Erzeugung, keinen Überschuss nach Hausverbrauch oder E-Auto-Ladung.
SolarEdge-Istleistung hat nur den Cloud-Abrufzeitpunkt und kann zeitlich verzögert
sein; ein punktgenauer Vergleich mit der Prognose ist deshalb eingeschränkt.

## Abrufe und Limits

Forecast.Solar: täglich 06, 08, 10, 12, 14, 16, 18, 20 und 22 Uhr Europe/Berlin.
Neun planmäßige Abrufe/Tag. Start-/Nachholabrufe sind möglich; persistierte
Zweistundenfenster verhindern Abrufschleifen. Fehler warten auf den nächsten Slot.

SolarEdge-Leistungsfluss: weiterhin maximal 54 Abrufe zwischen 07:30 und 20:45.
SolarEdge-Energie: einmal pro Stunde ganztägig. Ein Request holt heute und die
vorherigen sieben Tage, damit auch nachträgliche Meldungen berücksichtigt werden.
An einem normalen Tag insgesamt bis zu 78 SolarEdge-Aufrufe (bei Zeitumstellung
auf Winterzeit bis zu 79). Weitere Anwendungen zählen zusätzlich zum API-Limit.
Browseraufrufe verursachen keine externen API-Anfragen.

Wh werden durch 1000 in kWh umgerechnet. Fehlende/null-Werte werden nicht als null
kWh gespeichert und überschreiben keinen vorhandenen Tageswert. Der letzte
bekannte Stand behält seinen alten Abrufzeitpunkt.

## Datenbank und Sicherungen

forecast_runs: Abrufzeit/Fehler je Versuch.
forecast_days: normalisierte Tageskurven und Ertrag je Prognosestand.
solaredge_energy: neuester gemeldeter Tagesertrag und Abrufzeit je Datum.
energy_attempts: Abrufslots und bereinigte Fehler.
Alle Tabellen liegen in measurements.db und sind in den SQLite-Sicherungen enthalten.
Prognosen bleiben versioniert erhalten; Energie-Tageswerte werden bei Revision ersetzt.

## Prüfen

```sh
systemctl list-timers marstek-forecast.timer marstek-solaredge.timer --no-pager
journalctl -u marstek-forecast.service -u marstek-solaredge.service -n 20 --no-pager
```

Lokale Prüfungen: 23 Python-Tests, Forecast.Solar-Liveantwort und HTTP-Dashboard-API.
SolarEdge-Energie wurde mangels Zugangsdaten mit Testantworten geprüft.
Visuelle Browserprüfung war beim Aufbau durch die Browseranbindung blockiert.

Quellen:
- https://forecast.solar/index.html
- https://knowledge-center.solaredge.com/sites/kc/files/se_monitoring_api.pdf
- https://www.wikidata.org/wiki/Q635197 (Ortskoordinaten)

## Windy-Karte

Neben der PV-Prognose öffnet „Windy · Wolkenkarte“ ein Dialogfenster mit der externen ECMWF-Wolkenkarte (54.269 / 9.782, Zoom 7). Die Karte lädt erst beim Klick. Schließen ist per Schaltfläche, Escape oder Klick außerhalb möglich. Auf kleinen Bildschirmen passt sich das Fenster an. Die gespeicherte PV-Prognose wird nicht verändert.

## Einstellbare PV-Schwelle (1.6.0)

Die Dashboard-Einstellungen enthalten Hausgrundlast in W (Standard 160) und dreiphasigen Ladestrom in A (Standard 5). Die Schwelle berechnet sich aus Grundlast + 3 × 230 V × Ladestrom. Vorschau, Beschriftung, Überschuss und gelbes Band verwenden dieselben Werte. Diese Einstellung steuert kein Fahrzeug. Bereits gespeicherte Einstellungen werden um fehlende Standardwerte ergänzt, ohne vorhandene Werte zu überschreiben. Historische Diagramme verwenden die aktuellen Einstellungen.

## Anordnung ab 1.7.2

SolarEdge-Tagesertrag heute steht hervorgehoben über Prognose heute und Prognose morgen. Die Restprognose steht bei heute. Die oberen Werte sind unabhängig von der Diagramm-Datumsauswahl; gewählte andere Tage zeigen ihren Ertrag direkt am Diagramm. Der zusätzliche today_energy-Wert wird nur aus der lokalen Datenbank gelesen, ohne zusätzliche Cloud-Abfrage.
