"""Central constants: default configuration and schema version.

Everything here is overridable via the user's dhriti.config.json.
The defaults encode the resolutions recorded in docs/RESOLUTIONS.md.
"""

import json
import os
from pathlib import Path

SCHEMA_VERSION = 6

APP_NAME = "dhriti"
HOMEDIR_ENV = "DHRITI_HOME"
BRIDGE_TOKEN_ENV = "DHRITI_BRIDGE_TOKEN"

DEFAULT_HOME = Path(os.environ.get(HOMEDIR_ENV) or (Path.home() / f".{APP_NAME}"))
DB_NAME = "dhriti.sqlite3"
DB_VIDURA_NAME = "vidura.sqlite3"
DB_PATH = DEFAULT_HOME / DB_NAME
DB_VIDURA_PATH = DEFAULT_HOME / DB_VIDURA_NAME

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
    "vidura": {
        # L-6: Vidura is off by default; enabling is a cold-state act.
        "enabled": False,
        "max_items": 5000,
    },
    # v0.7.0 Part 3 §3.1 — the saved-content mirror. Off by default
    # (L-6); every default respects the laws.
    "mirror": {
        "enabled": False,           # L-6
        "ingestion_interval_minutes": 15,
        "ingestion_only_in_evening": True,
        "max_items_per_ingestion": 500,
        "youtube": {
            "oauth_client_id_env": "DHRITI_YOUTUBE_CLIENT_ID",
            "oauth_client_secret_env": "DHRITI_YOUTUBE_CLIENT_SECRET",
            "oauth_refresh_token_path": "youtube_refresh_token",
            "sources": [{"type": "youtube_liked", "identifier": "LL",
                         "display_name": "Liked Videos",
                         "intent_class": "intent", "enabled": True}],
            "quota_budget_per_day": 8000,
            "quota_search_disallowed": True,
        },
        "ml_service": {"enabled": False,
                       "url": "http://127.0.0.1:8765",
                       "timeout_seconds": 10,
                       "fallback_to_rule": True},
        "surfacing": {
            "one_per_day": True,
            "one_per_day_when_opened": False,
            "surface_after_window_end": True,
            "surface_time_local": "21:00",
            "recall_before_reveal": True,
            "time_budget_narrowing_enabled": True,
            "max_age_days_for_surfacing": 365,
            "aged_out_after_days": 180,
            "degrade_after_consecutive_dismissals": 5,
            "degrade_to": "title_only",
        },
        "decay": {
            "use_stability": False,   # gate 3 (FSRS)
            "fsrs_v": "v4",
            "type_half_life_days": {"intent": 30, "reference": 180,
                                    "mixed": 60},
            "dismiss_penalty": 0.2,
            "open_boost": 0.3,
            "completion_boost": 0.5,
            "resave_boost": 0.2,
            "recall_failure_penalty": 0.4,
            "recall_success_boost": 0.15,
            "difficulty_cap": 2.0,
            "stability_bounds_ratio": 4.0,
        },
        "active_learning": {"enabled": True,
                            "confidence_threshold": 0.6,
                            "labels_per_review": 3},
        "privacy": {"store_descriptions": True,
                    "store_transcripts": False,
                    "delete_after_days": None},
    },
    # v0.7.0 Part 3 §3.2 — the life mirror (declared alternatives).
    "life_mirror": {"enabled": True},
    # v0.7.0 Part 3 §3.3 — declared device-use bounds. The honest
    # number is unknown; the per-navigation weight states the
    # assumption instead of hiding it.
    "declared_bounds": {
        "evening_minutes": 60,
        "unit": "minutes",
        "minutes_per_navigation": 3,
    },
    # v0.7.0 Part 3 §3.11 — the break-glass friction ladder.
    "break_glass_friction": {
        "baseline": {"delay_seconds": 60, "min_reason_words": 20},
        "physical": {"barcode_required": False,
                     "barcode_scan_dir": "~/.dhriti/barcodes",
                     "barcode_min_match_score": 0.85},
        "communication": {"otp_enabled": False,
                          "otp_provider": "email_to_sms",
                          "otp_gateway_email": "",
                          "otp_recipient_phone": "",
                          "otp_window_seconds": 300},
        "human": {"approval_enabled": False,
                  "approver_label": ""},
        "text": {"long_random_chars": 0},
        "time": {"max_delay_hours": 24},
        "escalation": {"enabled": True,
                       "tier_up_after_breaks_in_30_days": 2,
                       "tiers": ["baseline", "text", "communication",
                                 "physical"]},
    },
    # v0.7.0 Part 3 §3.12 — existing stack integration.
    "stack": {
        "cold_turkey": {"enabled": False, "executable": "",
                        "arm_cmd": [], "disarm_cmd": [],
                        "status_cmd": [], "delegate_domains": []},
        "nextdns": {"enabled": False, "profile_id": "",
                    "api_key_env": "DHRITI_NEXTDNS_API_KEY",
                    "log_poll_minutes": 15},
        "foqos": {"enabled": False, "barcode_dir": "~/.dhriti/barcodes"},
        "unhook": {"enabled": False,
                   "delegate_youtube_suppression": True},
        "brave_filters": {"enabled": False, "import_path": ""},
        "applock": {"enabled": False, "executable": "",
                    "status_cmd": []},
    },
    # v0.7.0 Part 3 §3.13 — the reflection bank (off by default: the
    # questions are harsh; enabling them is a cold-state act).
    "reflection_bank": {"enabled": False, "questions_per_week": 1},
    # v0.7.0 Part 3 §3.16 — the semantic topic-lock (L-9, off).
    "topic_lock": {
        "require_topic": True,
        "min_topic_chars": 10,
        "semantic_mode_enabled": False,   # L-9 exception; off by default
        "similarity_threshold": 0.65,
        "lexical_weight": 0.4,
        "embedding_weight": 0.6,
        "embedding_model": "local",
        "on_divergence": "pre_send",
        "park_button": True,
    },
    # v0.7.0 Part 4 — the rituals.
    "digest_extra": {
        "witness_mode": True,
        "one_true_thing_enabled": True,
    },
    "compost": {"interval_days": 90},
    "absence": {"max_days_per_month": 1},
    "ceremony": {"enabled": True},
    "meta_commitment": {"enabled": False},
    "quiet_hour": {"enabled": False, "start_local": "16:00",
                   "duration_minutes": 60},
    "debrief": {"enabled": True},
    "letters": {"enabled": True},
    "voice_archive": {"enabled": False},
    "wall": {"show_line_by_default": False},
    "archive": {"enabled": True},
    "confession": {"enabled": False},
    "aftermath_views": {"five_views": True},
    "database": {
        # Plan §4.10 / R-007: null = auto (DELETE on Windows, WAL
        # elsewhere). Force "delete" or "wal" explicitly if needed.
        "journal_mode": None,
    },
    "report": {
        "dir": "reports",
    },
    # Dhriti Guard Kit (v1.1 additions per D-071..D-089)
    "guard": {
        "prompt_budget_per_pass": 15,
        "burst": {"window_minutes": 10, "threshold": 3,
                  "toll_seconds": 10, "cooldown_minutes": 10},
        "debt": {"ceiling": 10.0, "accrual_per_event": 1.0,
                 "daily_decay": 0.5},
        "taper_schmitt": {"down_days": 3, "up_immediate": True},
        "length_limit_chars": 300,
        "pivot_budget": {"full_lock": 0, "reduced_lock": 1,
                         "checkpoint": None, "advisory": None},
    },
    "guard_sidecar": {
        "enabled": False,  # L-6: cold-state consent; off by default
        "host": "127.0.0.1",
        "port": 8765,
    },
    "retention": {
        "raw_text_days": 14,  # D-075: purge raw text after 14 days
    },
    "canary": {
        "e2_hostname": "dhriti-canary.invalid",
        "dom": True,
    },
    "metrics": {
        "park_break_floor": 2.0,
        "novelty_threshold": 3,
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
