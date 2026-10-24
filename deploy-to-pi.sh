#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
target="$ENERGYPI_TARGET"
remote_directory="$ENERGYPI_REMOTE_DIR"
stamp="$(date +%Y%m%d-%H%M%S)"
backup_directory="${remote_directory%/}-code-backups"
backup_file="$backup_directory/energypi-code-$stamp.tar.gz"

# Die bisherige Programmversion bleibt getrennt von Datenbank und lokaler
# Konfiguration verfügbar. Die drei neuesten Code-Sicherungen werden behalten.
ssh "$target" "set -eu; mkdir -p '$remote_directory' '$backup_directory'; if [ -n \"\$(find '$remote_directory' -mindepth 1 -maxdepth 1 -print -quit)\" ]; then tar -czf '$backup_file' --exclude='.venv' --exclude='.git' --exclude='data' --exclude='backups' --exclude='config.toml' --exclude='marstek.toml' --exclude='forecast.toml' --exclude='secrets.toml' --exclude='deploy-local.env' -C '$remote_directory' .; fi; ls -1t '$backup_directory'/energypi-code-*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm --"

# Lokale Anlagen-, Geräte- und Zugangsdaten auf dem Pi niemals ersetzen.
rsync -av \
  --exclude '.venv/' --exclude '.git/' --exclude '__pycache__/' \
  --exclude 'data/' --exclude 'backups/' --exclude '*.log' \
  --exclude 'config.toml' --exclude 'marstek.toml' \
  --exclude 'forecast.toml' --exclude 'secrets.toml' \
  --exclude 'deploy-local.env' \
  ./ "$target:$remote_directory/"

if ! ssh -t "$target" "ENERGYPI_REMOTE_DIR='$remote_directory' bash '$remote_directory/deploy/install-on-pi.sh'"; then
    echo "Installation fehlgeschlagen. Die vorherige Code-Sicherung liegt auf dem Pi:" >&2
    echo "$backup_file" >&2
    echo "Die laufenden Dienste wurden vom Installer erst nach erfolgreichen Tests neu gestartet." >&2
    exit 1
fi
echo "Code-Sicherung vor diesem Update: $backup_file"
