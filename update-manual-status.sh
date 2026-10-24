#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av system_status.py marstek_control.py project_info.json MARSTEK.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av tests/test_system.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && sudo systemctl restart marstek-battery marstek-web && systemctl is-active marstek-battery marstek-web'
echo 'Manuelle Vorgaben werden neutral angezeigt. Dashboard neu laden.'
