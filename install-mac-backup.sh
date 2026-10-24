#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
project=$(pwd)
key="$HOME/.ssh/marstek_backup_ed25519"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
if [ ! -f "$key" ]; then
    ssh-keygen -t ed25519 -N '' -C marstek-backup-only -f "$key"
fi
# Dieser Schlüssel darf auf dem Pi nur die SQLite-Sicherung ausgeben.
# Kein Terminal, keine Portweiterleitung und keine beliebigen Befehle.
line="restrict,command=\"cd /home/pi/marstek-control && .venv/bin/python maintenance.py --export-backup\" $(cat "$key.pub")"
printf '%s\n' "$line" | ssh ${ENERGYPI_TARGET} 'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; IFS= read -r entry; if ! grep -qxF "$entry" ~/.ssh/authorized_keys; then printf "\n%s\n" "$entry" >> ~/.ssh/authorized_keys; fi'
# Status-Schlüssel einrichten, falls noch nicht vorhanden.
if [ ! -f "$HOME/.ssh/marstek_backup_status_ed25519" ]; then
    bash install-backup-status.sh
fi
bash repair-mac-backup.sh
