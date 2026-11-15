"""The search-escape detector (v0.7.0 Part 3 §3.4).

Method: scan browser_navigation events; extract the query string from
Google/Brave/DuckDuckGo/Bing/YouTube search URLs (the ?q= parameter —
structure, not content reading: the query is already in the record);
join to unopened mirror items by category keyword match. A search for
what you already saved IS the escape: the pile answers the question.

`dhriti search-escape report --since YYYY-MM-DD` populates the
search_escape table and prints the join.
"""

from datetime import timedelta
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso

SEARCH_HOSTS = ("google.", "search.brave.com", "duckduckgo.com",
                "bing.com", "www.youtube.com", "youtube.com")


def extract_query(url: str) -> Optional[str]:
    """The ?q= (or YouTube's search_path) query — structure, not
    content: the URL is already an event in the ledger."""
    try:
        parsed = urlparse(url or "")
        host = (parsed.hostname or "").lower()
        if not any(h in host for h in SEARCH_HOSTS):
            return None
        if "youtube" in host and parsed.path == "/results":
            params = parse_qs(parsed.query)
            return (params.get("search_query") or [None])[0]
        params = parse_qs(parsed.query)
        return (params.get("q") or [None])[0]
    except Exception:
        return None


class SearchEscapeDetector:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config
        self.clock = clock or RealClock()
        self.ledger = ledger

    def detect(self, since_iso: str) -> list:
        """Scan navigations since `since_iso`; for each search query,
        join to unopened items by category keyword; record rows in
        search_escape. Returns the rows."""
        rows = self.db.query(
            "SELECT occurred_at_utc, observed_payload FROM event "
            "WHERE event_type='browser_navigation' AND "
            "occurred_at_utc >= ? ORDER BY occurred_at_utc",
            (since_iso + "T00:00:00Z",))
        escapes = []
        for row in rows:
            try:
                payload = json_loads(row["observed_payload"])
            except Exception:
                continue
            query = extract_query(payload.get("url", ""))
            if not query or not query.strip():
                continue
            query = query.strip()[:200]
            host = urlparse(payload.get("url", "")).hostname or ""
            category, count, oldest_days = self._join(query)
            if category is None:
                continue
            now = to_iso(self.clock.now_utc())
            self.db.insert("search_escape", {
                "computed_at": now,
                "search_at": row["occurred_at_utc"],
                "search_query": query,
                "search_host": host,
                "matched_category": category,
                "unopened_count": count,
                "oldest_unopened_days": oldest_days,
            })
            escapes.append({
                "query": query, "host": host, "category": category,
                "unopened_count": count,
                "oldest_unopened_days": oldest_days})
        return escapes

    def _join(self, query: str):
        """Match the query to an unopened-item category via the
        classifier's keywords; return (category, unopened_count,
        oldest_days) or (None, 0, 0)."""
        from .mirror.classify_rule import classify
        verdict = classify(query)
        category = verdict["category"]
        if category == "unknown":
            return None, 0, 0
        row = self.db.query_one(
            "SELECT COUNT(*) AS n, MIN(saved_at_utc) AS oldest FROM "
            "content_item WHERE category=? AND opened_at IS NULL AND "
            "abandoned_at IS NULL AND aged_out_at IS NULL",
            (category,))
        if not row or not row["n"]:
            return None, 0, 0
        oldest_days = 0
        if row["oldest"]:
            oldest_days = (self.clock.now_utc()
                           - parse_iso(row["oldest"])).days
        return category, row["n"], oldest_days

    def week_summary(self, week_start_iso: str) -> list:
        """The aftermath's search-escape lines: query -> N searches, M
        unopened items of the matched category."""
        start = week_start_iso + "T00:00:00Z"
        end = (parse_iso(week_start_iso + "T00:00:00Z")
               + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self.db.query(
            "SELECT search_query, COUNT(*) AS searches, "
            "matched_category, MAX(unopened_count) AS unopened FROM "
            "search_escape WHERE search_at>=? AND search_at<? "
            "GROUP BY search_query ORDER BY searches DESC",
            (start, end))
        return rows


def json_loads(text):
    import json
    return json.loads(text or "{}")
