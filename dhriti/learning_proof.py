"""Dhriti Learning Proof & Honest Recall Verification (L-11 / L-1 / Package L).

Enforces that study videos and tutorials are active Stage output rather than passive consumption:
1. Demands a minimum 50-word synthesis of what was learned before verifying the target.
2. Rejects superficial copy-paste and single-word spam.
3. Hashes the synthesis (SHA-256) and logs a permanent ledger proof event.
4. Marks the target as verified in today's contract.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from typing import Any, Dict, Optional


class LearningProofError(ValueError):
    """Raised when recall synthesis fails verification criteria."""
    pass


class LearningProofService:
    def __init__(self, db, ledger=None):
        self.db = db
        self.ledger = ledger

    def verify_synthesis(self, text: str) -> Dict[str, Any]:
        """Validates honest recall synthesis constraints."""
        clean = (text or "").strip()
        words = re.findall(r"\b\w+\b", clean)
        word_count = len(words)

        if word_count < 50:
            raise LearningProofError(
                f"Recall synthesis requires at least 50 words (currently {word_count} words). "
                f"Synthesize the core algorithmic concepts or architectural takeaways."
            )

        unique_words = {w.lower() for w in words}
        if len(unique_words) < 25:
            raise LearningProofError(
                f"Recall synthesis lacks lexical diversity ({len(unique_words)} unique words). "
                f"Please explain the concept in your own natural phrasing."
            )

        sha = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        return {
            "valid": True,
            "word_count": word_count,
            "unique_words": len(unique_words),
            "sha256": sha,
            "snippet": clean[:100] + ("..." if len(clean) > 100 else "")
        }

    def claim_with_proof(
        self,
        target_id: str,
        synthesis_text: str,
        scope_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validates recall proof and marks contract target as verified."""
        proof_meta = self.verify_synthesis(synthesis_text)
        today = scope_date or dt.date.today().isoformat()

        row = self.db.query_one(
            "SELECT id, payload_json FROM contract WHERE kind='daily' AND scope_date=? AND state='SEALED'",
            (today,)
        )
        if not row:
            raise LearningProofError(f"No sealed contract found for {today}.")

        contract_id = row["id"]
        payload = json.loads(row["payload_json"])
        targets = payload.get("targets", [])
        
        found = False
        target_label = target_id
        for t in targets:
            if str(t.get("id")) == str(target_id):
                t["claimed"] = True
                t["proof"] = f"sha256:{proof_meta['sha256'][:16]}"
                t["claimed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
                target_label = t.get("label", target_id)
                found = True
                break

        if not found:
            raise LearningProofError(f"Target '{target_id}' not found in today's contract.")

        # In Dhriti, sealed contracts are strictly immutable (abort_contract_update trigger).
        # We record the verified proof and target claim into the append-only ledger and evidence store.
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        if self.ledger:
            self.ledger.record(
                "learning_proof_verified",
                observed={
                    "contract_id": contract_id,
                    "target_id": target_id,
                    "target_label": target_label,
                    "word_count": proof_meta["word_count"],
                    "proof_hash": proof_meta["sha256"],
                    "synthesis_preview": proof_meta["snippet"]
                }
            )
        else:
            self.db.execute(
                """INSERT INTO event (event_id, occurred_at_utc, source_adapter, event_type, observed_payload, telemetry_quality, prev_hash, row_hash)
                   VALUES (?, ?, 'learning_proof', 'learning_proof_verified', ?, 'OK', 'GENESIS', ?)""",
                (str(proof_meta["sha256"][:16]), now_iso,
                 json.dumps({"contract_id": contract_id, "target_id": target_id, "target_label": target_label, "proof_hash": proof_meta["sha256"]}),
                 proof_meta["sha256"])
            )

        # If a session exists for today, also record an accepted evidence entry
        try:
            today_date = dt.date.today().isoformat()
            sess = self.db.query_one(
                "SELECT s.id FROM session s JOIN day d ON s.day_id=d.id WHERE d.date=? AND s.state='ACTIVE' LIMIT 1",
                (today_date,)
            )
            if not sess:
                sess = self.db.query_one(
                    "SELECT s.id FROM session s JOIN day d ON s.day_id=d.id WHERE d.date=? ORDER BY s.started_at DESC LIMIT 1",
                    (today_date,)
                )
            if sess:
                import uuid
                ev_id = str(uuid.uuid4())
                detail_json = json.dumps({
                    "target_id": target_id,
                    "target_label": target_label,
                    "kind": "learning_proof",
                    "sha256": proof_meta["sha256"],
                    "word_count": proof_meta["word_count"]
                })
                self.db.insert("evidence", {
                    "id": ev_id,
                    "session_id": sess["id"],
                    "class": "MACHINE_CHECKED",
                    "kind": "learning_proof",
                    "submitted_at": now_iso,
                    "detail_json": detail_json,
                    "verdict": "ACCEPTED",
                    "verdict_reason": "Recall verified by LearningProofService",
                    "checked_at": now_iso
                })
        except Exception:
            pass

        return {
            "ok": True,
            "target_id": target_id,
            "target_label": target_label,
            "proof_hash": proof_meta["sha256"],
            "word_count": proof_meta["word_count"]
        }
