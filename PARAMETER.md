# Parameter

Stand 1.23.0. Diese Werte sind Programmvorgaben, nicht die ausgelesenen aktuellen Pi-Einstellungen. Aktuelle Werte stehen im Dashboard unter Einstellungen. Die Akku-Grenze ist zusätzlich über den Regler in der Marstek-Karte änderbar; beide Oberflächen verwenden denselben gespeicherten Wert.

| Parameter | Vorgabe | Erlaubt | Wirkung |
|---|---|---|---|
| Startschwelle (`block_above_w`) | 2000 W | größer als Endschwelle, höchstens 100.000 W | Strikt darüber startet anhand von Netzbezug plus Akku-Abgabe die Bestätigungszeit. |
| Endschwelle (`release_below_w`) | 1000 W | 0 bis unter Startschwelle | Strikt darunter startet anhand derselben korrigierten Leistung die Bestätigungszeit für das Ende. |
| Bestätigungsdauer (`hold_seconds`) | 180 s | 1–3600 s | Gilt für Beginn und Ende; kurze Überschreitungen reichen nicht. |
| Dauerlastschutz-Leistung (`sustained_discharge_w`) | 750 W | 50–800 ganze W | Ab dieser Marstek-AC-Abgabe läuft unabhängig von der Startschwelle die Schutzfrist. |
| Dauerlastschutz-Dauer (`sustained_discharge_seconds`) | 600 s | 60–3600 ganze s | Nach durchgängiger hoher Akku-Abgabe wird die Entladegrenze gesetzt. |
| Maximale Messlücke (`max_gap_seconds`) | 15 s | mindestens 2 × Abfrageintervall, höchstens 3600 s | Größere Lücken setzen eine laufende Prüfung zurück; bei 5-s-Abfrage mindestens 10 s. |
| Marstek-Mindestabstand (`marstek_interval_seconds`) | 900 s / 15 min | 60–86.400 s / 1–1440 min | Mindestabstand zwischen allen Entladegrenzen-Schreibversuchen einschließlich Rücksetzung; keine Wirkung auf Messabfragen. |
| Einspeisevergütung (`feed_in_ct`) | 9 ct/kWh | 0–100 ct/kWh | Vergleichslinie und Preiskennzeichnung, auch rückwirkend mit dem aktuellen Wert. |
| Hausgrundlast (`base_load_w`) | 160 W | 0–10.000 W | Wird von der PV-Prognose abgezogen; keine laufend gemessene Grundlast. |
| Angenommener Ladestrom (`ev_current_a`) | 5 A | 1–32 A | Nur PV-Fenster: Ladeleistung = 3 × 230 V × Strom. Kein Befehl an NRGkick; Wertebereich keine Freigabe eines realen Ladestroms. |
| Lüfterlaufzeit (`fan_minutes`) | 20 min | 1–120 ganze Minuten | Gilt für den nächsten Start/Timerneustart, verändert eine laufende Frist nicht. |

| Akku-Grenze bei Autoladen (`ev_discharge_limit_w`) | 200 W | 0–800 W in 50-W-Schritten | Höchstens diese Entladeleistung bei bestätigtem Autoladen oder Dauerlastschutz; danach vorherige Grenze wiederherstellen. |

Der Regler verändert beim Schieben zunächst nur seinen Entwurf. Erst `Übernehmen`
speichert den Wert und protokolliert die Änderung. Ohne aktiven Schutz wird kein
Geräteregister geschrieben. Bei bereits aktivem Schutz übernimmt der Marstek-Worker
das neue Ziel unter Beachtung des eingestellten Mindestabstands. Die separat
angezeigte aktuelle Entladegrenze stammt weiterhin aus dem Gerät.

## Feste SOC-Sicherheitsstufen

Die SOC-Sicherung ist derzeit kein veränderbarer Parameter. Über 60 % gelten 800 W,
von 41 bis 60 % 300 W und bis 40 % 100 W. Auch bis 20 % bleiben vorläufig 100 W,
bis eine Entladegrenze von 0 W am realen Gerät geprüft wurde. Beim steigenden SOC
werden die Stufen erst bei 23, 43 und 63 % freigegeben. Der wirksame Zielwert ist
das Minimum aus dieser Grenze, der vorherigen Gerätefreigabe und dem Ziel bei
Autoladen oder Dauerlastschutz.

Gespeichert wird in `preferences`; Änderungen mit alten/neuen Werten in `preference_changes`. Der Collector übernimmt Erkennungsänderungen im nächsten Messzyklus, behält den bestätigten Zustand und beginnt eine laufende Prüfung neu. Gleichheit mit einer Schwelle erfüllt weder die Start- noch die Endbedingung.

## Weitere Einstellungen

`config.toml`: Shelly-IP aus der lokalen `config.toml`, Abfrage alle 5 s, HTTP-Timeout 3 s, Datenbank `data/measurements.db`. Relative Datenbankpfade beziehen sich auf den Konfigurationsordner. `MARSTEK_CONFIG` kann einen anderen Konfigurationspfad wählen. Änderungen erfordern einen Neustart betroffener Prozesse. `[high_load]` gehört zum alten Testmonitor; die Dashboard-Regeln kommen aus SQLite.

`forecast.toml`: Standort, 7 kWp, Südorientierung und 43° Neigung. Winkelkonvention des API-Anbieters beachten, nicht ungeprüft 180° als API-Azimut einsetzen. `secrets.toml`: Zugangsdaten SolarEdge, Tibber und Meross; nicht mit Code verteilen.

Nicht im Einstellungsdialog: Aktualisierungs-/Cloud-Zeitpläne, 30 Tage Rohdatenhaltung, sieben Sicherungen, Frist für veraltete Anzeigen und Webserver-Port. Änderungen daran sind Code-/Dienständerungen und benötigen eigene Prüfung.

## PV-Fenster

Mit Vorgaben: 160 W + 3 × 230 V × 5 A = 3610 W PV-Schwelle. Die Prognose muss während der ganzen Viertelstunde darüber liegen. Das Band ist eine Prognose, kein Ladungsnachweis. Es wird aus dem letzten gespeicherten Prognosestand des Tages und aktuellen Parametern neu berechnet, nicht als damalige Ja/Nein-Entscheidung gespeichert.


## Kosten-Beobachtung (1.15.0)

Nur Simulation: Plan ein/aus; Netzladen im Plan ja/nein; Kapazität 5,12 kWh (1–30); Mindest-/Maximal-SOC 20/95 %; Endreserve 20 %; Gesamtwirkungsgrad 85 % (50–100); Verschleiß 2 und Vorteilspuffer 3 ct/kWh (je 0–50); PV-Abschlag 20 % (0–100); angenommener Hausverbrauch 160 W (0–10000); Ladeleistung 2500 W (0–2500), Entladeleistung 800 W (0–800); Horizont 24 Stunden (1–36). Einspeisevergütung aus bestehendem Parameter. Neue Werte gelten beim nächsten 15-Minuten-Planlauf. Endladestand mindestens Startladestand/Endreserve. Siehe BEOBACHTUNG.md.


## PV-/Akku-Diagramm (1.16.1)

`forecast_start_hour`: Vorgabe 5, ganze Stunden 0–23. `forecast_end_hour`: Vorgabe 23, ganze Stunden 1–24. Beginn muss vor Ende liegen. Feste Zeitachse des ausgewählten Tages in Europe/Berlin statt automatischer Bereichswahl; Speichern aktualisiert die Anzeige sofort. Tageserträge, Prognosekarten, Erfassungszeiten und gespeicherte Daten bleiben unverändert. Wetter-Popup und andere Diagramme verwenden weiterhin ihre eigenen Zeitachsen.

## Morgenkomfort (historischer Stand 1.22.0, durch 1.23.0 ersetzt)

Die einmalige Auslösung mit Zeit- und Energiebudget wird nicht mehr verwendet.

## Akku-Zeitregel und Nachtreserve (1.23.0)

| Parameter | Vorgabe | Bereich / Wirkung |
|---|---:|---|
| Morgenfreigabe | Ein | Aktiviert die durchgehende Zeitfreigabe. |
| Morgenzeit | 05:00–10:00 | Ganze Stunden; volle Freigabe bis zur Schutzgrenze. |
| Morgenleistung | 800 W | 100–800 W in 50-W-Schritten. |
| SOC-Schutzgrenze | 12 % | 11–30 %; bei Erreichen 0 W. |
| Nachtbeginn | 22:00 | Ganze Stunde nach dem Morgenende. |
| Nachtbedarf | 1,6 kWh | 0–10 kWh. |
| Verlustaufschlag | 10 % | 0–30 %. |
| Prognosepuffer | 1,0 kWh | 0–10 kWh zusätzlich zur fehlenden Nachtreserve. |
| SOC-Schwellen | 60/40/20 % | Aufsteigend über der Schutzgrenze. |
| SOC-Leistungen | 800/300/100/100 W | Je 0–800 W in 50-W-Schritten. |

Der Ziel-SOC zum Nachtbeginn wird mit der Kapazität aus dem Kostenplan berechnet.
Bei den Vorgaben 5,12 kWh Kapazität, 1,6 kWh Bedarf, 10 % Aufschlag und 12 %
Schutzgrenze sind es rund 46,4 %. Autoladen und Dauerlast verwenden unabhängig
davon den gemeinsamen Parameter `ev_discharge_limit_w` und haben Vorrang.

Die Nachtleistung wird aus Bedarf und Zeitfenster berechnet und auf 50 W
aufgerundet. Mit 1,6 kWh von 22:00 bis 05:00 Uhr sind das 250 W. Diese
Mindestfreigabe gilt nur oberhalb der SOC-Schutzgrenze und kann durch aktiven
Autolade-/Dauerlastschutz weiter reduziert werden.
