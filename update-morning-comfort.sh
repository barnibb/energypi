#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av morning.py marstek_control.py marstek_actions.py marstek_display.py preferences.py project_info.json MARSTEK.md PARAMETER.md TECHNIK.md AUTOLADEN.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/marstek.js static/preferences.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_morning.py tests/test_marstek_control.py tests/test_marstek_display.py tests/test_marstek_ui.cjs tests/test_preferences.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web marstek-battery && systemctl is-active marstek-web marstek-battery'
echo 'Akku-Zeitregel und Nachtreserve installiert. Dashboard vollständig neu laden.'
