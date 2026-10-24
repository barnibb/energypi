#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av balance.py webapp.py project_info.json DASHBOARD.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av static/dashboard.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av tests/test_balance.py tests/test_dashboard.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
