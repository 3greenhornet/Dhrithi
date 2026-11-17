"""The saved-content mirror (v0.7.0 Part 3 §3.1): event types.

The mirror records what you saved (YouTube likes, playlists, CSV
imports) and surfaces it back — one item a day, after the earned
evening, with recall before reveal. It is the inversion of the feed:
the pile is yours, the schedule is honest, and nothing is optimized.
"""

CONTENT_ITEM_SAVED = "content_item_saved"
CONTENT_ITEM_RESAVED = "content_item_resaved"
CONTENT_ITEM_CATEGORIZED = "content_item_categorized"
CONTENT_ITEM_SURFACED = "content_item_surfaced"
CONTENT_ITEM_RECALLED = "content_item_recalled"
CONTENT_ITEM_OPENED = "content_item_opened"
CONTENT_ITEM_PROGRESS = "content_item_progress"
CONTENT_ITEM_COMPLETED = "content_item_completed"
CONTENT_ITEM_DISMISSED = "content_item_dismissed"
CONTENT_ITEM_ABANDONED = "content_item_abandoned"
CONTENT_ITEM_REENTRY = "content_item_reentry"
CONTENT_ITEM_REENTRY_OUTCOME = "content_item_reentry_outcome"
CONTENT_ITEM_LABELED = "content_item_labeled"
SURFACE_INTENSITY_DEGRADED = "surface_intensity_degraded"
SURFACE_INTENSITY_RESTORED = "surface_intensity_restored"
MIRROR_OAUTH_EXPIRED = "mirror_oauth_expired"
MIRROR_QUOTA_EXHAUSTED = "mirror_quota_exhausted"
MIRROR_INGESTION_RETRY = "mirror_ingestion_retry"
MIRROR_INGESTION_MALFORMED = "mirror_ingestion_malformed"
ACTIVE_LEARNING_GATE_OPENED = "active_learning_gate_opened"
FSRS_SHADOW_GATE_OPENED = "fsrs_shadow_gate_opened"
FSRS_SHADOW_COMPUTED = "fsrs_shadow_computed"

ALL = (CONTENT_ITEM_SAVED, CONTENT_ITEM_RESAVED,
       CONTENT_ITEM_CATEGORIZED, CONTENT_ITEM_SURFACED,
       CONTENT_ITEM_RECALLED, CONTENT_ITEM_OPENED,
       CONTENT_ITEM_PROGRESS, CONTENT_ITEM_COMPLETED,
       CONTENT_ITEM_DISMISSED, CONTENT_ITEM_ABANDONED,
       CONTENT_ITEM_REENTRY, CONTENT_ITEM_REENTRY_OUTCOME,
       CONTENT_ITEM_LABELED, SURFACE_INTENSITY_DEGRADED,
       SURFACE_INTENSITY_RESTORED, MIRROR_OAUTH_EXPIRED,
       MIRROR_QUOTA_EXHAUSTED, MIRROR_INGESTION_RETRY,
       MIRROR_INGESTION_MALFORMED, ACTIVE_LEARNING_GATE_OPENED,
       FSRS_SHADOW_GATE_OPENED, FSRS_SHADOW_COMPUTED)
