"""Central constants: default configuration and schema version.

Everything here is overridable via the user's dhriti.config.json.
The defaults encode the resolutions recorded in docs/RESOLUTIONS.md.
"""

import json
import os
from pathlib import Path

SCHEMA_VERSION = 1

APP_NAME = "dhriti"
HOMEDIR_ENV = "DHRITI_HOME"
BRIDGE_TOKEN_ENV = "DHRITI_BRIDGE_TOKEN"

# Six founding principles (PDF section 2.3) — referenced by TRACEABILITY.md.
PRINCIPLES = [
    "commitment_precedes_temptation",
    "no_in_the_moment_negotiation",
    "discomfort_is_anticipated",
    "execution_outranks_analysis",
    "commitments_have_visible_consequences",
    "enforcement_over_sustained_period",
]

DEFAULT_CONFIG = {
    # Personal experiment parameters, not universal science (dossier 6.2).
    "timezone": "Asia/Kolkata",
    "day_window": {
        # Resolution of the PDF section 3.6 / dossier D-018 contradiction:
        #   window_end  = hard ceiling, everything releases unconditionally
        #                 (bounded release — never an indefinite lock),
        #   day_close   = earliest possible early release, only if the
        #                 day's targets are already met,
        #   finishing early never releases before day_close (closes the
        #                 easy-contract loophole, PDF 3.7).
        "start": "10:00",
        "end": "21:00",
        "day_close": "20:00",
    },
    "break_glass": {
        "delay_seconds": 60,          # PDF 7.2.1 — the toll's waiting room
        "cooldown_hours": 2,          # PDF 7.2.5 — no break/restart loops
        "min_reason_chars": 20,       # typed words, not a dropdown
        "emergency_min_reason_chars": 10,  # D-019 — shorter, still typed
        "penalties": [],              # cold-state declared, never auto-executed
    },
    "surface_suppression": {
        # D-024 (DECIDED): the default interface is retrieval, not
        # recommendation. The springboard (feeds, autoplay, related
        # links, AI follow-up suggestions) is suppressed during strict
        # sessions. The domain stays allowed; the surface is removed.
        "enabled": True,
    },
    "builder_clause": {
        # R-001 made mechanical ("the plan becomes the avoidance"): while
        # the day's targets are unmet, the listed domains (the Dhriti
        # repo itself, its host) are blocked — building the tool is a
        # privilege earned by meeting the day's target, exactly like any
        # other substitute. OFF by default: enabling it is a cold-state
        # decision recorded in the config, ideally witnessed in a digest.
        "enabled": False,
        "blocked_domains": [],
    },
    "digest": {
        # Minimal E4 dead-man's switch: the weekly digest a trusted human
        # should receive. The label only documents intent; sending stays
        # manual (no credentials in config, no silent email).
        "recipient_label": "",        # e.g. "the one human who cares"
    },
    "stage_ratio": {
        # D-046: the subject's own metric, in his own vocabulary —
        # stage vs. audience ("i too am a audience for 90% of time").
        # The band below is the one he endorsed in Specimen 001
        # (70–80% stage / 20–30% audience). The measure is
        # deterministic: navigation counts by category, never content.
        # Counts are not minutes; duration-grade ratios need
        # ActivityWatch. Facts only — the reader judges the distance.
        "audience_band": [0.2, 0.3],
    },
    "observation_evening": {
        # D-048: enforcement correctly ends at window_end; observation
        # currently ends with it — the evening hole. When enabled (a
        # cold-state consent act under the surveillance_comfort review
        # question), category observation continues after window_end
        # until day_end: the hole becomes measured, not closed. Counts
        # only (D-014 absolute): no content, no keystrokes, no
        # screenshots — the same navigation events, observed longer.
        "enabled": False,
        "day_end": "23:59",
    },
    "earned_evening": {
        # D-049: the specimen's own protocol, generalized from the
        # builder clause — "no video, no explanation, no philosophical
        # question to an AI, until one practice problem is compiled or
        # 25 minutes are spent coding." When enabled (cold-state act,
        # exactly like D-035), on days whose targets were NOT met the
        # configured consumption categories stay blocked after
        # window_end until day_end (bounded, never indefinite — D-018).
        # Days that met their targets release to an open evening:
        # consumption is earned by evidence, not by the clock.
        # Break-glass still exists and is the honest exit.
        "enabled": False,
        "blocked_categories": ["video", "social", "ai_chat", "games",
                               "entertainment"],
    },
    "bridge": {
        "host": "127.0.0.1",
        "port": 7311,
        "token_file": "bridge_token",  # inside the Dhriti home
        "policy_ttl_minutes": 720,     # extension fail-safe cache lifetime
    },
    "ledger": {
        "anchor_interval_events": 100,  # hash-chain checkpoint frequency
    },
    "enforcement": {
        "level": "E1",                          # E1..E4, see docs/ENFORCEMENT_LEVELS.md
        "required_adapters": ["extension_bridge"],
    },
    "adapters": {
        "activitywatch": {"enabled": False, "url": "http://127.0.0.1:5600"},
        "sysmon": {"enabled": False, "export_dir": ""},
        "screenpipe": {"enabled": False, "url": "http://127.0.0.1:3030"},
        "focusme": {"enabled": False, "executable": "", "arm_cmd": [], "disarm_cmd": []},
        "cold_turkey": {"enabled": False, "executable": "", "arm_cmd": [], "disarm_cmd": []},
        "plucky": {"enabled": False, "executable": "", "arm_cmd": [], "disarm_cmd": []},
        "focuser": {"enabled": False, "executable": "", "arm_cmd": [], "disarm_cmd": []},
        "hosts_file": {"enabled": False, "blocked_domains": []},
    },
    "taper": {
        # Evidence-based taper thresholds (PDF 9.3, dossier D-022).
        # Personal experimental parameters — tune from your own data.
        "min_days": 30,
        "compliance_threshold": 0.80,      # share of days with targets met
        "proof_threshold": 0.70,           # share of sessions with accepted proof
        "breakglass_max_per_week": 1,
    },
    "research_pass": {
        "default_max_minutes": 20,         # bounded research allowance
    },
    "database": {
        # Plan §4.10 / R-007: null = auto (DELETE on Windows, WAL
        # elsewhere). Force "delete" or "wal" explicitly if needed.
        "journal_mode": None,
    },
    "report": {
        "dir": "reports",
    },
}


def default_home() -> Path:
    """Dhriti home directory: $DHRITI_HOME or ~/.dhriti."""
    env = os.environ.get(HOMEDIR_ENV)
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".dhriti"


def load_config(home: Path) -> dict:
    """Load config from <home>/dhriti.config.json, deep-merged over defaults."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    path = home / "dhriti.config.json"
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        _deep_merge(cfg, user)
    return cfg


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
