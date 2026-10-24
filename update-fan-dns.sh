#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
rsync -av meross_dns.py fan_worker.py project_info.json MEROSS.md ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av tests/test_meross_dns.py ${ENERGYPI_TARGET}:/home/pi/marstek-control/tests/
ssh -t ${ENERGYPI_TARGET} 'cd /home/pi/marstek-control && .venv/bin/python -m unittest discover -s tests -q && .venv/bin/python -c "from meross_dns import configure_meross_dns; configure_meross_dns()" && sudo systemctl restart marstek-fan marstek-web'
echo 'DNS-Anpassung installiert. Nach etwa einer Minute Dashboard und Lüfterprotokoll prüfen.'
