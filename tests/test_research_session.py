from __future__ import annotations

import csv
import json

from research_export import export_sessions_csv
from research_session import ResearchSessionManager


def load_events(session_dir):
    return [
        json.loads(line)
        for line in (session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_research_session_records_minimum_events_and_summary(tmp_path):
    manager = ResearchSessionManager(tmp_path / "sessions")
    session = manager.start_session(
        project_id="demo",
        project_name="Proyecto",
        video_id="video-a",
        video_name="Vídeo A",
        video_position_ms=0,
        user_id="1",
        user_name="PX-01",
    )
    pause_id = "pause-1"

    manager.present_pause(
        pause_event_id=pause_id,
        video_id="video-a",
        video_name="Vídeo A",
        scheduled_time_ms=1200,
        activated_position_ms=1210,
        hotspots_present=[{"hotspot_id": "hotspot-1", "shape": "rectangle", "typology": "verb"}],
        supports_present=[{"support_id": "support-1", "type": "texto", "visible": True}],
    )
    manager.record_hotspot_activation("hotspot-1", audio_played=False, tts_played=False, typology="verb")
    manager.record_support_activation("support-1", audio_played=True, tts_played=False, typology="noun")
    manager.record_continue(video_id="video-a", video_name="Vídeo A", video_position_ms=1200)
    manager.record_event("video_seeked", video_id="video-a", video_name="Vídeo A", video_position_ms=500, seek_action="slider_drag", from_ms=2000, to_ms=500, direction="backward")
    manager.record_pause_rearmed(
        pause_event_id=pause_id,
        video_id="video-a",
        video_name="Vídeo A",
        scheduled_time_ms=1200,
        from_ms=2000,
        to_ms=500,
    )
    manager.present_pause(
        pause_event_id=pause_id,
        video_id="video-a",
        video_name="Vídeo A",
        scheduled_time_ms=1200,
        activated_position_ms=1200,
        hotspots_present=[],
        supports_present=[],
    )
    manager.record_event("professional_turn_marked", hotspot_id="hotspot-1")
    manager.record_event("response_marked_adequate", hotspot_id="hotspot-1")
    manager.record_event("review_marked", support_id="support-1")

    summary = manager.finish_session()
    session_dir = tmp_path / "sessions" / session.session_id
    events = load_events(session_dir)

    assert (session_dir / "session.json").exists()
    assert (session_dir / "summary.json").exists()
    assert json.loads((session_dir / "session.json").read_text(encoding="utf-8"))["schema_version"] == 2
    assert [event["event_type"] for event in events][:2] == ["session_started", "pause_event_presented"]
    assert [event["event_index"] for event in events] == list(range(1, len(events) + 1))
    elapsed_values = [event["elapsed_session_ms"] for event in events]
    assert all(isinstance(value, int) for value in elapsed_values)
    assert elapsed_values == sorted(elapsed_values)
    common_fields = {
        "session_id",
        "event_index",
        "timestamp",
        "elapsed_session_ms",
        "event_type",
        "participant_id",
        "participant_name",
        "is_anonymous",
        "video_id",
        "video_name",
        "video_position_ms",
        "pause_id",
    }
    assert all(common_fields <= set(event) for event in events)
    assert all(event["schema_version"] == 2 for event in events)
    assert events[0]["participant_id"] == "1"
    assert events[0]["participant_name"] == "PX-01"
    assert events[0]["is_anonymous"] is False
    assert events[0]["video_name"] == "Vídeo A"
    assert any(event["event_type"] == "pause_rearmed" for event in events)
    assert summary["pauses_presented"] == 2
    assert summary["repeated_presentations"] == 1
    assert summary["hotspots_activated"] == 1
    assert summary["supports_activated"] == 1
    assert summary["continue_presses"] == 1
    assert summary["manual_seeks"] == 1
    assert summary["professional_turn_marked"] == 1
    assert summary["response_marked_adequate"] == 1
    assert summary["review_marked"] == 1
    assert summary["pauses_without_interaction"] == 1
    assert summary["schema_version"] == 2
    assert summary["user_id"] == "1"
    assert summary["user_name"] == "PX-01"


def test_research_session_ignores_events_without_active_session(tmp_path):
    manager = ResearchSessionManager(tmp_path / "sessions")

    assert manager.record_event("video_started") is None
    assert not (tmp_path / "sessions").exists()


def test_research_export_writes_events_and_summaries_csv(tmp_path):
    manager = ResearchSessionManager(tmp_path / "sessions")
    manager.start_session(project_id="demo", project_name="", video_id="video-a")
    manager.record_event("video_started", video_position_ms=0)
    manager.finish_session()

    events_csv, summaries_csv = export_sessions_csv(tmp_path / "sessions", tmp_path / "export")

    with events_csv.open(newline="", encoding="utf-8") as handle:
        event_rows = list(csv.DictReader(handle))
    with summaries_csv.open(newline="", encoding="utf-8") as handle:
        summary_rows = list(csv.DictReader(handle))

    assert any(row["event_type"] == "video_started" for row in event_rows)
    assert "event_index" in event_rows[0]
    assert "participant_id" in event_rows[0]
    assert summary_rows[0]["project_id"] == "demo"
