#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av marstek.py marstek_control.py marstek_actions.py webapp.py project_info.json MARSTEK.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/marstek.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_marstek_actions.py tests/test_project_info.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-battery marstek-web && systemctl is-active marstek-battery marstek-web'
echo 'Eigenverbrauch-Freigabe installiert; bekannte Entladegrenze wird beim ausdrücklichen Wechsel sofort sicher wiederhergestellt.'
