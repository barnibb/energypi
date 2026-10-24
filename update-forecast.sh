#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av forecast.py forecast.toml energy.py solaredge.py webapp.py secrets.example.toml ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/ ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/ ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_forecast.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/marstek-forecast.service deploy/marstek-forecast.timer deploy/marstek-solaredge.service deploy/marstek-solaredge.timer deploy/install-forecast-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-forecast-on-pi.sh'
