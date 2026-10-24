#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
target="$ENERGYPI_TARGET"

rsync -av webapp.py "$target:/home/pi/marstek-control/"
rsync -av templates/energy_flow_preview.html "$target:/home/pi/marstek-control/templates/"
rsync -av static/energy-flow-preview.css static/energy-flow-preview.js "$target:/home/pi/marstek-control/static/"
rsync -av static/manifest.webmanifest "$target:/home/pi/marstek-control/static/"
rsync -av static/icons/ "$target:/home/pi/marstek-control/static/icons/"
rsync -av tests/test_energy_flow_preview.py "$target:/home/pi/marstek-control/tests/"

ssh -t "$target" 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-web && sleep 3 && systemctl is-active marstek-web'
echo "Energiefluss-Vorschau installiert: $ENERGYPI_URL/energiefluss-preview"
