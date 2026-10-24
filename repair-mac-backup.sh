#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
for key in marstek_backup_ed25519 marstek_backup_status_ed25519; do
    test -f "$HOME/.ssh/$key" || { echo "Schlüssel fehlt: $key. Bisherige Sicherungseinrichtung zuerst abschließen." >&2; exit 1; }
done
test -x /usr/bin/sqlite3
runtime="$HOME/Library/Application Support/EnergyPi"
label="local.energypi.mac-backup"
legacy_label="${ENERGYPI_LEGACY_LAUNCHD_LABEL:-}"
plist="$HOME/Library/LaunchAgents/$label.plist"
mkdir -p "$runtime/backups" "$HOME/Library/LaunchAgents"
chmod 700 "$runtime" "$runtime/backups"
# Kein Symlink und keine virtuelle Python-Umgebung aus Documents.
cp mac-backup/run-backup.sh "$runtime/run-backup.sh"
cp deploy-local.env "$runtime/deploy-local.env"
chmod 700 "$runtime/run-backup.sh"
chmod 600 "$runtime/deploy-local.env"
if [ -f "$plist" ]; then cp "$plist" "$runtime/previous-launchagent.plist"; fi
.venv/bin/python - "$runtime" "$plist" <<'PY'
import plistlib,sys
from pathlib import Path
root=Path(sys.argv[1])
settings=dict(Label='local.energypi.mac-backup',ProgramArguments=['/bin/bash',str(root/'run-backup.sh')],
 WorkingDirectory=str(root),StartCalendarInterval=dict(Hour=4,Minute=15),
 StandardOutPath=str(root/'backups'/'automatic.log'),StandardErrorPath=str(root/'backups'/'automatic-error.log'))
with open(sys.argv[2],'wb') as f:plistlib.dump(settings,f)
PY
plutil -lint "$plist"
uid=$(id -u)
if [ -n "$legacy_label" ]; then launchctl bootout "gui/$uid/$legacy_label" 2>/dev/null || true; fi
launchctl bootout "gui/$uid/$label" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$plist"
launchctl kickstart "gui/$uid/$label"
echo "Hintergrundtest gestartet. Sicherungen und Logs liegen unter: $runtime/backups"
echo 'Der Zeitplan bleibt täglich 04:15. Vorhandene Sicherungen im Projektordner bleiben erhalten.'
echo 'Der Test ist erst erfolgreich, wenn das Log „Sicherung und Rückmeldung erfolgreich“ meldet.'
