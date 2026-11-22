"""Tests for Browser Bookmarks Ingestion Watcher Daemon (§6.6.3 / §19.3)."""

import json
import os
import tempfile
import time
from pathlib import Path
import pytest

from dhriti.vidura_corpus import ViduraCorpus
from dhriti.vidura_watcher import (
    BookmarksWatcher,
    find_platform_bookmark_paths,
    BookmarkChangeHandler,
)


@pytest.fixture
def temp_vidura_corpus(tmp_path):
    db_path = tmp_path / "vidura.sqlite3"
    return ViduraCorpus(db_path)


@pytest.fixture
def sample_bookmarks_json(tmp_path):
    bm_file = tmp_path / "Bookmarks"
    content = {
        "roots": {
            "bookmark_bar": {
                "name": "Bookmarks Bar",
                "type": "folder",
                "children": [
                    {
                        "name": "Python Regex Tool",
                        "type": "url",
                        "url": "https://regex101.com"
                    },
                    {
                        "name": "DSA Binary Search Notes",
                        "type": "url",
                        "url": "https://neetcode.io/practice"
                    }
                ]
            },
            "other": {
                "name": "Other",
                "type": "folder",
                "children": []
            }
        }
    }
    with open(bm_file, "w", encoding="utf-8") as f:
        json.dump(content, f)
    return bm_file


def test_platform_locator_returns_list():
    paths = find_platform_bookmark_paths()
    assert isinstance(paths, list)


def test_one_shot_ingestion(temp_vidura_corpus, sample_bookmarks_json):
    watcher = BookmarksWatcher(
        corpus=temp_vidura_corpus,
        bookmark_paths=[sample_bookmarks_json],
        debounce_seconds=0.1
    )

    results = watcher.ingest_all_now()
    assert str(sample_bookmarks_json) in results
    assert results[str(sample_bookmarks_json)] == 2

    # Verify search in Vidura FTS
    hits = temp_vidura_corpus.search("Regex")
    assert len(hits) >= 1
    assert "regex101.com" in hits[0]["url"]


def test_ci_environment_law(temp_vidura_corpus, sample_bookmarks_json, monkeypatch):
    """Under DHRITI_CI_ENVIRONMENT=true, watcher runs deterministically without OS thread."""
    monkeypatch.setenv("DHRITI_CI_ENVIRONMENT", "true")

    watcher = BookmarksWatcher(
        corpus=temp_vidura_corpus,
        bookmark_paths=[sample_bookmarks_json],
    )
    assert watcher.is_ci is True

    # start() should execute one-shot ingestion and return immediately
    watcher.start(blocking=False)
    assert watcher._observer is None

    hits = temp_vidura_corpus.search("neetcode")
    assert len(hits) >= 1


def test_debounce_change_handler(sample_bookmarks_json):
    triggered = []

    def on_change(p):
        triggered.append(p)

    handler = BookmarkChangeHandler(
        target_paths=[sample_bookmarks_json],
        on_change_callback=on_change,
        debounce_seconds=0.1
    )

    # Simulate 3 rapid bursts of events
    handler._handle_path(str(sample_bookmarks_json))
    handler._handle_path(str(sample_bookmarks_json))
    handler._handle_path(str(sample_bookmarks_json))

    # Before debounce expires, callback should not have fired yet
    assert len(triggered) == 0

    # Wait for debounce to elapse
    time.sleep(0.25)
    assert len(triggered) == 1
    assert triggered[0] == sample_bookmarks_json.resolve()
