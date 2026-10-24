# Kosten-Beobachtung 1.15.0

Der neue Bereich steht ganz unten unter dem Entscheidungsprotokoll. Er simuliert Akku-Bewirtschaftung und sendet keinerlei Gerätebefehle. Die bestehende Autolade-Begrenzung bleibt unabhängig davon aktiv. „Netzladen erlauben“ ist ausschließlich eine Erlaubnis innerhalb der Simulation. Manuelle Vorgaben am Gerät werden vom Plan nicht ausgeführt oder aufgehoben.

## Berechnung

Dynamische Programmierung mit Energiezuständen in 0,02-kWh-Schritten, Startzustand zusätzlich exakt. Viertelstunden ab der nächsten vollen Viertelstunde, maximal 36 Stunden. Verwendet nur vorhandene EUR-Tibber-Gesamtpreise, gespeicherte Forecast.Solar-Energieprognosen und einen höchstens 90 Sekunden alten Akku-Ladestand. Kein Netzaufruf im Planer. Preis- oder Prognoselücken kürzen den Horizont; mindestens vier zusammenhängende Viertelstunden erforderlich. Prognosen über 24 Stunden werden nicht genutzt, über sechs Stunden als unsicher gekennzeichnet.

PV-Energie aus interpoliertem kumuliertem Prognoseertrag abzüglich Sicherheitsabschlag. Hausverbrauch zunächst konstant aus dem Einstellwert (160 W Vorgabe), kein gelerntes Lastprofil; Autoverbrauch nicht prognostiziert. Aktuell erkanntes Autoladen begrenzt vorsorglich die simulierte Entladeleistung für den gesamten Plan.

Zielfunktion je Viertelstunde: Netzbezug × Tibber-Preis − Einspeisung × Vergütung + Akku-Abgabe × (Verschleißansatz + Vorteilspuffer). Kostenanzeige enthält Verschleiß, jedoch nicht den fiktiven Vorteilspuffer. Positive Akkuladung und Entladung sind gegenseitig ausgeschlossen. Keine gezielte Akku-Einspeisung: Entladung höchstens bis zum angenommenen Hausdefizit. Netzladen kann separat ausgeschlossen werden. Gesamtwirkungsgrad wird symmetrisch auf Laden und Entladen verteilt. Bereits unter Mindestreserve liegender Akku darf nicht weiter entladen werden; bereits über maximalem SOC liegender Akku wird nicht weiter geladen.

Endenergie mindestens Startenergie bzw. Endreserve. So wird vorhandene Akkuladung nicht als kostenloser einmaliger Vorteil aufgebraucht. Diese konservative Randbedingung kann wirtschaftlich sinnvolle Entladung über den Planungshorizont hinaus zurückhalten. Es wird kein angeblich garantierter Sparbetrag gegenüber dem realen Betrieb ausgewiesen.

5,12 kWh Kapazität, 85 % Wirkungsgrad und 2 ct/kWh Verschleiß sind veränderbare Modellannahmen, keine im Projekt gemessenen Geräteeigenschaften. Leistungsspezifische Verluste/Standbyverbrauch, dynamisches Verbrauchsprofil und ein Steuer-Mindestabstand über 15 Minuten sind noch nicht modelliert. Bei längerem konfiguriertem Mindestabstand erscheint ein Hinweis. Ergebnisse sind Vorschläge innerhalb dieses Modells, kein automatisch ausführbarer Betriebsplan.

## Speicherung und Betrieb

`observation_plans`: Zeitstempel und JSON mit Parametern, Eingangs-Ladestand/Zeit, Prognoseständen, Viertelstundenpreisen, angenommener Last/PV, Plan und Hinweisen. Dauerhaft gespeichert, etwa 96 Pläne/Tag, inklusive SQLite-Sicherung. Planungsannahmen in `preferences`, Änderungen im vorhandenen Änderungsjournal. Keine Änderungen an Gerätebefehlen.

`marstek-observer.timer`: alle 15 Minuten. `marstek-observer.service` als separater, netzwerkisolierter Prozess (`PrivateNetwork=true`), bis 180 Sekunden Laufzeit. Webendpunkt `/api/observation-plan` liest nur den letzten gespeicherten Plan. Über 20 Minuten alter Plan und geänderte Einstellungen werden markiert. Neue Parameter gelten beim nächsten Timerlauf. Ausschalten blendet den Plan unmittelbar aus; der Timer kann weiterhin einen deaktivierten Status speichern.

Installation auf vorhandener 1.14.0: `bash update-observer.sh`.

Pi-Diagnose:

```sh
systemctl status marstek-observer.timer --no-pager
journalctl -u marstek-observer.service -n 20 --no-pager
```

Bei Datenbank-Wiederherstellung zusätzlich Observer-Timer und -Service stoppen. Bestehende historische Messwerte werden weder geändert noch nachgebildet.
