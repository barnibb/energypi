#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av tibber.py opportunities.py webapp.py secrets.example.toml ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av static/ ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av templates/ ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av tests/test_tibber.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/marstek-tibber.service deploy/marstek-tibber.timer deploy/install-tibber-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-tibber-on-pi.sh'
