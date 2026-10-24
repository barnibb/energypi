"""Hochlast-Erkennung ohne Gerätezugriff."""
from dataclasses import dataclass
import math


@dataclass
class Controller:
    block_w: float = 3000
    release_w: float = 2000
    hold_s: float = 180
    max_gap_s: float = 15
    sustained_discharge_w: float = 750
    sustained_discharge_s: float = 600
    blocked: bool = False
    since: float | None = None
    sustained_since: float | None = None
    last: float | None = None

    def update(self, power: float | None, now: float, battery_discharge: float | None = None) -> str | None:
        if self.last is not None and (now < self.last or now - self.last > self.max_gap_s):
            self.since = None
            self.sustained_since = None
        self.last = now
        if power is None or not math.isfinite(power):
            self.since = None
            self.sustained_since = None
            return None
        battery_valid=(battery_discharge is not None and math.isfinite(battery_discharge)
                       and battery_discharge >= 0)
        if self.blocked:
            self.sustained_since=None
            if power >= self.release_w:
                self.since=None
                return None
            if self.since is None:self.since=now
            if now-self.since >= self.hold_s:
                self.blocked=False;self.since=None
                return "WUERDE_FREIGEBEN"
            return None
        if power > self.block_w:
            if self.since is None:self.since=now
        else:self.since=None
        if battery_valid and battery_discharge >= self.sustained_discharge_w:
            if self.sustained_since is None:self.sustained_since=now
        else:self.sustained_since=None
        if self.since is not None and now-self.since >= self.hold_s:
            self.blocked=True;self.since=self.sustained_since=None
            return "WUERDE_SPERREN"
        if self.sustained_since is not None and now-self.sustained_since >= self.sustained_discharge_s:
            self.blocked=True;self.since=self.sustained_since=None
            return "WUERDE_SPERREN_DAUERLAST"
        return None

    def remaining(self, now: float) -> float | None:
        pending=self.pending(now)
        return pending[1] if pending else None

    def pending(self, now: float):
        if self.blocked:
            return None if self.since is None else ('end',max(0,self.hold_s-(now-self.since)))
        candidates=[]
        if self.since is not None:candidates.append(('start',max(0,self.hold_s-(now-self.since))))
        if self.sustained_since is not None:candidates.append(('protection',max(0,self.sustained_discharge_s-(now-self.sustained_since))))
        return min(candidates,key=lambda item:item[1]) if candidates else None
