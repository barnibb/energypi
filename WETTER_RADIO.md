# Wetter und NDR-Radio

Version 1.9.0. Auf dem Mac im Projekt `bash update-weather-radio.sh` ausführen. Auf dem Pi werden Wettertabellen und ein 15-Minuten-Timer angelegt, einmal Wetter abgerufen und nur der Webdienst neu gestartet. Kein API-Key und keine zusätzlichen Python-Pakete nötig. Anschließend Dashboard vollständig neu laden. Erfolg des Radioempfangs auf dem jeweiligen Browsergerät prüfen; Installation startet keine Wiedergabe.

## Anlagenstandort und Sevilla

Die Meteo-Kachel zeigt den in der lokalen `forecast.toml` benannten Anlagenstandort groß und Sevilla in Spanien kleiner rechts daneben. Koordinaten und Anzeigename des Anlagenstandorts werden nicht veröffentlicht. Beide Angaben sind Open-Meteo-Best-Match-Lufttemperaturen in 2 m Höhe und keine Sensorwerte vor Ort. Das Tages-Popup zeichnet beide gespeicherten Verläufe gemeinsam und zeigt für jeden Ort eigene Sonnenzeiten. Die Sevilla-Koordinaten entsprechen der Stadtangabe der spanischen Wetterbehörde AEMET.

Sevilla beginnt mit einer eigenen Messreihe in `weather_sevilla_samples`. Frühere Werte des ersetzten zweiten Standorts werden nicht umgedeutet und bleiben lediglich als ungenutzte Alttabelle in bestehenden Datenbanken erhalten.

`weather.py` fragt jeden Standort höchstens einmal je UTC-Viertelstunde ab, auch bei Fehlern. Timeout 10 s, keine unmittelbaren Wiederholungen. Das sind normal höchstens 96 Anfragen pro Standort und Tag. Beide Orte haben getrennte Tabellen und Fehlerzustände, damit ein Ausfall den jeweils anderen Wert nicht entfernt. Browser liest `/api/weather` jede Minute lokal; Cloud-Abruf läuft unabhängig. Letzte gute Werte bleiben nach Fehlern erhalten; nach mehr als einer Stunde seit Wetterzeit oder Abruf gelten sie als veraltet.

Tabellen `weather_samples`: fetched_at, valid_at (UTC-Sekunden), temperature_c (°C), angefragte Standortkoordinaten und source. Die API kann einen benachbarten Rasterpunkt liefern. `weather_attempts`: Viertelstundenslot, Abrufzeit und sicherer Fehlertext. Beide Tabellen sind Bestandteil der vollständigen SQLite-Sicherung; derzeit keine automatische Löschfrist. Noch kein Temperaturdiagramm und keine Wärmepumpensteuerung.

Kontrolle auf Pi: `systemctl status marstek-weather.timer` und `journalctl -u marstek-weather.service -n 10 --no-pager`. Wetterdienst während Datenbankwiederherstellung zusammen mit den übrigen Schreibdiensten stoppen.

Quelle: https://open-meteo.com/en/docs — private nicht-kommerzielle Nutzung ohne Schlüssel. Attribution Open-Meteo / CC BY 4.0 wird an der Karte angezeigt.

## NDR Info und NDR 2

Zwei Buttons links neben Lüfter Bad. Start per Klick; zweiter Klick auf den aktiven Sender stoppt und entfernt die Audioquelle, damit keine Verbindung weiterläuft. Ein Klick auf den anderen Sender beendet zunächst den laufenden Stream und startet danach den gewählten Sender. Es läuft höchstens ein Sender je Browser-Tab. Kein Autoplay und keine Audioaufzeichnung. Browsergerät benötigt Internet; Pi ist kein Audioplayer oder Streamproxy. Kein Lautstärkeregler im Dashboard; Player-Pegel 50 %, Lautstärke über das Wiedergabegerät ändern. Neuladen/Seitenwechsel beendet Wiedergabe.

Offizielle Playlist geprüft am 18.09.2026: https://www.ndr.de/resources/metadaten/audio/m3u/ndrinfo.m3u
Sie liefert `http://icecast.ndr.de/ndr/ndrinfo/live/mp3/128/stream.mp3`; verwendet wird die geprüfte HTTPS-Variante. Die stabile Adresse leitet auf einen kurzlebigen CDN-Link um; keine temporäre Zieladresse speichern. Streamadresse liegt als data-src im HTML. Bei Änderung offizielle Playlist erneut prüfen. Kein CORS-Proxy nötig. Bei Fehlern erscheint ein Hinweis und Link zur offiziellen NDR-Seite.

Für NDR 2 wird seit Version 1.26.0 die offizielle regionale MP3-Ausgabe für Schleswig-Holstein verwendet: `https://icecast.ndr.de/ndr/ndr2/schleswigholstein/mp3/128/stream.mp3`. Die zugehörige offizielle Playlist ist `https://www.ndr.de/resources/metadaten/audio/m3u/ndr2_sh.m3u`.

## Prüfumfang

Tests für Wettervalidierung, negative Temperatur, Ausfall, Veraltung, doppelte Abrufe und API. JavaScript-Prüfung für Radio-Start/Stop, exklusives Umschalten zwischen NDR Info und NDR 2, verworfene verspätete Startantwort und Wiedergabefehler. End-to-End-Tonwiedergabe und Layout am tatsächlich verwendeten Mac/Handy nach Update vor Ort prüfen.

Beim lokalen Mac-Test hatte die Projekt-Python-Umgebung keinen passenden Standard-Zertifikatspfad. Mit `SSL_CERT_FILE=/etc/ssl/cert.pem .venv/bin/python weather.py` funktioniert der Abruf mit aktivierter TLS-Prüfung. Auf Debian nutzt Python normalerweise den System-Zertifikatsspeicher; bei Zertifikatfehlern Uhrzeit und ca-certificates prüfen, niemals TLS-Prüfung ausschalten. Der Live-Abruf wurde in einer temporären Datenbank geprüft; keine Testwerte in die produktive Datenbank geschrieben.


## Temperatur-Tagesverlauf (1.16.0)

Klick auf die Außen-Kachel öffnet ein natives Dialogfenster, per Tastatur bedienbar und mit Escape schließbar. Quellenlinks bleiben unabhängig. Heute, Gestern und Datumsauswahl; durchgehende lokale Tagesachse bis 24:00, °C-Achse, Tooltip und niedrigster/höchster erfasster Wert. Sommer-/Winterzeitgrenzen werden als 23-/25-Stunden-Tage berücksichtigt. Keine Messwerte nach dem aktuellen Zeitpunkt.

GET `/api/weather/history?date=YYYY-MM-DD` liest nur SQLite. Index auf valid_at/fetched_at. Maßgeblich ist valid_at (Wetterzeit), bei mehrfach gespeichertem Zeitstempel zählt die letzte Version. Lücken über 20 Minuten werden nicht verbunden. Fehlende Tage zeigen einen Leerzustand; Min/Max beziehen sich nur auf erfasste Werte. Heutiger Tag aktualisiert sich bei geöffnetem Fenster jede Minute, ältere Tage nur bei Auswahl. Überholte Anfragen werden abgebrochen.

Installation: `bash update-weather-history.sh`. Keine zusätzlichen Cloud-Anfragen oder neuen Tabellen.
