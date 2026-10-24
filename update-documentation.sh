#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/deploy-common.sh"
cd "$(dirname "$0")"
.venv/bin/python - <<'PY'
import json
from pathlib import Path
info=json.loads(Path('project_info.json').read_text())
assert info['version']=='1.8.5'
for name in ('README.md','BETRIEB.md','PARAMETER.md','TECHNIK.md','DASHBOARD.md','AUFBEWAHRUNG.md','AUTOLADEN.md'):
    assert Path(name).is_file(),name
PY
rsync -av README.md BETRIEB.md PARAMETER.md TECHNIK.md DASHBOARD.md AUFBEWAHRUNG.md AUTOLADEN.md SOLAREDGE.md PROGNOSE.md TIBBER.md MEROSS.md project_info.json ${ENERGYPI_TARGET}:/home/pi/marstek-control/
rsync -av templates/documentation.html ${ENERGYPI_TARGET}:/home/pi/marstek-control/templates/
ssh -t ${ENERGYPI_TARGET} 'sudo systemctl restart marstek-web && systemctl is-active marstek-web'
echo 'Dokumentation übertragen. Im Dashboard die Versionsnummer anklicken.'
