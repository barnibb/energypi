#!/bin/bash
# Eigenständiger launchd-Runner: nur macOS-Systemprogramme und eingeschränkte SSH-Schlüssel.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
cd "$(dirname "$0")"
if [ ! -f deploy-local.env ]; then
    echo 'Lokale Zielkonfiguration deploy-local.env fehlt.' >&2
    exit 1
fi
# shellcheck disable=SC1091
source deploy-local.env
: "${ENERGYPI_TARGET:?ENERGYPI_TARGET fehlt in deploy-local.env}"
umask 077
mkdir -p backups
lock=backups/.running
if ! mkdir "$lock" 2>/dev/null; then
    echo 'Sicherung bereits aktiv oder alte Sperre vorhanden.' >&2
    exit 1
fi
partial=''
caffeinate_pid=''
report() {
    printf '%s\n' "$1" | /usr/bin/ssh -i "$HOME/.ssh/marstek_backup_status_ed25519" \
      -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
      -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
      "$ENERGYPI_TARGET" backup-status
}
cleanup() {
    result=$?
    trap - EXIT
    if [ -n "$partial" ]; then rm -f "$partial"; fi
    if [ -n "$caffeinate_pid" ]; then kill "$caffeinate_pid" 2>/dev/null || true; fi
    rmdir "$lock"
    if [ "$result" -ne 0 ]; then
        echo "$(date -Iseconds 2>/dev/null || date): Sicherung/Statusübertragung fehlgeschlagen (Code $result)." >&2
        report failure || true
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for key in marstek_backup_ed25519 marstek_backup_status_ed25519; do
    test -f "$HOME/.ssh/$key" || { echo "SSH-Schlüssel fehlt: $key" >&2; exit 1; }
done
# Verhindert, dass der Mac während der laufenden SSH-Übertragung in den
# Ruhezustand wechselt. Nach Ende dieses Skripts verschwindet die Zusicherung.
/usr/bin/caffeinate -i -w $$ &
caffeinate_pid=$!
target="backups/pi-$(date +%Y%m%d-%H%M%S)-$$.sqlite3"
partial="$target.partial"
attempt=1
while :; do
    if /usr/bin/ssh -C -i "$HOME/.ssh/marstek_backup_ed25519" \
      -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
      -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o IPQoS=throughput \
      "$ENERGYPI_TARGET" 'cd /home/pi/marstek-control && .venv/bin/python maintenance.py --export-backup' > "$partial"; then
        break
    fi
    rm -f "$partial"
    if [ "$attempt" -ge 2 ]; then
        echo 'SSH-Übertragung auch beim zweiten Versuch fehlgeschlagen.' >&2
        exit 1
    fi
    echo 'SSH-Übertragung fehlgeschlagen; einmaliger Neuversuch in 10 Sekunden.' >&2
    attempt=$((attempt+1))
    sleep 10
done
test -s "$partial"
check=$(/usr/bin/sqlite3 -readonly "$partial" 'PRAGMA quick_check;')
[ "$check" = ok ] || { echo 'SQLite-Prüfung fehlgeschlagen.' >&2; exit 1; }
# Eine leere SQLite-Datenbank würde quick_check ebenfalls bestehen.
[ "$(/usr/bin/sqlite3 -readonly "$partial" "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='measurements';")" = 1 ]
mv "$partial" "$target"
partial=''
# Ausschließlich Dateien unseres festen Namensschemas rotieren; keine fremden Dateien.
count=0
while IFS= read -r file; do
    count=$((count+1))
    if [ "$count" -gt 7 ]; then rm -- "backups/$file"; fi
done < <(find backups -maxdepth 1 -type f -name 'pi-*.sqlite3' -exec basename {} \; | LC_ALL=C sort -r)
echo "$(date): Geprüfte Sicherung: $(pwd)/$target"
report success
echo "$(date): Sicherung und Rückmeldung erfolgreich."
