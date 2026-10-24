# Aufbewahrung und Sicherung

Seit Version 1.40.0 beginnt die begrenzte Aufbewahrung bewusst mit kurzlebigen
Journalen. Vor jeder automatischen Wartung wird ein geprüfter SQLite-Snapshot
erstellt. Shelly-, Marstek-, SolarEdge-, Wetter-, Prognose- und Tibber-Messwerte
werden in dieser ersten Stufe nicht gelöscht.

## Installation (im Terminal auf dem Mac)

```sh
cd /PFAD/ZU/marstek-control
bash update-retention.sh
```

SSH-/sudo-Passwort auf Nachfrage direkt eingeben. Das Update überschreibt weder
config.toml noch Messdaten. Es erweitert das Schema, startet den Webdienst neu
und installiert einen täglichen systemd-Timer. Der Sammler läuft weiter.
Der erste Archiv-/Sicherungslauf wird sofort gestartet.

Danach die automatische Kopie auf den Mac einrichten:

```sh
bash install-mac-backup.sh
```

Hier wird ein eigener passwortloser SSH-Schlüssel unter
`~/.ssh/marstek_backup_ed25519` erzeugt. Sein Eintrag auf dem Pi erlaubt nur den
festen Befehl zum Erzeugen und Abrufen einer Datenbanksicherung; keine Shell und
keine Weiterleitungen. Der vorhandene normale SSH-Zugang bleibt bestehen.
Der Installer prüft zuerst einen echten Download und aktiviert erst danach den
Zeitplan als LaunchAgent des angemeldeten Mac-Benutzers.

Die automatische Sicherung wurde am 16.09.2026 erfolgreich bestätigt. Bei Neuinstallation den Erfolg erneut prüfen.

## Regeln

- Rohdaten: mindestens die letzten 30 × 24 Stunden, Grenze auf volle UTC-Minute abgerundet.
- Älter: Minutenmittel, Minimum, Maximum aller zehn Messfelder sowie Anzahl,
  erster/letzter Messzeitpunkt. Lücken trennen auch innerhalb einer Minute.
- Details alter Fehlertexte entfallen; Trennmarken bleiben erhalten.
- Archiv und Entfernen der Rohdaten erfolgen pro Minute atomar in einer Transaktion.
- Bei einem Fehler bleiben nicht abgeschlossene Rohdaten erhalten; Wiederholung möglich.
- Das Archiv wird dauerhaft behalten. Es gibt somit weiterhin keine feste maximale
  Datenbankgröße. Speicher wächst langsamer, aber nicht unbegrenzt auf einer SD-Karte.
- SQLite gibt freigewordene Seiten zur Wiederverwendung frei. Die Dateigröße muss
  nach einer Verdichtung nicht unmittelbar schrumpfen. Kein blockierendes VACUUM.

## Begrenzte Journale (Stufe 1)

- Abrufversuche für SolarEdge-Tagesenergie, Tibber und Wetter: 90 Tage.
- Lüfterereignisse und abgeschlossene Bedienaufträge: 365 Tage.
- Autolade-Erkennung, Marstek-Steuerjournal und Einstellungsänderungen: 730 Tage.
- Vollständige Beobachtungspläne: 14 Tage; der jüngste Plan bleibt immer erhalten.
- Offene, laufende oder bestätigte Geräteaufträge werden nicht gelöscht.
- Der jeweils neueste Eintrag einer Tabelle bleibt als Diagnosehinweis erhalten.
- Pro Tabelle werden je Nacht höchstens 10.000 alte Zeilen entfernt. Ein großer
  Altbestand wird dadurch kontrolliert über mehrere Nächte abgebaut.
- Für die großen Beobachtungspläne gilt eine strengere Grenze von 500 Zeilen pro
  Lauf. Netzladeaufträge und Entscheidungsprotokolle liegen in anderen Tabellen
  und werden durch diese Regel nicht berührt.
- Ergebnis und Restmenge stehen als einzelner Datensatz in maintenance_status;
  diese Statustabelle wächst nicht.

Jede Tabelle wird in einer eigenen kurzen Transaktion bereinigt. Ein Fehler in
einer Tabelle führt nicht zu einer teilweise abgeschlossenen Löschung innerhalb
dieser Tabelle. Die Sicherung liegt bereits vor Beginn der Wartung vor. Die
Wartungssperre wartet höchstens 60 Sekunden; der systemd-Dienst endet spätestens
nach 30 Minuten, statt unbegrenzt hängen zu können.

## Begrenzte Wartungsphasen (1.41.0)

- Sperre: höchstens 60 Sekunden Wartezeit.
- Integritätsprüfung vor dem Lauf: höchstens 120 Sekunden.
- SQLite-Sicherung: eigener Unterprozess, höchstens 10 Minuten.
- Shelly-Archivierung: höchstens 10 Minuten und 20.000 Minutenblöcke je Lauf.
- Journalbereinigung: höchstens 10.000 Zeilen pro Tabelle und Lauf.
- Sicherungsexport zum Mac: höchstens 15 Minuten.
- Gesamter systemd-Lauf: höchstens 30 Minuten; Beenden höchstens 30 Sekunden.

Vor der Sicherung werden Datenbankgröße und freier Speicher geprüft. Erforderlich
sind das 1,5-Fache der Datenbankgröße plus 500 MiB Reserve. Reicht der Platz nicht,
beginnen weder Sicherung noch Löschung. Ein Unterprozess kann auch dann beendet
werden, wenn SQLite intern nicht zurückkehrt. systemd beendet mit KillMode
control-group auch verbliebene Kindprozesse.

Beim Start entfernt die Wartung ausschließlich `.partial`-Dateien, die älter als
eine Stunde sind, und nur während sie die exklusive Wartungssperre hält. Nach
einem fehlgeschlagenen eigenen Sicherungsversuch wird dessen unvollständige Datei
entfernt. Fertige Snapshots werden nicht angetastet.

Der Systemstatus speichert Phase, Ergebnis, Laufzeit, Sicherungsgröße,
archivierte Minuten sowie verbleibende Roh- und Journalzeilen in einem einzelnen
Datensatz. Bei einem Fehler bleibt der Zeitpunkt des letzten erfolgreichen Laufs
sichtbar. Ein Rückstand wird am folgenden Tag kontrolliert fortgesetzt.

## Messreihen-Aufbewahrung: sichere Einführung (1.42.0)

Die erste Stufe analysiert ausschließlich den Bestand. Sie liest Zeilenzahl,
ältesten und jüngsten Zeitpunkt sowie – sofern SQLite dbstat bereitstellt – den
Seitenbedarf von Shelly-Rohwerten, Minutenarchiv, Marstek, SolarEdge, Wetter,
PV-Prognosen, Tibber, Beobachtungsplänen und Finanzcache. SolarEdge-Tageserträge
und Prognosetage werden zusätzlich gezählt.

Die Analyse erstellt keine Messwertarchive und löscht keine Messwerte. Ihr
Ergebnis wird innerhalb des bereits vorhandenen einzelnen Wartungsstatus
gespeichert; dadurch wächst keine weitere Protokolltabelle. Ab dem zweiten Lauf
wird außerdem die Veränderung der Zeilenzahlen seit dem vorherigen Lauf gezeigt.
Im Dashboard erscheint dafür „Datenaufbewahrung“ mit dem ausdrücklichen Hinweis,
dass die Originaldaten in dieser Analysephase vollständig erhalten bleiben.

Erst nach einem erfolgreichen Lauf auf dem Pi und Prüfung dieser Bestandswerte
folgt die zweite Stufe mit neuen Archivtabellen. Auch dann bleiben die Quelldaten
zunächst erhalten. Löschungen werden erst nach getesteten gemischten Lesewegen
und einem weiteren geprüften Snapshot aktiviert.

## Zeitpläne und Speicherorte

Pi: täglich 03:15 in seiner Systemzeitzone, bis fünf Minuten Zufallsverzögerung.
Versäumte Timerläufe werden beim nächsten Start nachgeholt.
Datenbank: `/home/pi/marstek-control/data/measurements.db`
Snapshots: `/home/pi/marstek-control/data/backups/`
Sieben erfolgreiche Snapshots bleiben erhalten; ältere werden nach erfolgreicher
Neusicherung gelöscht. `latest.sqlite3` verweist auf das neueste vollständige Backup.

Mac: täglich 04:15 in der Mac-Systemzeitzone. Ein im Schlaf versäumter Termin wird
beim Aufwachen nachgeholt; nach vollständigem Ausschalten nicht zuverlässig.
Der Benutzer muss angemeldet sein und den Pi im Heimnetz erreichen können.
Bei Netzwerkfehler bleibt die letzte erfolgreiche Sicherung erhalten; nächster
Versuch beim nächsten Termin oder manuell mit `bash "$HOME/Library/Application Support/EnergyPi/run-backup.sh"`.
Aktuelles Ziel: `~/Library/Application Support/EnergyPi/backups/`. Sieben erfolgreiche Kopien bleiben erhalten.
Fehlerprotokoll dort: `automatic-error.log`. Das alte backup-to-mac.sh sichert weiterhin separat in den Projektordner. Unvollständige Downloads tragen
`.partial` und zählen nicht als erfolgreiche Sicherung.

Backups werden mit der SQLite-Backup-API erzeugt, vor Veröffentlichung und nach
Download mit quick_check geprüft. WAL-Inhalte sind enthalten. Der Download hält
die Wartungssperre, damit die Datei nicht währenddessen rotiert wird.
Snapshots auf dem Pi allein schützen nicht gegen einen Ausfall der SD-Karte.
Auch Snapshots brauchen Platz: Hauptdatenbank plus bis zu sieben Vollkopien und
vorübergehend eine weitere Kopie beim Sichern einplanen; auf dem Mac ebenfalls.

## Kontrolle

Auf dem Pi:

```sh
systemctl list-timers marstek-maintenance.timer --no-pager
journalctl -u marstek-maintenance.service -n 30 --no-pager
du -sh ~/marstek-control/data
```

Auf dem Mac:

```sh
launchctl print gui/$(id -u)/local.energypi.mac-backup
ls -lh "$HOME/Library/Application Support/EnergyPi/backups/"
```

## Wiederherstellung

Die vollständige Anleitung steht in [BETRIEB.md](BETRIEB.md), einschließlich aller schreibenden Dienste, alter Lüfteraufträge und Wiederaufbau nach SD-Karten-Ausfall.

## Abschalten der Zeitpläne

Pi: `sudo systemctl disable --now marstek-maintenance.timer`
Mac: `launchctl bootout gui/$(id -u)/local.energypi.mac-backup`
Für dauerhaftes Entfernen auch die zugehörige plist unter ~/Library/LaunchAgents
entfernen. Messdaten und vorhandene Sicherungen werden dabei nicht gelöscht.

## Sicherungsstatus (1.4.0)

`bash update-backup-status.sh` installiert die Statusanzeige und richtet auf dem Mac einen separaten Schlüssel `~/.ssh/marstek_backup_status_ed25519` ein. Dieser darf über einen erzwungenen SSH-Befehl nur `success` oder `failure` an `backup_status.py` übergeben. Der bestehende Export-Schlüssel bleibt unverändert eingeschränkt.

Das aktualisierte backup-to-mac.sh meldet Erfolg erst nach Download, SQLite-quick_check, Umbenennung und Rotation. Fehler lösen einen Rückmeldeversuch aus. Ist der Pi unerreichbar, steht der Übertragungsfehler im lokalen Sicherungslog; der Pi behält den zuletzt bekannten Status. Nach 36 Stunden wird ein alter Erfolg als überfällig angezeigt. Seit 1.7.1 verwendet launchd stattdessen den eigenständigen Runner unter Library/Application Support/EnergyPi.

Der Status wird in der SQLite-Tabelle backup_status gespeichert. Zeitstempel entsprechen dem Empfang am Pi. Die Update-Anleitung führt direkt eine erste Sicherung aus. Erfolg bedeutet eine zum damaligen Zeitpunkt geprüfte Sicherung, keine laufende Überwachung der Datei auf dem Mac.

## macOS-Dokumentenschutz beheben (1.7.1)

Im Mac-Projekt `bash repair-mac-backup.sh` ausführen. Der Installer kopiert den eigenständigen Runner nach `~/Library/Application Support/EnergyPi/run-backup.sh`. Er verwendet ausschließlich macOS-Systemprogramme und die bisherigen eingeschränkten SSH-Schlüssel; keine Laufzeitdateien aus Documents. Das Entwicklungsprojekt bleibt unverändert am bisherigen Ort.

launchd wird weiterhin für 04:15 eingerichtet und direkt als Hintergrundtest gestartet. Installation allein ist noch kein erfolgreicher Test. In `~/Library/Application Support/EnergyPi/backups/automatic.log` muss anschließend „Sicherung und Rückmeldung erfolgreich“ stehen. Fehler stehen in automatic-error.log. Dieser Hintergrundlauf ist aussagekräftiger als ein manueller Terminal-Aufruf.

Neue Sicherungen liegen im selben backups-Ordner, maximal sieben. Alte Sicherungen im Projekt bleiben erhalten, werden nicht verschoben und nicht in die neue Rotation einbezogen. Die vorherige LaunchAgent-Konfiguration wird als previous-launchagent.plist gesichert. Bei künftigen Runner-Änderungen repair-mac-backup.sh erneut ausführen, da der Hintergrundlauf eine unabhängige Kopie nutzt. Nach hartem Abbruch kann die Sperre backups/.running stehenbleiben; nur entfernen, wenn kein Lauf aktiv ist.
