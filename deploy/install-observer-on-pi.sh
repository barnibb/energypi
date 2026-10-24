#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -c 'from settings import load_settings; from optimizer import initialize_optimizer; initialize_optimizer(load_settings()["database_path"])'
sudo install -m 644 deploy/marstek-observer.service deploy/marstek-observer.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now marstek-observer.timer
sudo systemctl start marstek-observer.service
sudo systemctl restart marstek-web
systemctl is-active marstek-web marstek-observer.timer
journalctl -u marstek-observer.service -n 5 --no-pager
echo 'Beobachtungsmodus installiert. Keine Akku-Befehle aus dem Kostenplan. Dashboard neu laden.'
