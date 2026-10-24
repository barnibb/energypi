#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av project_info.json TECHNIK.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
ssh -t ${ENERGYPI_TARGET} 'sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Projektstruktur in der Dokumentation ergänzt. Versionslink im Dashboard öffnen.'
