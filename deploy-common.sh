#!/bin/bash
# Gemeinsame, lokale Zielkonfiguration für Installations- und Update-Skripte.
deploy_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
deploy_env="${ENERGYPI_DEPLOY_ENV:-$deploy_script_dir/deploy-local.env}"
if [ ! -f "$deploy_env" ]; then
    echo "Lokale Zielkonfiguration fehlt: $deploy_env" >&2
    echo "deploy-local.example.env nach deploy-local.env kopieren und anpassen." >&2
    return 1 2>/dev/null || exit 1
fi
# shellcheck disable=SC1090
source "$deploy_env"
: "${ENERGYPI_TARGET:?ENERGYPI_TARGET fehlt in deploy-local.env}"
: "${ENERGYPI_HOST:?ENERGYPI_HOST fehlt in deploy-local.env}"
ENERGYPI_REMOTE_DIR="${ENERGYPI_REMOTE_DIR:-/home/pi/marstek-control}"
ENERGYPI_URL="${ENERGYPI_URL:-http://$ENERGYPI_HOST:8080}"
