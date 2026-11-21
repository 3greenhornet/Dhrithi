"""Tests for the Vidura 4-Facet Taxonomy, Surfacing, Instrument Routing, and Artifact Test."""

import datetime
from pathlib import Path
import pytest

from dhriti.constants import SCHEMA_VERSION
from dhriti.db import Database
from dhriti.life_mirror import LifeMirrorService
from dhriti.stage_ratio import compute_artifact_stage_ratio
from dhriti.timeutil import SimulatedClock, to_iso
from dhriti.vidura_corpus import ViduraCorpus
from dhriti.vidura_facets import FacetEngine
from dhriti.vidura_surface import ViduraSurfaceService


@pytest.fixture
def temp_vidura(tmp_path):
    db_path = tmp_path / "test_vidura.sqlite3"
    corpus = ViduraCorpus(db_path)
    return corpus


@pytest.fixture
def temp_dhriti_db(tmp_path):
    db_path = tmp_path / "test_dhriti.sqlite3"
    db = Database(db_path)
    return db


def test_facet_classification_and_breakdown(temp_vidura):
    # Add items of various kinds and topics
    temp_vidura.add_item(
        url="https://youtube.com/watch?v=123",
        title="Building a Python Compiler from Scratch Tutorial",
        duration_s=2400,
        kind="video"
    )
    temp_vidura.add_item(
        url="https://mentalmathtrainer.com",
        title="Mental Math Practice Speed Trainer Tool",
        duration_s=0,
        kind="tool"
    )
    temp_vidura.add_item(
        url="https://youtube.com/watch?v=456",
        title="Hilarious Comedy Standup Bloopers",
        duration_s=180,
        kind="video"
    )

    engine = FacetEngine(temp_vidura)
    res = engine.classify_all_unclassified()
    assert res["classified_count"] == 3

    breakdown = engine.get_facet_breakdown()
    assert breakdown["domain"]["cs"] >= 1
    assert breakdown["form"]["tool"] >= 1
    assert breakdown["intent"]["instrument"] >= 1
    assert breakdown["intent"]["audience"] >= 1
    assert breakdown["effort"]["deep"] >= 1
    assert breakdown["effort"]["5min"] >= 2

    instruments = engine.get_instruments()
    assert len(instruments) == 1
    assert "Mental Math" in instruments[0]["title"]


def test_instrument_routing_to_life_mirror(temp_vidura, temp_dhriti_db):
    temp_vidura.add_item(
        url="https://speechpractice.org",
        title="Impromptu Speech Practice Tool",
        duration_s=0,
        kind="tool"
    )
    clock = SimulatedClock(datetime.datetime(2026, 11, 22, 10, 0, 0, tzinfo=datetime.timezone.utc))
    life_svc = LifeMirrorService(temp_dhriti_db, {"life_mirror": {"enabled": True}}, clock=clock)

    added = life_svc.sync_instruments_from_vidura(temp_vidura)
    assert len(added) == 1
    assert "Speech Practice" in added[0]["label"]

    # Cadence practice check: should appear in life_alternative
    alts = life_svc.list()
    assert any("Speech Practice" in a["label"] for a in alts)


def test_vidura_daily_evening_surfacing_and_recall(temp_vidura):
    temp_vidura.add_item(
        url="https://youtube.com/watch?v=abc",
        title="Deep Diving Into Memory Architectures",
        duration_s=1200,
        kind="video"
    )
    engine = FacetEngine(temp_vidura)
    engine.classify_all_unclassified()

    clock = SimulatedClock(datetime.datetime(2026, 11, 22, 21, 30, 0, tzinfo=datetime.timezone.utc))
    surf = ViduraSurfaceService(temp_vidura, clock=clock)

    item = surf.suggest_daily_item()
    assert item is not None
    assert item["title"] == "Deep Diving Into Memory Architectures"

    card = surf.prepare_recall_card(item)
    assert card["revealed"] is False
    assert "Before revealing the link" in card["prompt"]

    # Submit recall response
    revealed = surf.submit_recall_response(item["id"], "Studying memory caching")
    assert revealed["revealed"] is True
    assert revealed["recalled"] is True
    assert revealed["url"] == "https://youtube.com/watch?v=abc"


def test_behavioral_artifact_stage_ratio(temp_dhriti_db):
    t0 = datetime.datetime(2026, 11, 22, 14, 0, 0, tzinfo=datetime.timezone.utc)
    t_ev = t0 + datetime.timedelta(minutes=15)
    t_late = t0 + datetime.timedelta(minutes=45)

    # Log an open event followed by evidence within 30 min (Stage)
    temp_dhriti_db.insert("event", {
        "event_id": "ev-open-1",
        "event_type": "content_item_opened",
        "occurred_at_utc": to_iso(t0),
        "source_adapter": "test",
        "observed_payload": '{"title": "Algorithms Book"}',
        "inference_payload": "{}",
        "action_taken": "opened",
        "telemetry_quality": "OK",
        "row_hash": "h1",
        "prev_hash": "p1"
    })
    temp_dhriti_db.insert("event", {
        "event_id": "ev-proof-1",
        "event_type": "evidence_submitted",
        "occurred_at_utc": to_iso(t_ev),
        "source_adapter": "test",
        "observed_payload": '{"proof": "code_commit"}',
        "inference_payload": "{}",
        "action_taken": "submitted",
        "telemetry_quality": "OK",
        "row_hash": "h2",
        "prev_hash": "p2"
    })

    # Log an open event with no evidence (Audience)
    t1 = datetime.datetime(2026, 11, 22, 16, 0, 0, tzinfo=datetime.timezone.utc)
    temp_dhriti_db.insert("event", {
        "event_id": "ev-open-2",
        "event_type": "content_item_opened",
        "occurred_at_utc": to_iso(t1),
        "source_adapter": "test",
        "observed_payload": '{"title": "Random Video"}',
        "inference_payload": "{}",
        "action_taken": "opened",
        "telemetry_quality": "OK",
        "row_hash": "h3",
        "prev_hash": "p3"
    })

    res = compute_artifact_stage_ratio(temp_dhriti_db, window_minutes=30)
    assert res["total_content_opened"] == 2
    assert res["stage_with_evidence"] == 1
    assert res["audience_unaccompanied"] == 1
    assert res["artifact_stage_ratio"] == 0.5
