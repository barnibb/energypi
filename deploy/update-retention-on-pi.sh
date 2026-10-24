#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -v
# Ein Snapshot vor der ersten Verdichtung bleibt unter den sieben Sicherungen.
timeout --signal=INT --kill-after=30s 30m .venv/bin/python maintenance.py --backup-only
sudo -v
sudo install -m 644 deploy/marstek-maintenance.service /etc/systemd/system/marstek-maintenance.service
sudo install -m 644 deploy/marstek-maintenance.timer /etc/systemd/system/marstek-maintenance.timer
sudo systemctl daemon-reload
sudo systemctl restart marstek-web
sudo systemctl enable --now marstek-maintenance.timer
sudo systemctl start marstek-maintenance.service
systemctl is-active marstek-collector marstek-web marstek-maintenance.timer
systemctl list-timers marstek-maintenance.timer --no-pager
echo 'Aufbewahrung und tägliche Sicherung auf dem Pi sind eingerichtet.'
