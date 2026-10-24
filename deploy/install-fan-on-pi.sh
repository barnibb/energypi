#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m pip install -r requirements-meross.txt
.venv/bin/python -c 'from meross_iot.http_api import MerossHttpClient; from meross_iot.manager import MerossManager'
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -c 'from webapp import create_app; create_app()'
sudo install -m 644 deploy/marstek-fan.service /etc/systemd/system/marstek-fan.service
sudo systemctl daemon-reload
sudo systemctl enable marstek-fan
sudo systemctl restart marstek-web marstek-fan
systemctl is-active marstek-web marstek-fan
echo 'Dienst installiert. Ohne Meross-Zugangsdaten bleibt der Lüfter nicht bereit; es wird nichts eingeschaltet.'
