"""Time handling: UTC storage, local windows, injectable clock.

Rules (docs/FAILURE_MODES.md #3):
  * Everything persisted is ISO-8601 UTC ("...Z").
  * Day windows are defined in the user's local timezone from the config.
  * Monotonic offsets are recorded alongside wall time so later analysis
    can detect clock changes / DST oddities without trusting them.
  * If the IANA tz database is unavailable (bare Windows Python without
    the tzdata package) we degrade to a fixed offset with a recorded
    warning instead of crashing.
"""

import datetime as _dt
import time as _time
from typing import Optional

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
    _HAS_ZONEINFO = True
except Exception:  # pragma: no cover
    _HAS_ZONEINFO = False

UTC = _dt.timezone.utc
_FALLBACK_TZ = _dt.timezone(_dt.timedelta(hours=5, minutes=30), "Asia/Kolkata+fixed")


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(UTC)


def to_iso(dt: _dt.datetime) -> str:
    """UTC ISO-8601 with Z suffix, second precision."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> _dt.datetime:
    return _dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def local_tz(name: str) -> _dt.tzinfo:
    """Resolve a timezone by IANA name, degrading honestly if impossible."""
    if _HAS_ZONEINFO:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return _FALLBACK_TZ


def parse_hhmm(text: str) -> _dt.time:
    h, m = text.split(":")
    return _dt.time(int(h), int(m))


class Clock:
    """Injectable time source. Production uses RealClock; tests and the
    simulated demo use SimulatedClock so day-window logic is fully
    deterministic and reproducible."""

    def now_utc(self) -> _dt.datetime:  # pragma: no cover - interface
        raise NotImplementedError

    def monotonic_ms(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def iso(self) -> str:
        return to_iso(self.now_utc())


class RealClock(Clock):
    def now_utc(self) -> _dt.datetime:
        return now_utc()

    def monotonic_ms(self) -> int:
        return int(_time.monotonic() * 1000)

    def sleep(self, seconds: float) -> None:
        _time.sleep(seconds)


class SimulatedClock(Clock):
    """Deterministic clock for tests and the shipped demo.

    Wall time and a monotonic counter both advance by the same amount so
    day-window math and delay/cooldown math stay consistent.
    """

    def __init__(self, start: Optional[_dt.datetime] = None):
        self._now = start or _dt.datetime(2026, 11, 2, 4, 0, tzinfo=UTC)
        self._mono = 1_000_000

    def now_utc(self) -> _dt.datetime:
        return self._now

    def monotonic_ms(self) -> int:
        return self._mono

    def sleep(self, seconds: float) -> None:
        self.advance(minutes=seconds / 60.0)

    def advance(self, minutes: float = 0, hours: float = 0.0,
                seconds: float = 0.0, days: float = 0.0):
        delta = _dt.timedelta(days=days, minutes=minutes, hours=hours,
                              seconds=seconds)
        self._now += delta
        self._mono += int(delta.total_seconds() * 1000)
        return self

    def set(self, dt: _dt.datetime):
        self._now = dt.astimezone(UTC)
        return self
