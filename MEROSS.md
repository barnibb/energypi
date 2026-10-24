# Lüfter Bad – Version 1.8.0

## Einrichtung

Vom Mac `bash update-fan.sh` ausführen. Auf dem Pi installiert das Skript die optionale Bibliothek meross_iot==0.4.10.4 und den Dienst marstek-fan. Bestehende secrets.toml wird nicht übertragen oder überschrieben.

Auf dem Pi mit `nano /home/pi/marstek-control/secrets.toml` diesen Abschnitt ergänzen (bestehende SolarEdge-/Tibber-Abschnitte behalten):

```toml
[meross]
email = "DEINE_MEROSS_EMAIL"
password = "DEIN_MEROSS_PASSWORT"
```

Danach `chmod 600 /home/pi/marstek-control/secrets.toml` und `sudo systemctl restart marstek-fan`. Zugangsdaten gehören nicht in Chat, Logs oder Versionsverwaltung. Die Cloud-Region ist Europa. Noch keine physische Schaltung beim Installieren oder Erkennen des Geräts. Erst ein Startauftrag schaltet ein.

Der Dienst sucht genau eine MSS210 namens „Lüfter Bad“, speichert ihre UUID und bleibt daran gebunden. Eine Umbenennung ändert die Auswahl nicht; ein Ersatzgerät muss ausdrücklich neu zugeordnet werden. Fehlende oder mehrdeutige Geräte führen zu keiner Schaltung.

## Bedienung und Verhalten

Button oben links vom Messstatus: Dialog mit Einschalten, Neustart der Laufzeit und Ausschalten. Parameter fan_minutes: 1–120 ganze Minuten, Standard 20. Laufzeitänderungen beeinflussen aktive Fristen nicht. Ein Start während eines aktiven Timers setzt die Frist ab dem neuen Auftrag neu. Aufträge und Fristen stehen dauerhaft in fan_state; Start, Stop und Ablauf werden in fan_events protokolliert. Beide Tabellen sind Teil der SQLite-Sicherung.

Ein separater einzelner Worker schaltet; Browser und Webserver senden nur Anforderungen. Die Abschaltfrist wird vor der Schaltung gespeichert. Überfällige Startaufträge werden nach Neustart nicht eingeschaltet. Ausschaltaufträge bleiben bis zur Bestätigung bestehen. Ein unbekannter Zustand wird nicht als Aus dargestellt. Der Geräteabruf erfolgt regulär etwa alle 30 Sekunden; neue Aufträge werden etwa alle zwei Sekunden bemerkt. Netzwerkzeiten und Wiederholungen können die Abschaltung verzögern.

Es ist kein geräteinterner Countdown bestätigt. Pi-Ausfall, Internet-/Cloud-Ausfall oder nicht erreichbare Steckdose verhindern eine garantierte fristgerechte Abschaltung. Bei Fehlern erfolgt erneuter Verbindungsaufbau mit Pause. Keine Steuerung einsetzen, bei der eine garantierte Abschaltung erforderlich ist. Änderungen der Systemuhr beeinflussen die absolute Frist.

Außerhalb von EnergyPi eingeschaltete Geräte bleiben ohne EnergyPi-Timer. Während eines aktiven Timers setzt der Worker den angeforderten Einschaltzustand durch; daher zum Abbrechen EnergyPi „Jetzt ausschalten“ nutzen. Schaltanforderungen sind für Benutzer mit Zugriff auf das lokale Dashboard möglich. Der Endpunkt akzeptiert nur JSON mit eigenem Header, keine fremden HTML-Formulare.

## Prüfung

Automatische Tests nutzen simulierte Geräte: eindeutige Auswahl, Timerpersistenz, Neustart mit abgelaufener Frist, Ausschaltfehler, API-Prüfung und konkurrierende Anforderungen. Echte Meross-Anmeldung, Python-Paketinstallation auf dem Pi und reale Schaltfunktion müssen vor Ort geprüft werden. Zunächst Laufzeit 1 Minute wählen, starten und tatsächliche Abschaltung prüfen; danach gewünschten Wert setzen.

Bibliotheksdokumentation: https://albertogeniola.github.io/MerossIot/quick-start.html

## Diagnose ab 1.8.1

Fehler nennen den fehlgeschlagenen Schritt (Konfiguration, EU-Anmeldung, MQTT, Geräteerkennung oder Status/Schaltung) und eine bekannte Fehlerklasse. Rohtexte, URLs, Tokens und Kontodaten bleiben unterdrückt. Die Geräteauswahl protokolliert nur Geräte-/Trefferanzahl und ob bereits eine UUID gebunden ist. Die allgemeine Meldung in 1.8.0 erlaubte keine Ursachenbestimmung.

## System-DNS (1.8.2)

Auf dem Pi zeigte aiohttp 3.14.3 mit AsyncResolver einen DNS-Timeout, während ThreadedResolver den Meross-Host erfolgreich auflöste. meross_dns.py ersetzt deshalb nur die von meross_iot.http_api verwendete ClientSession-Factory im Lüfterprozess und setzt einen TCPConnector mit ThreadedResolver. Dies gilt für Login, Geräteabfragen und Logout. TLS-Prüfung und dynamische Namensauflösung bleiben erhalten; keine festen IP-Adressen, keine Routeränderung und keine Deinstallation von aiodns.

Die Anpassung beruht auf der internen ClientSession-Verwendung der festgelegten MerossIot-Version; bei Bibliotheksupdates prüfen. update-fan-dns.sh installiert die Anpassung und startet den Dienst neu. Lokale Tests prüfen die begrenzte Wirkung und Wiederholbarkeit der Factory-Anpassung; erfolgreiche Cloud-Anmeldung und MQTT-/Geräteverbindung müssen anschließend auf dem Pi bestätigt werden.
