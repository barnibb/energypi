#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av system_status.py project_info.json MARSTEK.md WETTER_RADIO.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/radio.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_system.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Systemstatus und Radio aktualisiert. Dashboard vollständig neu laden.'
