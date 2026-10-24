#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av battery_history.py flow_summary.py finance_summary.py finance_history.py forecast.py webapp.py project_info.json MARSTEK.md TECHNIK.md README.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/forecast.js static/dashboard.js static/finance-history.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_battery_history.py tests/test_flow_summary.py tests/test_finance_summary.py tests/test_finance_history.py tests/test_finance_history_ui.cjs tests/test_money_rings.cjs tests/test_marstek.py tests/test_project_info.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Energieanteile, Geldwerte, Zehn-Tage-Preisvergleich und Akku-Verlauf aktualisiert. Dashboard vollständig neu laden.'
