"""Gemeinsame Konfiguration; relative Datenpfade beziehen sich auf die TOML-Datei."""
import os
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parent

def load_settings(path=None):
    path = Path(path or os.environ.get('MARSTEK_CONFIG', ROOT / 'config.toml')).resolve()
    with path.open('rb') as file:
        config = tomllib.load(file)
    config['database_path'] = path.parent / config.get('storage', {}).get('path', 'data/measurements.db')
    for key in ('poll_seconds', 'timeout_seconds'):
        if not 0 < float(config['shelly'][key]) <= 3600:
            raise ValueError(f'Ungültiger Wert: {key}')
    return config
