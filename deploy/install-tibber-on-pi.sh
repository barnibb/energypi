#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c 'from webapp import create_app; create_app()'
if [ ! -e secrets.toml ]; then
    install -m 600 secrets.example.toml secrets.toml
fi
sudo install -m 644 deploy/marstek-tibber.service /etc/systemd/system/marstek-tibber.service
sudo install -m 644 deploy/marstek-tibber.timer /etc/systemd/system/marstek-tibber.timer
sudo systemctl daemon-reload
sudo systemctl restart marstek-web
sudo systemctl enable --now marstek-tibber.timer
sudo systemctl start marstek-tibber.service
systemctl is-active marstek-web marstek-tibber.timer
journalctl -u marstek-tibber.service -n 8 --no-pager
echo 'Tibber ergänzt. [tibber] mit token und optional home_id in secrets.toml eintragen.'
