#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av opportunities.py tibber.py project_info.json TIBBER.md TECHNIK.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/tibber.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_opportunities.py tests/test_tibber.py tests/test_tibber_ui.cjs ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Akku-Wirtschaftlichkeitsgrenzen ergänzt. Dashboard vollständig neu laden.'
