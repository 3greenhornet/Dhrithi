"""Domain models: enums and the shared DayWindow value object.

Lifecycles (dossier section 3.4) — activity states are observations,
never authorities. Only these state machines decide enforcement.
"""

import datetime as _dt
from dataclasses import dataclass, field
from enum import Enum


class ContractKind(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ContractState(str, Enum):
    DRAFT = "DRAFT"
    SEALED = "SEALED"
    SUPERSEDED = "SUPERSEDED"   # an older draft replaced by a newer draft


class DayState(str, Enum):
    PLANNED = "PLANNED"
    NO_CONTRACT = "NO_CONTRACT"             # window arrived, no sealed contract
    OPEN = "OPEN"                           # wall is up
    RELEASED_EARLY = "RELEASED_EARLY"       # targets met, released at/after day_close
    CLOSED_COMPLETE = "CLOSED_COMPLETE"     # targets met by window_end
    CLOSED_INCOMPLETE = "CLOSED_INCOMPLETE" # window_end with targets unmet
    RECOVERED = "RECOVERED"                 # daemon was down during the window


class SessionState(str, Enum):
    DRAFT = "DRAFT"
    SEALED = "SEALED"
    ARMING = "ARMING"
    ACTIVE = "ACTIVE"
    SUCCESS = "SUCCESS"
    INCOMPLETE = "INCOMPLETE"
    BREAK_GLASS = "BREAK_GLASS"
    INTERRUPTED = "INTERRUPTED"
    ARMING_FAILED = "ARMING_FAILED"


class EvidenceClass(str, Enum):
    """Dossier 7.3 — these are NOT equivalent. A screenshot does not prove
    time spent; a passing test does not prove the whole task is correct."""
    OBSERVED = "OBSERVED"                # adapter saw it happen
    SUBMITTED = "SUBMITTED"              # user handed it over
    MACHINE_CHECKED = "MACHINE_CHECKED"  # command/artifact verified locally


class EvidenceVerdict(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ResearchPassState(str, Enum):
    OPEN = "OPEN"
    RETURNED = "RETURNED"
    EXPIRED = "EXPIRED"
    ABORTED = "ABORTED"


class BootcampState(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    TAPERED = "TAPERED"     # stage 2..4 (reduced/checkpoint/advisory)
    GRADUATED = "GRADUATED"
    ABANDONED = "ABANDONED"


class EnforcementLevel(str, Enum):
    """Dossier 3.3 — explicit levels; none is 'unbreakable'."""
    E1_BROWSER = "E1"   # extension + browser policies
    E2_OS = "E2"        # hosts/DNS, per-app firewall, process restriction
    E3_WORKSPACE = "E3" # separate standard account / kiosk / managed policy
    E4_EXTERNAL = "E4"  # trusted person holds admin or router control


class WorkMode(str, Enum):
    """Dossier 3.5 — three modes, never collapsed into one semantic score."""
    CLOSED_WORLD = "closed_world"     # allowlist only, deterministic
    BOUNDED_RESEARCH = "bounded_research"  # finite declared sources + expiry
    OPEN_EXPLORATION = "open_exploration"  # only via explicit cold-state choice


class ActivityClass(str, Enum):
    """Observations within ACTIVE — not new authorities (dossier 3.4)."""
    ON_TASK = "ON_TASK"
    PERMITTED_RESEARCH = "PERMITTED_RESEARCH"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"
    UNCLASSIFIED = "UNCLASSIFIED"


class Action(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    WARN = "WARN"   # advisory tier only: logged, never surfaced mid-session


class TelemetryQuality(str, Enum):
    OK = "OK"
    MISSING = "MISSING"      # source absent — NOT evidence of inactivity
    DEGRADED = "DEGRADED"
    SUSPECT = "SUSPECT"      # e.g. clock jumped backwards


class TaperStage(int, Enum):
    FULL_LOCK = 1
    REDUCED_LOCK = 2
    CHECKPOINT = 3           # tool asks before blocking; overrides logged
    ADVISORY = 4


@dataclass
class PolicyDecision:
    action: Action
    rule_id: str
    category: str = ""
    detail: str = ""


@dataclass
class DayWindow:
    """Resolved UTC instants for one local calendar date.

    window_end is the unconditional ceiling (D-018): whatever happened,
    everything releases at window_end. day_close is the earliest instant
    an early release may happen, and only when the day's targets are met.
    """
    local_date: _dt.date
    tz_name: str
    window_start: _dt.datetime
    day_close: _dt.datetime
    window_end: _dt.datetime

    def contains(self, at: _dt.datetime) -> bool:
        return self.window_start <= at <= self.window_end

    def after_day_close(self, at: _dt.datetime) -> bool:
        return at >= self.day_close

    def as_dict(self) -> dict:
        from .timeutil import to_iso
        return {
            "local_date": self.local_date.isoformat(),
            "timezone": self.tz_name,
            "window_start": to_iso(self.window_start),
            "day_close": to_iso(self.day_close),
            "window_end": to_iso(self.window_end),
        }


@dataclass
class ProbeResult:
    status: str            # INSTALLED | NOT_INSTALLED | ERROR
    detail: str = ""
    hint: str = ""         # where the setup guide lives, if not installed


@dataclass
class ArmingReport:
    armed: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    skipped: list = field(default_factory=list)   # disabled-by-config adapters

    @property
    def ok(self) -> bool:
        return not self.failed

    def disclosure(self) -> str:
        """Honest one-line disclosure of what is and is not enforcing."""
        parts = []
        if self.armed:
            parts.append("armed: " + ", ".join(self.armed))
        if self.failed:
            parts.append("FAILED: " + ", ".join(self.failed))
        if self.skipped:
            parts.append("not configured: " + ", ".join(self.skipped))
        return "; ".join(parts) or "no adapters configured"
