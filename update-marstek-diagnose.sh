#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
target="$ENERGYPI_TARGET"
rsync -av marstek_diagnose.py project_info.json MARSTEK.md "$target:/home/pi/marstek-control/"
rsync -av tests/test_marstek_diagnose.py "$target:/home/pi/marstek-control/tests/"
ssh -t "$target" 'cd /home/pi/marstek-control && .venv/bin/python -m unittest tests.test_marstek_diagnose -q && sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Schreibfreie Marstek-Diagnose installiert.'
