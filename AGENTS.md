# Projektpflege

Bei jeder ausgelieferten Änderung project_info.json aktualisieren:
- Version erhöhen (Patch für Fehlerkorrekturen, Minor für neue Funktionen, Major für inkompatible Änderungen).
- Datum und neuen Eintrag oben in releases ergänzen; alte Einträge erhalten.
- Betroffene Dokumentationsabschnitte und technische Markdown-Anleitungen aktualisieren.
- project_info.json und templates/documentation.html in Update-Paketen berücksichtigen, wenn sie geändert wurden.
- Keine Zugangsdaten oder Inhalte von secrets.toml in die Dokumentation aufnehmen.

Die erste explizit vergebene Version ist 1.0.0. Keine rückwirkenden Versionsnummern oder unbelegten Veröffentlichungsdaten erfinden.
