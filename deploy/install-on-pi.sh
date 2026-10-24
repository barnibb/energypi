#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
if [ "$(id -un)" != pi ]; then
    echo 'Bitte als Benutzer pi ausführen.' >&2
    exit 1
fi
python3 -c 'import sys,sqlite3,ssl,venv; assert sys.version_info >= (3,11), "Python >= 3.11 erforderlich"'
# Keine fremde Anwendung auf Port 8080 verdrängen.
if ss -ltnH 'sport = :8080' | read -r _; then
    if ! systemctl is-active --quiet marstek-web; then
        echo 'Port 8080 ist bereits durch eine andere Anwendung belegt. Installation angehalten.' >&2
        exit 1
    fi
fi
sudo -v
sudo apt-get update
sudo apt-get install -y python3-venv
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
mkdir -p data
.venv/bin/python -c 'from settings import load_settings; from database import initialize; initialize(load_settings()["database_path"])'
# Bestehende gleichnamige Dienstdefinitionen für eine Rückkehr sichern.
stamp=$(date +%Y%m%d-%H%M%S)
for service in marstek-collector marstek-web; do
    if [ -f "/etc/systemd/system/$service.service" ]; then
        sudo cp -p "/etc/systemd/system/$service.service" "/etc/systemd/system/$service.service.backup-$stamp"
    fi
    sudo install -m 644 "deploy/$service.service" "/etc/systemd/system/$service.service"
done
sudo systemctl daemon-reload
sudo systemctl enable marstek-collector marstek-web
sudo systemctl restart marstek-collector marstek-web
# Auf HTTP-Antwort UND eine aktuelle erfolgreiche Messung warten.
.venv/bin/python - <<'PY'
import json
import time
from urllib.request import build_opener, ProxyHandler
opener = build_opener(ProxyHandler({}))
for attempt in range(20):
    try:
        with opener.open('http://127.0.0.1:8080/api/status', timeout=2) as response:
            status = json.load(response)
        if not status['stale']:
            print('Dashboard erreichbar. Aktueller Shelly-Wert:', status['sample']['total_act_power'], 'W')
            break
    except (OSError, ValueError):
        pass
    time.sleep(2)
else:
    raise SystemExit('Keine aktuellen Werte. Prüfen: journalctl -u marstek-collector -u marstek-web -n 50 --no-pager')
PY
systemctl is-enabled marstek-collector marstek-web
systemctl is-active marstek-collector marstek-web
host_address="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "Fertig: http://${host_address:-RASPBERRY_PI_IP}:8080 — beide Dienste starten beim Booten automatisch."
