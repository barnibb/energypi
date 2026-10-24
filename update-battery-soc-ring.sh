#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av charging.py controller.py collector.py preferences.py marstek_control.py marstek_display.py optimizer.py opportunities.py tibber.py project_info.json AUTOLADEN.md PARAMETER.md TECHNIK.md TIBBER.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/charging.js static/preferences.js static/tibber.js static/marstek.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_balance.py tests/test_charging.py tests/test_charging_ui.cjs tests/test_controller.py tests/test_marstek.py tests/test_marstek_ui.cjs tests/test_marstek_control.py tests/test_marstek_display.py tests/test_preferences.py tests/test_optimizer.py tests/test_opportunities.py tests/test_tibber.py tests/test_tibber_ui.cjs ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && sudo systemctl restart marstek-collector && sudo systemctl restart marstek-battery && systemctl is-active marstek-web marstek-collector marstek-battery'
echo 'Dauerlastschutz und Akku-Ladestandsring ergänzt. Dashboard vollständig neu laden.'
