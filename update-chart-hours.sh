#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av preferences.py forecast.py project_info.json PARAMETER.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/preferences.js static/forecast.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_preferences.py tests/test_forecast.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Diagrammzeitbereich einstellbar. Dashboard vollständig neu laden.'
