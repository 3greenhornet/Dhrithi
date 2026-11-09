"""The journal: the experimenter's own log (operator toolkit #7).

A separate SQLite database (journal.sqlite3 in the home), NOT the main
ledger. The journal is private thinking about the experiment itself —
the cold review asks about behavior; the journal records how the
experiment is going. The main ledger records only the FACT that an
entry was added (journal_entry_added), never the content.
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from .timeutil import Clock, RealClock


class JournalService:
    def __init__(self, home: Path, clock: Optional[Clock] = None):
        self.home = Path(home)
        self.path = self.home / "journal.sqlite3"
        self.clock = clock or RealClock()
        self._conn = sqlite3.connect(str(self.path),
                                     check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS journal ("
            " id TEXT PRIMARY KEY,"
            " at_utc TEXT NOT NULL,"
            " text TEXT NOT NULL)")
        self._conn.commit()

    def add(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValueError("an empty journal entry is not an entry")
        row_id = str(uuid.uuid4())
        at = self.clock.iso()
        self._conn.execute(
            "INSERT INTO journal(id, at_utc, text) VALUES (?,?,?)",
            (row_id, at, text[:5000]))
        self._conn.commit()
        return {"id": row_id, "at_utc": at, "text": text}

    def list(self, since: Optional[str] = None) -> list:
        if since:
            rows = self._conn.execute(
                "SELECT id, at_utc, text FROM journal WHERE at_utc>=? "
                "ORDER BY at_utc", (since,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, at_utc, text FROM journal "
                "ORDER BY at_utc").fetchall()
        return [{"id": r[0], "at_utc": r[1], "text": r[2]} for r in rows]

    def export(self) -> str:
        return json.dumps(self.list(), indent=2, ensure_ascii=False)

    def close(self):
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass
