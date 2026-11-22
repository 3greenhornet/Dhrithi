"""Dhriti Declared Pivot Service (L-6 §6.3 / Package F).

Permits bounded hot target additions mid-session when study priorities shift
(e.g., pivoting to an urgent aptitude drill or unblocking a placement topic)
without mutating the immutable sealed contract.
"""

import datetime as dt
import uuid
from typing import Dict, List, Optional

FORBIDDEN_PIVOT_WORDS = {
    "porn", "xxx", "hentai", "nsfw", "erotic", "sex", "adult",
    "gaming", "gameplay", "fortnite", "valorant", "steam", "minecraft",
    "anime", "manga", "netflix", "hotstar", "prime", "movie", "series",
    "tiktok", "instagram", "reels", "shorts", "meme"
}


class PivotError(ValueError):
    """Raised when a pivot declaration fails bounded constraints."""
    pass


class PivotService:
    """Manages hot bounded target pivots for the active day."""

    def __init__(self, db, clock=None, ledger=None, max_per_day: int = 3):
        self.db = db
        self.clock = clock
        self.ledger = ledger
        self.max_per_day = max_per_day
        self._ensure_table()

    def _ensure_table(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS day_pivot(
                id TEXT PRIMARY KEY,
                day_id TEXT,
                topic TEXT NOT NULL,
                reason TEXT NOT NULL,
                units REAL NOT NULL DEFAULT 1.0,
                declared_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                source_query_sha TEXT
            )
        """)

    def _now(self) -> dt.datetime:
        if self.clock:
            return self.clock.now_utc()
        return dt.datetime.now(dt.timezone.utc)

    def remaining_today(self, day_date: Optional[str] = None) -> int:
        target_date = day_date or self._now().date().isoformat()
        rows = self.db.query(
            "SELECT COUNT(*) as cnt FROM day_pivot WHERE date(declared_at)=?",
            (target_date,)
        )
        used = rows[0]["cnt"] if rows else 0
        return max(0, self.max_per_day - used)

    def list_active_pivots(self, day_date: Optional[str] = None) -> List[Dict]:
        now_iso = self._now().isoformat()
        target_date = day_date or self._now().date().isoformat()
        rows = self.db.query("""
            SELECT * FROM day_pivot
            WHERE date(declared_at)=? AND expires_at > ? AND consumed_at IS NULL
            ORDER BY declared_at DESC
        """, (target_date, now_iso))
        return rows

    def declare(self, topic: str, reason: str, minutes: int = 120,
                day_id: Optional[str] = None, source_sha: Optional[str] = None) -> Dict:
        """Declares a hot bounded pivot for today."""
        topic_clean = (topic or "").strip()
        reason_clean = (reason or "").strip()

        if not topic_clean:
            raise PivotError("Topic description cannot be empty.")

        # 1. Reason constraints (prose, min length)
        words = reason_clean.split()
        if len(reason_clean) < 15 or len(words) < 3:
            raise PivotError("Pivot reason must be at least 15 characters and at least 3 words explaining intent.")

        # 2. Daily Cap Check
        now = self._now()
        date_iso = now.date().isoformat()
        if self.remaining_today(date_iso) <= 0:
            raise PivotError(f"Daily pivot limit reached ({self.max_per_day}/day maximum).")

        # 3. Forbidden Category Check
        topic_lower = topic_clean.lower()
        for forbidden in FORBIDDEN_PIVOT_WORDS:
            if forbidden in topic_lower:
                if self.ledger:
                    self.ledger.record("pivot_refused", observed={"topic": topic_clean, "reason": "forbidden_category"})
                raise PivotError(f"Pivot rejected: '{forbidden}' belongs to a non-study/entertainment category.")

        # 4. Expiry Calculation
        expires = now + dt.timedelta(minutes=minutes)
        row_id = str(uuid.uuid4())
        pivot_row = {
            "id": row_id,
            "day_id": day_id,
            "topic": topic_clean,
            "reason": reason_clean,
            "units": 1.0,
            "declared_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "consumed_at": None,
            "source_query_sha": source_sha
        }
        self.db.insert("day_pivot", pivot_row)

        if self.ledger:
            self.ledger.record("pivot_declared", observed={
                "pivot_id": row_id,
                "topic": topic_clean,
                "expires_at": expires.isoformat()
            })

        # Also register as safe anchor in topic gate for immediate recognition
        try:
            from .topic_gate import TopicGate
            gate = TopicGate(self.db)
            gate.add_safe_anchor(topic_clean, source="declared_pivot")
        except Exception:
            pass

        return pivot_row
