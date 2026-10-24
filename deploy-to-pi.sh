#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
target="$ENERGYPI_TARGET"
remote_directory="$ENERGYPI_REMOTE_DIR"
ssh "$target" "mkdir -p '$remote_directory'"
rsync -av --exclude '.venv/' --exclude '.git/' --exclude 'secrets.toml' --exclude 'deploy-local.env' --exclude '__pycache__/' --exclude 'data/' --exclude 'backups/' --exclude '*.log' ./ "$target:$remote_directory/"
ssh -t "$target" "bash '$remote_directory/deploy/install-on-pi.sh'"
