#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
report_backup() {
    local outcome="$1"
    local report_key="$HOME/.ssh/marstek_backup_status_ed25519"
    if [ -f "$report_key" ]; then
        if ! printf '%s\n' "$outcome" | ssh -i "$report_key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 ${ENERGYPI_TARGET} backup-status; then
            echo 'Sicherungsrückmeldung konnte nicht an den Pi übertragen werden.' >&2
        fi
    else
        echo 'Sicherungsstatus-Schlüssel fehlt; install-backup-status.sh ausführen.' >&2
    fi
}
trap 'result=$?; if [ "$result" -ne 0 ]; then report_backup failure; fi' EXIT
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
target="backups/pi-$stamp.sqlite3"
key="$HOME/.ssh/marstek_backup_ed25519"
options=(-o ConnectTimeout=10)
if [ -f "$key" ]; then
    options+=(-i "$key" -o IdentitiesOnly=yes -o BatchMode=yes)
elif [ "${1:-}" = --automatic ]; then
    echo 'SSH-Schlüssel fehlt; install-mac-backup.sh ausführen.' >&2
    exit 1
fi
# Remote bleibt die Backup-Sperre bis zum Ende des Downloads gehalten.
ssh "${options[@]}" ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python maintenance.py --export-backup' > "$target.partial"
.venv/bin/python - "$target.partial" <<'PY'
import sqlite3
import sys
from contextlib import closing
with closing(sqlite3.connect(sys.argv[1])) as db:
    if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise SystemExit('Sicherung auf dem Mac ist unvollständig oder beschädigt.')
PY
mv "$target.partial" "$target"
.venv/bin/python - <<'PY'
from pathlib import Path
# Nur eigene, erfolgreich abgeschlossene Sicherungen rotieren.
for old in sorted(Path('backups').glob('pi-*.sqlite3'), reverse=True)[7:]:
    old.unlink()
PY
echo "Geprüfte Sicherung auf dem Mac: $(pwd)/$target"

report_backup success
