#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av marstek.py marstek_control.py preferences.py webapp.py project_info.json MARSTEK.md PARAMETER.md README.md BETRIEB.md TECHNIK.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
# Bestehende Anschlusskonfiguration nicht überschreiben.
rsync -av --ignore-existing marstek.toml ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/marstek.js static/preferences.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_marstek.py tests/test_marstek_control.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/marstek-battery.service deploy/install-marstek-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-marstek-on-pi.sh'
