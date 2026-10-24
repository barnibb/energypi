#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av preferences.py collector.py opportunities.py webapp.py project_info.json AUTOLADEN.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av static/preferences.js static/tibber.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av templates/index.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av tests/test_preferences.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && .venv/bin/python -c "from webapp import create_app; create_app()" && sudo systemctl restart marstek-collector marstek-web && systemctl is-active marstek-collector marstek-web'
