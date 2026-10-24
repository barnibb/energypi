#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av weather.py webapp.py project_info.json WETTER_RADIO.md README.md BETRIEB.md TECHNIK.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/index.html templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
rsync -av static/weather.js static/radio.js static/style.css ${ENERGYPI_TARGET}:/home/pi/marstek-control/static/
rsync -av tests/test_weather.py tests/test_radio_ui.cjs ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
rsync -av deploy/marstek-weather.service deploy/marstek-weather.timer deploy/install-weather-on-pi.sh ${ENERGYPI_TARGET}:/home/pi/marstek-control/deploy/
ssh -t ${ENERGYPI_TARGET} 'bash /home/pi/marstek-control/deploy/install-weather-on-pi.sh'
