#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -c 'from settings import load_settings; from weather import initialize_weather; initialize_weather(load_settings()["database_path"])'
sudo install -m 644 deploy/marstek-weather.service /etc/systemd/system/marstek-weather.service
sudo install -m 644 deploy/marstek-weather.timer /etc/systemd/system/marstek-weather.timer
sudo systemctl daemon-reload
sudo systemctl enable --now marstek-weather.timer
sudo systemctl start marstek-weather.service
sudo systemctl restart marstek-web
systemctl is-active marstek-web marstek-weather.timer
journalctl -u marstek-weather.service -n 5 --no-pager
echo 'Wetter und NDR Info installiert. Dashboard vollständig neu laden.'
