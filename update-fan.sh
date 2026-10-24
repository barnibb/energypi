#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av fan.py fan_worker.py meross_dns.py preferences.py webapp.py project_info.json requirements-meross.txt MEROSS.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/fan.js static/preferences.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_fan.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/marstek-fan.service deploy/install-fan-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-fan-on-pi.sh'
