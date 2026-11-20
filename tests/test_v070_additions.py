import datetime
import sqlite3
import tempfile
from pathlib import Path
import pytest

from dhriti.topic_extract import tokens, query_of, chips, children_of
from dhriti.topic_time import day_histogram
from dhriti.life_bubbles import BubbleScheduler
from dhriti.decompression import DecompressionManager
from dhriti.task_balancer import (
    unit_value,
    calculate_daily_load,
    pick_your_poison,
    evaluate_auto_fill
)
from dhriti.vidura_corpus import ViduraCorpus


class MockClock:
    def __init__(self, now_dt):
        self._now = now_dt

    def now_utc(self):
        return self._now

    def advance(self, seconds):
        self._now += datetime.timedelta(seconds=seconds)


class MockDB:
    def __init__(self):
        self.rows = [
            {"id": "alt-1", "label": "Back exercises", "kind": "physical", "minimum_version": "v0.7.0"}
        ]

    def query(self, sql, params=()):
        if "life_alternative" in sql:
            return self.rows
        return []


class MockLedger:
    def __init__(self):
        self.events = []

    def record(self, event_type, observed=None, action_taken=None, telemetry_quality="OK"):
        self.events.append((event_type, observed or {}))


def test_topic_extract_basics():
    toks = tokens("Building Rust Compiler with AST Parser and LLVM Backend")
    assert "compiler" in toks
    assert "parser" in toks
    assert "backend" in toks
    assert "with" not in toks  # Stopword removed

    q = query_of("https://www.google.com/search?q=merge+sort+complexity+proof&hl=en")
    assert q == "merge sort complexity proof"

    ch = chips(query="naruto manga", title="chapter 500 discussion")
    assert len(ch) >= 1

    events = [
        {"domain": "youtube.com", "tokens": ["naruto", "shippuden", "minato", "rasengan"], "minutes": 15},
        {"domain": "github.com", "tokens": ["rust", "compiler"], "minutes": 45}
    ]
    children = children_of("naruto", events)
    assert "minato" in children


def test_topic_time_histogram():
    events = [
        {"host": "github.com", "minutes": 30.0, "on_topic": True, "genre": "code"},
        {"host": "reddit.com", "minutes": 10.0, "on_topic": False, "genre": "entertainment"}
    ]
    hist = day_histogram(events)
    assert "github.com" in hist["hosts"]
    assert len(hist["hosts"]["github.com"]["segments"]) >= 1
    assert hist["total_minutes"] == 40.0
    assert hist["stage_minutes"] == 30.0
    assert hist["audience_minutes"] == 10.0


def test_life_bubbles_scheduler():
    clock = MockClock(datetime.datetime(2026, 11, 20, 10, 0, 0))
    clock.iso = lambda: clock.now_utc().isoformat()
    db = MockDB()
    ledger = MockLedger()

    scheduler = BubbleScheduler(db, clock, ledger, cfg={"max_shown_per_day": 5, "min_gap_seconds": 10})

    bubble = scheduler.next()
    assert bubble is not None
    assert bubble["id"] == "alt-1"

    # Resolve
    scheduler.resolve("alt-1", outcome="done")
    assert len(ledger.events) >= 1


def test_decompression_manager():
    now_t = 1000.0
    mgr = DecompressionManager(config={"window_minutes": 90, "springboard_strikes_allowed": 3})
    start_info = mgr.start(now=now_t)
    assert mgr.active is True
    assert mgr.window_minutes == 90

    # Google search allowed
    res_search = mgr.evaluate_navigation(url="https://www.google.com/search?q=rust+syntax", now=now_t + 60)
    assert res_search["allowed"] is True

    # YouTube blocked
    res_yt = mgr.evaluate_navigation(url="https://www.youtube.com/watch?v=123", category="video", now=now_t + 120)
    assert res_yt["allowed"] is False
    assert res_yt["action"] == "block"


def test_task_balancer():
    units = unit_value("hard")
    assert units == 2.0

    load = calculate_daily_load([{"tier": "light"}, {"tier": "medium"}, {"tier": "hard"}])
    assert load == 3.5

    backlog = [
        {"id": "t1", "title": "Small bug fix", "tier": "light", "units": 0.5},
        {"id": "t2", "title": "Refactor router", "tier": "medium", "units": 1.0},
        {"id": "t3", "title": "Database migration", "tier": "hard", "units": 2.0}
    ]
    options = pick_your_poison(deficit_units=2.0, pool=backlog)
    assert len(options) >= 1

    autofill = evaluate_auto_fill(today_targets=[{"tier": "light"}], backlog=backlog, avg_units=3.0)
    assert autofill["needed"] is True
    assert len(autofill["auto_added"]) >= 1


def test_vidura_corpus():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "vidura.sqlite3"
        corpus = ViduraCorpus(db_path)

        # Topic tree hierarchy
        root_id = corpus.ensure_topic("Computer Science")
        child_id = corpus.ensure_topic("Compilers", parent_label="Computer Science")

        tree = corpus.get_topic_tree()
        assert len(tree) == 1
        assert tree[0]["id"] == root_id
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["id"] == child_id

        # Content item & FTS5 search
        item_id = corpus.add_item(
            url="https://llvm.org/docs/tutorial",
            title="LLVM Compiler Tutorial",
            description="Building a compiler frontend with AST and code generation."
        )

        results = corpus.search("frontend AST")
        assert len(results) == 1
        assert results[0]["id"] == item_id
