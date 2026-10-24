#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av fan_worker.py project_info.json MEROSS.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
ssh -t ${ENERGYPI_TARGET} 'sudo systemctl restart marstek-web marstek-fan'
echo 'Nach etwa einer Minute auf dem Pi prüfen: sudo journalctl -u marstek-fan --since "2 minutes ago" --no-pager'
