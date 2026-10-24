#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av optimizer.py planning_defaults.py preferences.py webapp.py project_info.json BEOBACHTUNG.md PARAMETER.md BETRIEB.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/observation.js static/preferences.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_optimizer.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/marstek-observer.service deploy/marstek-observer.timer deploy/install-observer-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-observer-on-pi.sh'
