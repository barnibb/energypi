#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
# Gezielt übertragen: keine Konfiguration und keine Datenbank überschreiben.
rsync -av database.py maintenance.py retention.py system_status.py project_info.json AUFBEWAHRUNG.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av tests/test_retention.py tests/test_retention_inventory.py tests/test_system.py tests/test_project_info.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/marstek-maintenance.service deploy/marstek-maintenance.timer deploy/update-retention-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/update-retention-on-pi.sh'
