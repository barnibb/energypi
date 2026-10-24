#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c 'from settings import load_settings; from solaredge import initialize_solar; initialize_solar(load_settings()["database_path"])'
if [ ! -e secrets.toml ]; then
    install -m 600 secrets.example.toml secrets.toml
fi
sudo install -m 644 deploy/marstek-solaredge.service /etc/systemd/system/marstek-solaredge.service
sudo install -m 644 deploy/marstek-solaredge.timer /etc/systemd/system/marstek-solaredge.timer
sudo systemctl daemon-reload
sudo systemctl restart marstek-web
sudo systemctl enable --now marstek-solaredge.timer
sudo systemctl start marstek-solaredge.service
systemctl is-active marstek-web marstek-solaredge.timer
echo 'SolarEdge vorbereitet. site_id und api_key in ~/marstek-control/secrets.toml eintragen.'
