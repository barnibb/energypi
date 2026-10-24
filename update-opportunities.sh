#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av opportunities.py tibber.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av static/tibber.js ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av templates/index.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av tests/test_opportunities.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/install-opportunities-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-opportunities-on-pi.sh'
