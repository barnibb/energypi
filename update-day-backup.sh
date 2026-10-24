#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av backup_status.py system_status.py project_info.json ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/dashboard.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_backup_status.py tests/test_system.py tests/test_day_navigation.py tests/test_mac_backup_runner.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
bash repair-mac-backup.sh
echo 'Tagesnavigation und Sicherungsstatus aktualisiert; ein geprüfter Mac-Sicherungstest wurde gestartet.'
