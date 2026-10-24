#!/bin/bash
set -euo pipefail
cd /home/pi/marstek-control
.venv/bin/python -m unittest discover -s tests -v
sudo systemctl restart marstek-web
systemctl is-active marstek-web
echo 'Preisfenster, PV-Band und 9-ct-Linie ergänzt. Dashboard neu laden.'
