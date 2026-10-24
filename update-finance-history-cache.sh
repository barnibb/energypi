#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av finance_history.py webapp.py project_info.json TECHNIK.md README.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/finance-history.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_finance_history.py tests/test_finance_history_ui.cjs tests/test_project_info.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Sieben-Tage-Kalenderwochen und Preiscache aktualisiert. Dashboard vollständig neu laden.'
