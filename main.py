"""Lokaler Shelly-Monitor. Sendet ausschließlich HTTP-GET, keine Steuerbefehle."""
import argparse
import json
import logging
import math
from pathlib import Path
import time
import tomllib
from urllib.request import build_opener, ProxyHandler

from controller import Controller


def read_power(opener, host, timeout):
    with opener.open(f"http://{host}/rpc/EM.GetStatus?id=0", timeout=timeout) as response:
        data = json.load(response)
    if not isinstance(data, dict) or data.get("errors") or data.get("code"):
        raise ValueError("Shelly meldet einen Fehler oder eine ungültige Antwort")
    value = data.get("total_act_power")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("total_act_power fehlt oder ist ungültig")
    return float(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.toml"))
    parser.add_argument("--once", action="store_true", help="Nur eine Messung auslesen")
    args = parser.parse_args()
    with args.config.open("rb") as file:
        config = tomllib.load(file)
    shelly, rule = config["shelly"], config["high_load"]
    interval = float(shelly["poll_seconds"])
    timeout = float(shelly["timeout_seconds"])
    if interval <= 0 or timeout <= 0 or rule["release_below_w"] >= rule["block_above_w"] or rule["hold_seconds"] <= 0 or rule["max_gap_seconds"] <= interval:
        raise ValueError("Ungültige Zeit- oder Schwellwerte in config.toml")
    controller = Controller(rule["block_above_w"], rule["release_below_w"], rule["hold_seconds"], rule["max_gap_seconds"])
    opener = build_opener(ProxyHandler({}))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("BEOBACHTUNGSMODUS: keine Marstek-Verbindung; Startzustand NORMAL (simuliert)")
    try:
        while True:
            start = time.monotonic()
            try:
                power = read_power(opener, shelly["host"], timeout)
            except (OSError, ValueError) as error:
                controller.update(None, time.monotonic())
                logging.warning("Messung ungültig: %s; Frist zurückgesetzt", error)
                if args.once:
                    return 1
            else:
                now = time.monotonic()
                action = controller.update(power, now)
                if action:
                    logging.info("%s — nur Simulation", action)
                remaining = controller.remaining(now)
                logging.info("Netz=%+.1f W | Zustand=%s | Frist=%s", power,
                             "GESPERRT_SIMULIERT" if controller.blocked else "NORMAL_SIMULIERT",
                             "—" if remaining is None else f"noch {remaining:.0f} s")
                if args.once:
                    return 0
            time.sleep(max(0, interval - (time.monotonic() - start)))
    except KeyboardInterrupt:
        logging.info("Beobachtung beendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
