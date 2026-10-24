#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av forecast.py project_info.json PROGNOSE.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av static/forecast.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av templates/index.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
