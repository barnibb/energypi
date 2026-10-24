#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
target="$ENERGYPI_TARGET"
rsync -av grid_charging.py marstek.py marstek_control.py preferences.py webapp.py sun_times.py project_info.json MARSTEK.md "$target:/home/pi/marstek-control/"
rsync -av static/observation.js static/preferences.js static/forecast.js static/tibber.js static/weather-history.js static/style.css static/design-live.css "$target:/home/pi/marstek-control/static/"
rsync -av templates/index.html templates/documentation.html templates/design_preview.html "$target:/home/pi/marstek-control/templates/"
rsync -av tests/test_grid_charging.py tests/test_marstek_control.py tests/test_project_info.py tests/test_design_preview.py "$target:/home/pi/marstek-control/tests/"
ssh -t "$target" 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web marstek-battery && sleep 5 && systemctl is-active marstek-web marstek-battery'
echo 'Zeitgenauer Netzladestart 1.35.1 installiert; erster Einsatz nur beaufsichtigt mit 500 W.'
