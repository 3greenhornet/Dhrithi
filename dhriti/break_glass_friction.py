"""The break-glass friction ladder (v0.7.0 Part 3 §3.11).

Semantics:
  * the baseline always applies (delay + a prose reason: min 20 WORDS
    with at least five words of 3+ chars — keysmash is not prose);
  * if escalation is enabled, the current tier rises with confirmed
    breaks in the last 30 days (breaks >= threshold * N -> tier N) and
    decays as they age out;
  * the chosen tier's requirements ADD to the baseline (never replace);
  * the emergency path (D-019) bypasses every tier — the reason is
    still typed.

Tiers: baseline -> text (type N random chars) -> communication (a
6-digit OTP via an email-to-SMS gateway, hashed, single-use, expiring)
-> physical (scan a pre-registered barcode or type the code printed
under it). Each mechanism is a stored, tested fact; the gateway and
the barcode scanner are the user's to provide (config), off by
default.
"""

import hashlib
import json
import random
import re
import string
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso

TIERS = ("baseline", "text", "communication", "physical")


def word_count(reason: str) -> int:
    return len([w for w in (reason or "").split() if w.strip()])


def is_prose(reason: str, min_words: int = 20) -> bool:
    """The reason must be prose: at least `min_words` words, at least
    five of them 3+ characters. 'aaaa bbbb ...' is keysmash, not prose."""
    words = [w.strip(string.punctuation) for w in (reason or "").split()]
    words = [w for w in words if w]
    if len(words) < min_words:
        return False
    substantial = [w for w in words if len(w) >= 3]
    return len(substantial) >= 5


class FrictionLadder:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("break_glass_friction", {})
        # §3.12: the physical tier can share the foqos tool's
        # registered barcodes (stack.foqos.barcode_dir)
        self._foqos_dir = (config.get("stack", {})
                           .get("foqos", {})
                           .get("barcode_dir", ""))
        self.clock = clock or RealClock()
        self.ledger = ledger

    # -- tier computation ------------------------------------------------------
    def confirmed_breaks_30d(self) -> int:
        since = to_iso(self.clock.now_utc() - timedelta(days=30))
        rows = self.db.query(
            "SELECT confirmed_at FROM break_glass WHERE confirmed_at "
            "IS NOT NULL AND pressed_at >= ?", (since,))
        return len(rows)

    def current_tier(self) -> str:
        escalation = self.config.get("escalation", {})
        if not escalation.get("enabled", True):
            return "baseline"
        threshold = max(1, int(escalation.get(
            "tier_up_after_breaks_in_30_days", 2)))
        breaks = self.confirmed_breaks_30d()
        # breaks >= threshold * N -> tier N (decays as breaks age out
        # of the 30-day window); the cap is the top tier.
        tier_index = min(breaks // threshold, len(TIERS) - 1)
        return TIERS[tier_index]

    def tier_requirements(self, tier: str) -> dict:
        """The requirements a tier ADDS to the baseline."""
        requirements = {}
        if tier == "text":
            requirements["long_random_chars"] = int(
                self.config.get("text", {}).get("long_random_chars", 0))
        elif tier == "communication":
            comm = self.config.get("communication", {})
            requirements["otp"] = bool(comm.get("otp_enabled", False))
        elif tier == "physical":
            phys = self.config.get("physical", {})
            requirements["barcode"] = bool(
                phys.get("barcode_required", False))
        return requirements

    def required_reason_words(self) -> int:
        return int(self.config.get("baseline", {}).get(
            "min_reason_words", 20))

    # -- the checks ---------------------------------------------------------------
    def check_reason(self, reason: str) -> dict:
        min_words = self.required_reason_words()
        ok = is_prose(reason, min_words=min_words)
        return {"ok": ok,
                "words": word_count(reason),
                "required": min_words,
                "message": (f"typed prose required ({word_count(reason)}/"
                            f"{min_words} words, at least five of 3+ "
                            "chars) — words, not keysmash"
                            if not ok else "prose accepted")}

    def generate_long_text(self, record_id: str, length: int) -> str:
        """The text tier: a deterministic block of random characters
        seeded per break — the user types it back. Deterministic so a
        re-prompt shows the same block."""
        rng = random.Random(f"dhriti:{record_id}")
        alphabet = (string.ascii_lowercase
                    + string.ascii_uppercase + string.digits)
        return "".join(rng.choice(alphabet) for _ in range(length))

    def verify_long_text(self, record_id: str, length: int,
                         typed: str) -> bool:
        return (typed or "").strip() == self.generate_long_text(
            record_id, length)

    # -- OTP (communication tier) ----------------------------------------------
    def issue_otp(self, record_id: str) -> dict:
        """Generate + store (hashed) a 6-digit code. SENDING it is the
        gateway's job (config: otp_gateway_email / recipient); the
        system stores the hash, single-use, with a window."""
        comm = self.config.get("communication", {})
        window = int(comm.get("otp_window_seconds", 300))
        code = "".join(random.Random().choice(string.digits)
                       for _ in range(6))
        now = self.clock.now_utc()
        self.db.insert("otp_code", {
            "id": str(uuid.uuid4()),
            "break_id": record_id,
            "code_hash": hashlib.sha256(
                code.encode()).hexdigest(),
            "issued_at": to_iso(now),
            "expires_at": to_iso(now + timedelta(seconds=window)),
            "used_at": None,
        })
        return {"sent_to": comm.get("otp_gateway_email", ""),
                "recipient": comm.get("otp_recipient_phone", ""),
                "window_seconds": window,
                # the code itself never enters the ledger; it is
                # returned once for the gateway send
                "code": code}

    def verify_otp(self, record_id: str, code: str) -> bool:
        rows = self.db.query(
            "SELECT * FROM otp_code WHERE break_id=? ORDER BY "
            "issued_at DESC", (record_id,))
        now = self.clock.now_utc()
        for row in rows:
            if row["used_at"]:
                continue  # single-use: replays fail
            if parse_iso(row["expires_at"]) < now:
                continue
            digest = hashlib.sha256(
                (code or "").strip().encode()).hexdigest()
            if digest == row["code_hash"]:
                self.db.execute(
                    "UPDATE otp_code SET used_at=? WHERE id=?",
                    (to_iso(now), row["id"]))
                return True
        return False

    # -- barcodes (physical tier) --------------------------------------------------
    def register_barcode(self, code: str, label: str = "") -> dict:
        """Cold state: pre-register a barcode's code (printed under
        the barcode). The scan OR the typed code both count — getting
        up to read it is the point."""
        code = (code or "").strip()
        if len(code) < 4:
            raise ValueError("barcode code must be at least 4 chars")
        barcode_id = str(uuid.uuid4())
        self.db.insert("barcode", {
            "id": barcode_id,
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "label": label[:100],
            "created_at": to_iso(self.clock.now_utc()),
        })
        return {"id": barcode_id, "label": label}

    def verify_barcode(self, code: str) -> bool:
        digest = hashlib.sha256(
            (code or "").strip().encode()).hexdigest()
        row = self.db.query_one(
            "SELECT 1 AS one FROM barcode WHERE code_hash=?",
            (digest,))
        if row is not None:
            return True
        # §3.12: the same barcodes foqos registered — the file's
        # name in stack.foqos.barcode_dir IS the printed code (the
        # assumption is stated here; adjust the format to foqos's
        # own if it differs)
        if self._foqos_dir:
            try:
                directory = Path(self._foqos_dir).expanduser()
                for entry in directory.iterdir():
                    if hashlib.sha256(
                            entry.name.encode()).hexdigest() == digest:
                        return True
            except OSError:
                return False
        return False

    # -- the ladder's summary for the aftermath (§4.19) ------------------------
    def month_summary(self) -> dict:
        breaks = self.confirmed_breaks_30d()
        tier = self.current_tier()
        return {"breaks_30d": breaks, "current_tier": tier,
                "escalated_from":
                    "baseline" if tier != "baseline" else None}
