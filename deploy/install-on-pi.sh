#!/bin/bash
set -euo pipefail
project_directory="${ENERGYPI_REMOTE_DIR:-/home/pi/marstek-control}"
if [[ ! "$project_directory" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    echo "Ungültiges Projektverzeichnis: $project_directory" >&2
    exit 1
fi
cd "$project_directory"
if [ "$(id -un)" != pi ]; then
    echo 'Bitte als Benutzer pi ausführen.' >&2
    exit 1
fi
for required in config.toml marstek.toml forecast.toml secrets.toml; do
    if [ ! -f "$required" ]; then
        echo "Lokale Konfiguration fehlt: $project_directory/$required" >&2
        exit 1
    fi
done
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
# Bestehende Dienstdefinitionen sichern und alle mitgelieferten Definitionen
# aktualisieren. Nur bereits laufende Dienste werden anschließend neu gestartet.
stamp=$(date +%Y%m%d-%H%M%S)
active_services=()
for source in deploy/marstek-*.service; do
    unit="$(basename "$source")"
    if systemctl is-active --quiet "$unit"; then
        active_services+=("$unit")
    fi
    if [ -f "/etc/systemd/system/$unit" ]; then
        sudo cp -p "/etc/systemd/system/$unit" "/etc/systemd/system/$unit.backup-$stamp"
    fi
    rendered="$(mktemp)"
    sed "s|/home/pi/marstek-control|$project_directory|g" "$source" > "$rendered"
    sudo install -m 644 "$rendered" "/etc/systemd/system/$unit"
    rm -f "$rendered"
done
for source in deploy/marstek-*.timer; do
    unit="$(basename "$source")"
    if [ -f "/etc/systemd/system/$unit" ]; then
        sudo cp -p "/etc/systemd/system/$unit" "/etc/systemd/system/$unit.backup-$stamp"
    fi
    sudo install -m 644 "$source" "/etc/systemd/system/$unit"
done
sudo systemctl daemon-reload
sudo systemctl enable marstek-collector marstek-web
restart_services=(marstek-collector.service marstek-web.service)
for unit in "${active_services[@]}"; do
    if [[ " ${restart_services[*]} " != *" $unit "* ]]; then
        restart_services+=("$unit")
    fi
done
sudo systemctl restart "${restart_services[@]}"
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
systemctl is-active "${restart_services[@]}"
host_address="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "Fertig: http://${host_address:-RASPBERRY_PI_IP}:8080 — laufende EnergyPi-Dienste wurden mit dem geprüften Stand neu gestartet."
