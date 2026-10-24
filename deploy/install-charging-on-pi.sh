#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c 'from webapp import create_app; create_app()'
sudo systemctl restart marstek-collector marstek-web
systemctl is-active marstek-collector marstek-web
echo 'Autolade-Erkennung und Statusanzeige eingerichtet. Dashboard neu laden.'
