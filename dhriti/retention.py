"""Dhriti Guard Kit -- retention CLI glue (D-075 answer to "deleted from
time to time??").

Purge the sidecar content store on a schedule; chain only the FACT
(counts), never the text. Wire into cli.py as:

    import argparse  # already imported there
    from dhriti.retention import cmd_retention
    sub = subparsers.add_parser("retention", help="purge expired raw text")
    sub.add_argument("--purge-raw-after", type=int, default=None,
                     help="override retention.raw_text_days (dry info)")
    sub.add_argument("--execute", action="store_true")
    sub.set_defaults(func=cmd_retention)

Answer to the recurring question: yes -- raw text is deleted on a TTL; the
verdicts and hashes stay forever (they ARE the N-of-1 dataset).
"""

from __future__ import annotations

from typing import Optional


def cmd_retention(args, config: dict, store) -> int:
    """store: an already-opened ContentStore. Returns 0 on success.
    config: DEFAULT_CONFIG['retention'] = {"raw_text_days": 14}."""
    days = getattr(args, "purge_raw_after", None) or \
        config.get("raw_text_days", 14)
    if not getattr(args, "execute", False):
        stats = store.stats()
        print(f"retention policy: raw text kept {days} days")
        print(f"sidecar stats: {stats}")
        print("dry run -- pass --execute to purge now")
        return 0
    purged = store.purge_expired()
    print(f"purged {purged} expired content rows")
    # Caller: append ledger event {"type": "guard_content_purged",
    #                              "count": purged}  -- the fact, not text.
    return 0


def schedule_hint() -> str:
    return (
        "schtasks /Create /TN \"Dhriti retention purge\" /SC DAILY /ST 03:30 "
        "/TR \"python -m dhriti.cli retention --execute\""
    )
