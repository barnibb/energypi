#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
key="$HOME/.ssh/marstek_backup_status_ed25519"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
if [ ! -f "$key" ]; then
    ssh-keygen -t ed25519 -N '' -C marstek-backup-status-only -f "$key"
fi
# Separater Schlüssel: nur Erfolg/Fehler melden, keine allgemeinen Befehle.
line="restrict,command=\"cd /home/pi/marstek-control && .venv/bin/python backup_status.py\" $(cat "$key.pub")"
printf '%s\n' "$line" | ssh ${ENERGYPI_TARGET} 'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; IFS= read -r entry; if ! grep -qxF "$entry" ~/.ssh/authorized_keys; then printf "\n%s\n" "$entry" >> ~/.ssh/authorized_keys; fi'
bash backup-to-mac.sh --automatic
