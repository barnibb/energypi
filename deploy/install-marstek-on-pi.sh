#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -c 'from settings import load_settings; from marstek import initialize_marstek; initialize_marstek(load_settings()["database_path"])'
sudo install -m 644 deploy/marstek-battery.service /etc/systemd/system/marstek-battery.service
sudo systemctl daemon-reload
sudo systemctl enable --now marstek-battery.service
sudo systemctl restart marstek-battery.service marstek-web.service
systemctl is-active marstek-battery.service marstek-web.service
curl --fail --silent --show-error --retry 5 --retry-connrefused --retry-delay 1 --max-time 5 http://127.0.0.1:8080/api/marstek
echo
echo 'Marstek mit Autolade-Entladegrenze installiert. Erste Messung spätestens nach 30 Sekunden; Dashboard neu laden.'
