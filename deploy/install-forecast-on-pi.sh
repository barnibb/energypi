#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c 'from webapp import create_app; create_app()'
sudo install -m 644 deploy/marstek-forecast.service /etc/systemd/system/marstek-forecast.service
sudo install -m 644 deploy/marstek-forecast.timer /etc/systemd/system/marstek-forecast.timer
if [ ! -e secrets.toml ]; then
    install -m 600 secrets.example.toml secrets.toml
fi
sudo install -m 644 deploy/marstek-solaredge.service /etc/systemd/system/marstek-solaredge.service
sudo install -m 644 deploy/marstek-solaredge.timer /etc/systemd/system/marstek-solaredge.timer
sudo systemctl daemon-reload
sudo systemctl restart marstek-web
sudo systemctl enable --now marstek-forecast.timer marstek-solaredge.timer
sudo systemctl start marstek-forecast.service
sudo systemctl start marstek-solaredge.service
systemctl is-active marstek-web marstek-forecast.timer
journalctl -u marstek-forecast.service -u marstek-solaredge.service -n 12 --no-pager
echo 'Prognose und Tagesertrag ergänzt; SolarEdge benötigt weiterhin secrets.toml.'
