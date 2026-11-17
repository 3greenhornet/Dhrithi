"""Dhriti Guard Kit -- CT-style witness verification (D-084 customise).

Certificate Transparency's trick applied to the witness protocol: the
witness stores only an anchor (a hash), never content. Later, any day can
be proven to be in the chain by revealing just the chain segment from an
anchor to the claimed head -- the witness recomputes hashes and compares.

ADAPTATION POINT (the one seam you must align): this module assumes
    event["hash"] = sha256(prev_hash_utf8 + canonical_json(event_without_hash))
Open dhriti/ledger.py and match `event_hash` to your exact concatenation
order/encoding. Everything else is generic.

stdlib only. The witness needs nothing but this file and the exported
bundle (verify with: python anchor_proof.py --verify bundle.json).
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Optional


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def event_hash(prev_hash: str, event: dict) -> str:
    """THE SEAM. Align with dhriti/ledger.py's exact hash construction."""
    payload = {k: v for k, v in event.items() if k != "hash"}
    return hashlib.sha256(
        (prev_hash + canonical(payload)).encode("utf-8")).hexdigest()


def verify_segment(anchor_event: dict, events: list[dict],
                   head_hash: str) -> tuple[bool, str]:
    """Recompute the chain from the anchor through the segment and compare
    to the claimed head. Witness-side: no content trust required."""
    prev = anchor_event.get("hash")
    if not prev:
        return False, "anchor event carries no hash"
    for ev in events:
        expected = event_hash(prev, ev)
        actual = ev.get("hash")
        if actual != expected:
            return False, f"chain break at offset {events.index(ev)}: " \
                          f"expected {expected[:16]}, got {str(actual)[:16]}"
        prev = actual
    return (prev == head_hash,
            "verified" if prev == head_hash
            else f"head mismatch: recomputed {prev[:16]}, claimed "
                 f"{str(head_hash)[:16]}")


def export_segment(all_events: list[dict], anchor_seq: int,
                   upto_seq: Optional[int] = None) -> dict:
    """Build the bundle the witness stores/verifies. all_events is the
    ledger's ordered event list (each with 'seq' and 'hash').
    Includes the anchor event and everything after it (optionally up to
    upto_seq)."""
    anchor = next((e for e in all_events if e.get("seq") == anchor_seq), None)
    if anchor is None:
        raise ValueError(f"no event with seq={anchor_seq}")
    seg = [e for e in all_events
           if e["seq"] > anchor_seq and (upto_seq is None
                                         or e["seq"] <= upto_seq)]
    return {"anchor": anchor, "events": seg,
            "head_hash": seg[-1]["hash"] if seg else anchor["hash"],
            "algorithm": "sha256(prev + canonical_json(event minus hash))"}


def verify_bundle(bundle: dict) -> tuple[bool, str]:
    return verify_segment(bundle["anchor"], bundle["events"],
                          bundle["head_hash"])


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--verify":
        with open(sys.argv[2], "r", encoding="utf-8") as fh:
            ok, detail = verify_bundle(json.load(fh))
        print(("VERIFIED: " if ok else "FAILED: ") + detail)
        sys.exit(0 if ok else 1)
    print("usage: python anchor_proof.py --verify bundle.json")
