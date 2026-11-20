"""Dhriti Topic Extraction Engine (D-091 / L-11).

Extracts semantic tokens, co-occurrence chips, query parameters,
and hierarchical child topics from committed navigation metadata (URLs and page titles).
Standard library only; zero cloud dependencies.
"""

from __future__ import annotations

import re
import urllib.parse
from collections import Counter
from typing import List, Dict, Any, Set

_STOP = {
    "the", "a", "an", "of", "in", "on", "and", "to", "for", "with", "how", "why",
    "what", "is", "are", "was", "video", "videos", "watch", "shorts", "from",
    "by", "at", "this", "that", "it", "as", "or", "an", "be", "about"
}


def tokens(text: str) -> List[str]:
    """Extract clean tokens of length > 2, excluding common stopwords."""
    return [
        t for t in re.findall(r"[a-z0-9']+", (text or "").lower())
        if t not in _STOP and len(t) > 2
    ]


def query_of(url: str) -> str:
    """Extract committed query string (?q=, ?search_query=) from search/video URLs."""
    try:
        parsed = urllib.parse.urlparse(url)
        q_dict = urllib.parse.parse_qs(parsed.query)
        for key in ("q", "search_query", "query"):
            vals = q_dict.get(key)
            if vals and vals[0]:
                return vals[0].replace("+", " ").strip()
        return ""
    except Exception:
        return ""


def chips(query: str, title: str) -> List[str]:
    """Co-occurrence pairs, order-insensitive (e.g. 'naruto manga' -> 'naruto + manga')."""
    seen: Set[str] = set()
    toks = tokens(query)
    ttl = set(tokens(title))
    pairs: List[str] = []

    # Intra-query token pairs
    for i, a in enumerate(toks):
        for b in toks[i + 1:]:
            pairs.append(f"{a} + {b}")

    # Cross-query and title token pairs
    for a in toks:
        for b in ttl:
            if a != b:
                pairs.append(f"{a} + {b}")

    out: List[str] = []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def children_of(genre: str, events: List[Dict[str, Any]]) -> Dict[str, float]:
    """Extract subtopics observed near a genre token (e.g. Uchiha, Minato near Naruto)."""
    c: Counter[str] = Counter()
    genre_lower = genre.lower()
    for ev in events:
        toks = ev.get("tokens", [])
        minutes = float(ev.get("minutes", 1.0))
        if genre_lower in toks:
            gi = toks.index(genre_lower)
            # Window of +/- 3 tokens around genre
            for t in toks[max(0, gi - 3): gi + 4]:
                if t != genre_lower and t not in _STOP:
                    c[t] += minutes
    return {k: round(v, 1) for k, v in c.most_common(12) if v >= 0.5}
