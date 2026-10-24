#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
target="$ENERGYPI_TARGET"

rsync -av webapp.py grid_charging.py database.py finance_history.py sun_times.py weather.py preferences.py project_info.json WETTER_RADIO.md "$target:/home/pi/marstek-control/"
rsync -av static/design-live.css static/style.css static/autumn-leaves.js static/dashboard.js static/preferences.js static/forecast.js static/tibber.js static/weather.js static/weather-history.js static/finance-history.js static/system.js static/phases.js static/observation.js static/grid-charge.js static/manifest.webmanifest "$target:/home/pi/marstek-control/static/"
rsync -av static/icons/ "$target:/home/pi/marstek-control/static/icons/"
rsync -av templates/design_preview.html templates/index.html templates/documentation.html "$target:/home/pi/marstek-control/templates/"
rsync -av tests/test_dashboard.py tests/test_design_preview.py tests/test_finance_history.py tests/test_preferences.py tests/test_project_info.py tests/test_marstek.py tests/test_marstek_display.py tests/test_grid_charging.py tests/test_weather.py tests/test_weather_history.py "$target:/home/pi/marstek-control/tests/"

ssh -t "$target" 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web marstek-battery && sudo systemctl start marstek-weather.service && sleep 3 && systemctl is-active marstek-web marstek-battery'
echo 'Aktuelles Dashboard-Design installiert; das alte Design bleibt unter /design_alt erreichbar.'
