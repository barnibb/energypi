#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av charging.py collector.py controller.py webapp.py project_info.json ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av static/charging.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av tests/test_charging.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/install-charging-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-charging-on-pi.sh'
