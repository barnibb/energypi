# Betrieb und Wiederherstellung

Stand 1.9.0, 18.09.2026. Dokumentierter Anlagenstand aus der Einrichtung; keine erneute Live-Inventur des Pi.

## Anlage

| Komponente | Rolle |
|---|---|
| Raspberry Pi 3 Model B Rev 1.2 | Debian 13, Python 3.13, lokale Adresse und Benutzer aus `deploy-local.env` |
| Shelly Pro 3EM, Adresse aus `config.toml` | Gesamt-Netzfluss und Phasenmessung alle 5 Sekunden |
| SolarEdge SE7K | Dreiphasige PV, 7 kWp, Süd 180°, Neigung 43°; Cloud-Leistung und Tagesertrag |
| Marstek Venus E V2 | Laut Nutzer auf Phase A; bisher Eigenregelung über Shelly, keine EnergyPi-Anbindung |
| NRGkick | Dreiphasiges Autoladen, keine direkte Datenverbindung; heuristische Erkennung |
| Meross MSS210 „Lüfter Bad“ | Zeitgesteuerte Schaltanforderung über Cloud, Dienst auf Pi |
| Tibber / Forecast.Solar | Preise / Prognose; keine Garantie für tatsächlichen PV-Überschuss |

SolarEdge beeinflusst alle drei Phasen, der Akku direkt nur A. Aus Phase A allein lässt sich Akkuleistung nicht trennen. B/C können Hinweise auf dreiphasige Lasten liefern, aber PV-Änderungen wirken ebenfalls darauf. Eine Phasen-basierte Autoerkennung ist nicht implementiert. Der kommende Daikin-Anschluss ist Planung, keine aktuelle Funktion.

## Marstek-Kabel: nur dokumentierter Arbeitsstand

Vom Nutzer genannte Adern: Pin 1 Rot, 2 Gelb, 3 Weiß, 4 Schwarz, 5 blank. Es liegen noch keine bestätigten Spannungsmessungen und kein erfolgreicher Modbus-Lesetest vor. Diese Liste ist keine Freigabe der Signalbelegung. Gefundene Zeichnungen verwenden unterschiedliche Zählweisen/GND-Zuordnungen; keine unbestätigte Löttabelle als gesichert übernehmen. Blankes Ende einzeln isolieren. Elfin-EW11A vorhanden, Versorgung laut Typenschild 5–36 V; Marstek-Ausgangsstrom nicht bestätigt. IP, Betriebsart und Anschlussprüfung des Elfin sind noch offen.

Vor tatsächlicher Akkusteuerung: geprüften Anschlussplan, Hardware/Firmware, Modbus-Parameter, Register und Vorzeichen dokumentieren. Erst lesen, dann eine begrenzte Schreibprüfung. Zuständigkeit gegenüber Marstek-Eigenregelung klären. 15-Minuten-Abstand ist bislang nur ein gespeicherter Parameter, kein aktiver Schutzmechanismus.

## Dienste und Diagnose auf dem Pi

```sh
systemctl status marstek-collector marstek-web marstek-fan --no-pager
systemctl list-timers 'marstek-*' --no-pager
journalctl -u marstek-collector -u marstek-web -u marstek-fan -n 60 --no-pager
df -h /
timedatectl
```

Dauerläufer: Collector, Webserver, Lüfter. Timer: SolarEdge alle 15 Minuten (Code begrenzt Leistungsabrufe tagsüber; Tagesenergie stündlich), Tibber stündlich nach Bedarf, Prognose zweistündlich 06–22 Uhr, Wartung 03:15 Uhr mit Zufallsverzögerung. Ein erfolgreich beendeter `oneshot`-Cloud-Dienst darf „inactive“ sein; entscheidend sind Timer, Exitstatus und letzter Datenabruf.

| Symptom | Erste Prüfung |
|---|---|
| Keine aktuellen Messwerte | Shelly erreichbar? `curl --max-time 5 'http://SHELLY_IP/rpc/EM.GetStatus?id=0'`; Collector-Log |
| Weboberfläche nicht erreichbar | WLAN/IP, `systemctl status marstek-web`, Port 8080 |
| Tageswechsel Tibber verzögert | Version mindestens 1.8.4, Browser vollständig neu laden; bei Fortbestand API-/Browserfehler untersuchen |
| PV-Band verändert sich rückwirkend | Neueste gespeicherte Tagesprognose plus aktuelle Parameter; keine damalige Entscheidung gespeichert |
| SolarEdge fehlt | Dienstlog, secrets.toml lokal prüfen, Kontingent/HTTP-Status; keine schnellen Wiederholungsserien |
| Lüfter nicht bereit | marstek-fan-Log; bei DNS-Fehlern Systemauflösung prüfen, siehe MEROSS.md |
| Mac-Sicherung fehlgeschlagen/überfällig | `automatic-error.log` prüfen. Der Runner hält den Mac während der Übertragung wach, komprimiert den SSH-Datenstrom und wiederholt einen abgebrochenen Transfer einmal. Der Fehlerzeitpunkt und der letzte Erfolg sind getrennte Angaben. |

Netzausfall/WLAN-Lücke: keine Nullwerte erfinden, laufende Erkennungsfrist wird zurückgesetzt. Pi-Neustart: bestätigte Ladevermutung bleibt, Frist startet neu. Meross-Ausfall: Abschaltung kann verzögert werden, siehe MEROSS.md. Marstek arbeitet bisher unabhängig von EnergyPi weiter.

## Updates und Rückkehr

Entwicklung am Mac; Update-Skript dort im Projekt ausführen. Skripte übertragen Dateien per SSH/rsync und benötigen gegebenenfalls Passwort. `deploy-to-pi.sh` ist die Basisinstallation und überträgt auch config.toml; gezielte Updates sind für Einzeländerungen vorgesehen. Daten, secrets.toml und virtuelle Umgebung werden vom vollständigen Deployment ausgeschlossen. Zusatzdienste werden separat eingerichtet.

Vor größeren Updates geprüfte DB-Sicherung und Kopie des bisherigen Codes einschließlich Konfiguration behalten. Die Rollback-Kopie darf secrets.toml nur geschützt enthalten. Nach Update Version im Browser und Dienststatus prüfen. Bei reinem Webfehler vorherige zusammengehörige Programmdateien zurückspielen und Webdienst neu starten. Bei geänderter Datenbankstruktur nicht blind alten Code mit neuer DB kombinieren: passendes Code/DB-Paar wiederherstellen. Kein automatisches Rollback vorhanden.

## Sicherungsumfang

Aktuelle automatische Mac-Sicherungen: `~/Library/Application Support/EnergyPi/backups/`. Dort `automatic.log` und `automatic-error.log`. Runner: benachbart `run-backup.sh`, geplant 04:15 Uhr. Sieben erfolgreiche Datenbankkopien; bei schlafendem Mac nach Aufwachen, sofern angemeldet und Pi erreichbar. Sobald ein Lauf begonnen hat, hält er den Mac bis zum Abschluss wach. SSH komprimiert die Übertragung, die gespeicherte Datei bleibt eine normale SQLite-Datenbank. Ein abgebrochener Transfer wird einmal neu begonnen. Pi-Snapshots: `/home/pi/marstek-control/data/backups/`.

Separat sichern: Projektcode, config.toml, forecast.toml, geschützte secrets.toml, eigene Dienstanpassungen und Wiederherstellungszugang. Die Datenbankkopie ersetzt diese Dateien nicht. Fehlende SSH-Sicherungsschlüssel lassen sich neu einrichten. Keine Passwörter oder Tokens in Fehlerberichte kopieren.

## Wiederherstellung einer Datenbank auf bestehendem Pi

Diese Schritte verändern Daten und sind eine Anleitung, keine bereits ausgeführte Wiederherstellung. Zuerst eine konkrete Sicherung auswählen, auf den Pi z. B. als `/home/pi/restore.sqlite3` übertragen und prüfen. Bei abweichendem konfiguriertem DB-Pfad die Anleitung entsprechend anpassen. Währenddessen keinen Mac-Sicherungslauf starten.

1. Lüfter physisch ausschalten; er bleibt während der Wiederherstellung ohne zuverlässigen Timer.
2. Alle Schreibprozesse einschließlich Timer anhalten:

```sh
sudo systemctl stop marstek-solaredge.timer marstek-forecast.timer marstek-tibber.timer marstek-maintenance.timer marstek-weather.timer
sudo systemctl stop marstek-collector marstek-web marstek-fan marstek-solaredge.service marstek-forecast.service marstek-tibber.service marstek-maintenance.service marstek-weather.service
```

3. Auf dem Pi im Projekt die ausgewählte Sicherung nur lesend prüfen:

```sh
cd /home/pi/marstek-control
.venv/bin/python - <<'CHECK'
import sqlite3
with sqlite3.connect('file:/home/pi/restore.sqlite3?mode=ro', uri=True) as db:
    assert db.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    assert db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='measurements'").fetchone()
    print('Messungen, letzter Zeitstempel:', db.execute('SELECT count(*),max(ts) FROM measurements').fetchone())
CHECK
```

4. Nur bei erfolgreicher Prüfung und passendem Sicherungsdatum den gesamten alten data-Ordner behalten und die Kopie einsetzen:

```sh
mv data "data-vor-restore-$(date +%Y%m%d-%H%M%S)"
install -d -m 700 data
install -m 600 /home/pi/restore.sqlite3 data/measurements.db
```

Als Benutzer pi ausführen. Keine alten `-wal`/`-shm`-Dateien dazukopieren. Platz für alten und neuen Datenbestand einplanen.

5. Mit passendem aktuellem Code Tabellen ergänzen und alte Lüfteranforderungen verwerfen, damit ein historischer Auftrag nicht erneut einschaltet:

```sh
.venv/bin/python - <<'RESET'
from webapp import create_app
from settings import load_settings
from database import connect
create_app()
with connect(load_settings()['database_path']) as db:
    db.execute('UPDATE fan_state SET revision=revision+1,desired=NULL,deadline=NULL,observed=NULL,checked=NULL,error=NULL WHERE id=1')
RESET
```

Dies schaltet die Steckdose nicht aus; dafür Schritt 1. Bestätigte historische Ladeerkennung und alte Messdaten bleiben erhalten. Lüftergerät/UUID vor erneuter Nutzung prüfen.

6. Starten und kontrollieren:

```sh
sudo systemctl start marstek-collector marstek-web
sudo systemctl start marstek-solaredge.timer marstek-forecast.timer marstek-tibber.timer marstek-maintenance.timer marstek-weather.timer
```

Aktuelle Shelly-Daten, Einstellungen, Tagesdiagramm und Gerätebindung prüfen. Erst danach bei weiterhin gewünschter Lüfterfunktion `sudo systemctl start marstek-fan`. Eine neue geprüfte Mac-Sicherung erzeugen. Alten data-Ordner erst nach erfolgreicher Kontrolle später entfernen.

## SD-Karte ausgefallen

Neue Karte mit passendem Raspberry-Pi-OS/Debian, WLAN, SSH-Benutzer pi, korrekter Zeit und reservierter IP vorbereiten. Projekt aus der Mac-Kopie übertragen; `.venv` auf dem Pi neu aufbauen. Basisinstallation: `bash deploy-to-pi.sh` auf dem Mac. Sie startet zunächst mit leerer Datenbank. Anschließend die oben beschriebene Wiederherstellung bei gestoppten Diensten ausführen (noch nicht installierte Dienste können als unbekannt gemeldet werden).

Geschützte secrets.toml und geprüfte Anlagenkonfiguration separat zurückbringen, chmod 600 für secrets.toml. Auf dem Pi danach benötigte Zusatzinstaller aus `deploy/` ausführen: `install-forecast-on-pi.sh` (inkl. SolarEdge/Energie), `install-tibber-on-pi.sh`, `update-retention-on-pi.sh`, zuletzt bei gewünschtem Lüfter `install-fan-on-pi.sh`. Diese Skripte starten Dienste und können Cloud-Anfragen auslösen. Archivierte Lüfteraufträge vorher wie oben verwerfen. Mac-Sicherungszugriff auf dem neuen Pi erneut mit den vorhandenen Installationsskripten einrichten und einen echten Sicherungslauf kontrollieren. Geänderten SSH-Hostschlüssel erst nach Prüfung des neuen Pi akzeptieren.

Die Wiederherstellungsanleitung ist am Code geprüft, bisher kein kompletter Wiederherstellungstest auf einer Ersatz-SD-Karte. Ein solcher Test bleibt empfohlen.

Ab 1.9.0 zusätzlich `deploy/install-weather-on-pi.sh` auf dem Pi installieren. Der Wettertimer läuft alle 15 Minuten. NDR-Audio läuft ausschließlich im Browser. Details in WETTER_RADIO.md.


## Marstek-Beobachtung (1.10.0)

Siehe [MARSTEK.md](MARSTEK.md): eigener Dienst `marstek-battery`, 30-Sekunden-Abfragen, Tabelle `marstek_samples`, lokaler Endpunkt `/api/marstek`. Ab 1.11.0 zusätzlich konfigurierbare Autolade-Entladegrenze (200 W), mit Wiederherstellung und Mindestabstand; siehe MARSTEK.md. Bei Wiederherstellung der Datenbank diesen zusätzlichen Schreiber ebenfalls stoppen. Installation vom Mac: `bash update-marstek.sh` (auf bestehender Version 1.9.0).


## Kosten-Beobachtung 1.15.0

Zusätzlicher Schreiber: marstek-observer.service / marstek-observer.timer. Bei Datenbank-Restore beide stoppen. Installation und Modellgrenzen siehe BEOBACHTUNG.md. Keine Gerätebefehle aus diesem Dienst.
