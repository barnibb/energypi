# Tibber-Preisvorschau

Die Anwendung nutzt https://api.tibber.com/v1-beta/gql serverseitig per GraphQL POST.
TIBBER_CONFIG in tibber.py enthält nur den festen API-Endpunkt. Der persönliche
Token steht ausschließlich in secrets.toml und wird als Bearer-Header gesendet.

## Update

Im Mac-Terminal:

```sh
cd /PFAD/ZU/marstek-control
bash update-tibber.sh
```

Die bisher installierten Dashboard-/Forecast-Module werden vorausgesetzt.
Das Skript überschreibt weder secrets.toml noch config.toml oder die Datenbank.
Es ergänzt Tabellen, startet den Webdienst neu und richtet einen Tibber-Timer ein.

Danach:

```sh
ssh pi@RASPBERRY_PI_IP
nano ~/marstek-control/secrets.toml
```

Diesen neuen Abschnitt unten hinzufügen; [solaredge] unbedingt behalten:

```toml
[tibber]
token = "DEIN_PERSOENLICHER_TIBBER_TOKEN"
home_id = ""
```

Bei genau einem Tibber-Home wird dieses automatisch verwendet. Bei mehreren Homes
muss die gewünschte ID angegeben werden. Nur IDs auflisten:

```sh
cd ~/marstek-control
.venv/bin/python tibber.py --list-homes
```

Token erhältst du über https://developer.tibber.com/ nach Anmeldung.
Speichern in nano: Ctrl+O, Enter, Ctrl+X. Anschließend:

```sh
chmod 600 ~/marstek-control/secrets.toml
sudo systemctl start marstek-tibber.service
journalctl -u marstek-tibber.service -n 10 --no-pager
```

Bei einem bereits erfolgten Versuch in derselben Stunde wartet die nächste
Preisabfrage bis zum folgenden Stundenfenster. Fehlende Zugangsdaten reservieren
kein Fenster. Dashboard unter http://RASPBERRY_PI_IP:8080 neu laden.

## Grafik

Heute, morgen oder gespeichertes Datum auswählen. Balken zeigen Viertelstundenpreise
in ct/kWh; negative Preise grün, sonst blau. Das aktuelle Intervall ist umrandet.
Karten zeigen aktuellen Preis sowie Minimum und Maximum des ausgewählten Tages.
Tagesmittel ist ein Zeitmittel, kein verbrauchsgewichteter Rechnungsbetrag.
Bei Datenlücken wird ausdrücklich nur das Mittel der vorhandenen Intervalle gezeigt.

Verwendet wird Tibbers Feld total, also der von der API gelieferte Gesamtpreis
je kWh. Monatsgrundgebühren sind darin nicht enthalten. Nur EUR wird akzeptiert.
Die Abfrage fordert ausdrücklich priceInfo(resolution: QUARTER_HOURLY) an.
Zeitstempel enthalten UTC-Offsets; dadurch bleiben doppelte Stunden bei
Zeitumstellung getrennt. Negative Preise werden nicht abgeschnitten.

Es handelt sich um veröffentlichte Vertragspreise, nicht um eine eigene
Preisprognose. Noch nicht gelieferte Morgenpreise werden nicht erfunden oder
als 0 angezeigt. Eine feste Veröffentlichungsuhrzeit wird nicht vorausgesetzt.

## Abrufstrategie

Timer prüft stündlich, löst aber nicht immer einen API-Aufruf aus:
- Heute und morgen vollständig gespeichert: kein erneuter Abruf.
- Heute vollständig, morgen fehlt: Versuche von 13 bis 20 Uhr, höchstens einmal
  pro Stundenfenster, bis morgen vollständig geliefert ist.
- Heute fehlt/ist unvollständig: beim nächsten Stundenlauf erneut versuchen.
- Fehler warten bis zum nächsten Fenster. Browser liest nur SQLite.

Normalerweise reicht nach Veröffentlichung ein erfolgreicher Aufruf pro Tag
für beide Tage. Bei verzögerter Veröffentlichung/Fehlern mehrere Versuche.
Tibber-Aufrufe verändern das separate SolarEdge-Abfragebudget nicht.
Für ein anderes Home werden vorhandene Preise nicht vermischt; home_id dient
als Bestandteil des Datenbankschlüssels.

## Speicherung und Backup

`tibber_prices`: Home-ID, Start/Ende, total/energy/tax in EUR/kWh, Währung,
Abrufzeitpunkt. Ein Tagesverlauf hat normalerweise 96 Intervalle, bei Zeitumstellung
92 oder 100. Preise werden dauerhaft gespeichert; erneuter Abruf aktualisiert
vorhandene Intervalle desselben Homes.
`tibber_attempts`: Zeitpunkt und bereinigter Status der Abfrage.
`tibber_meta`: zuletzt erfolgreich ausgewähltes Home.
Alle Tabellen liegen in measurements.db und werden mitgesichert. Token steht
nicht in SQLite, Webantworten, Logs oder dem übertragenen Beispiel.

## Validierung

30 Python-Tests bestehen. JavaScript- und Shell-Syntax geprüft. Tibber-Livezugriff
steht bis zum Eintragen des Tokens aus; keine persönlichen Zugangsdaten gelesen.
Die visuelle Browserprüfung muss nach dem Update erfolgen (Browseranbindung war
zuletzt nicht verfügbar). Auf dem Pi prüfen:

```sh
systemctl list-timers marstek-tibber.timer --no-pager
journalctl -u marstek-tibber.service -n 20 --no-pager
```

Referenzen:
https://developer.tibber.com/docs/reference
https://developer.tibber.com/docs/guides/calling-api

## Potentiell günstige Zeitfenster

Update im Mac-Terminal: `bash update-opportunities.sh`, danach Dashboard neu laden.

Die vorhandene Preisgrafik erhält:
- Hellblaue Hinterlegung für das günstigste Viertel der vorhandenen Tagespreise.
  Die Rangschwelle ist ceil(Anzahl/4); Preisgleichstände werden vollständig markiert.
  Sind alle Preise gleich, gibt es keine relative Günstig-Markierung.
- Eine gestrichelte Vergleichslinie bei 9 ct/kWh Einspeisevergütung und einen
  zusätzlichen Punkt an Preisbalken unter dieser Schwelle (strikt kleiner).
- Ein gelbes Band unabhängig von verfügbaren Tibber-Preisen. Voraussetzung:
  prognostizierte PV-Erzeugung ab 3610 W während der ganzen Viertelstunde.
  Rechnung: 160 W Grundlast plus 3450 W (5 A × 3 Phasen × 230 V).
- Hover/Berührung hebt das Intervall hervor und zeigt Preis, Begründungen und
  prognostizierten PV-Überschuss nach Abzug der Grundlast.

Stündliche PV-Punkte werden linear interpoliert; für die Bandfreigabe wird das
Minimum des Intervalls verwendet. Der Tooltip zeigt den Überschuss zur Intervallmitte.
Größere Prognoselücken werden nicht überbrückt. Für heute/morgen werden Prognosen
älter als vier Stunden nicht für das Band verwendet. Historische Ansichten sind
als archivierte Prognose gekennzeichnet. Das Zeitraster berücksichtigt Zeitumstellung.

Das ist eine unverbindliche Markierung, keine Ladeplanung oder Steuerung. Zusätzliche
Hausverbraucher, Marstek-Leistung und Prognosefehler sind nicht eingerechnet.
Es entstehen keine zusätzlichen externen API-Abfragen und keine neuen Tabellen.
35 Python-Tests bestanden; JavaScript-Syntax geprüft. Visuelle Kontrolle auf dem
Pi nach dem Update bleibt erforderlich.

## Datumswechsel ab 1.8.4

Das Leeren des Diagramms vor einem Tageswechsel berücksichtigt fehlende Daten. Die neue Anfrage startet unmittelbar; zuvor konnte ein JavaScript-Fehler sie bis zum nächsten automatischen Abruf verhindern. Update: `bash update-tibber-date-fix.sh`.

## Akku-Wirtschaftlichkeitsgrenzen ab 1.17.0

Zwei zusätzliche gestrichelte Linien zeigen Modellgrenzen, ab denen eine Entladung
gegenüber Netzbezug wirtschaftlich wird. Die PV-Akku-Grenze lautet
`Einspeisevergütung / Wirkungsgrad + Verschleiß + Vorteilspuffer`. Die Netz-Akku-
Grenze ersetzt die Einspeisevergütung durch den aktuell geltenden Tibber-Preis.
Bei 9 ct/kWh, 85 %, 2 ct und 3 ct ergeben sich rund 15,6 ct/kWh. Bei einem
aktuellen Ladepreis von 17,05 ct/kWh beträgt die Netz-Akku-Grenze rund 25,1 ct/kWh.

Die Linien verwenden die aktuellen Einstellungen, auch bei historischen Ansichten.
Sie weisen dem tatsächlich gespeicherten Strom keine Herkunft oder Einkaufskosten
zu und lösen keine Steuerung aus. Fehlt ein aktueller Tibber-Preis, wird nur die
PV-Akku-Grenze gezeigt.
