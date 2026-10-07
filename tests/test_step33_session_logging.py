from __future__ import annotations

import csv
import json

from research_export import export_sessions_csv
from research_session import ResearchSessionManager


def _load_events(session_dir):
    return [
        json.loads(line)
        for line in (session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_schema_v2_common_core_anonymous_and_interaction_details(tmp_path):
    manager = ResearchSessionManager(tmp_path / "sessions")
    session = manager.start_session(
        project_id="demo",
        project_name="Proyecto lógico",
        video_id="video-1",
        video_name="Vídeo 1",
        video_position_ms=0,
        is_anonymous=True,
        session_type="test",
    )
    manager.record_event("video_started", video_id="video-1", video_name="Vídeo 1", video_position_ms=0)
    manager.record_event("video_resumed", video_id="video-1", video_name="Vídeo 1", video_position_ms=300)
    manager.record_event("video_paused", video_id="video-1", video_name="Vídeo 1", video_position_ms=500)
    manager.record_event("video_stopped", video_id="video-1", video_name="Vídeo 1", video_position_ms=500)
    manager.record_event("video_seeked", video_id="video-1", video_name="Vídeo 1", video_position_ms=100, seek_action="timeline_click", from_ms=500, to_ms=100)
    manager.present_pause(
        pause_event_id="pause-1",
        video_id="video-1",
        video_name="Vídeo 1",
        scheduled_time_ms=1000,
        activated_position_ms=1000,
        hotspots_present=[
            {
                "hotspot_id": "hotspot-1",
                "text": "Hola",
                "typology": "social",
                "shape": "ellipse",
                "audio_available": True,
                "tts_enabled": True,
            }
        ],
        supports_present=[
            {
                "support_id": "support-1",
                "text": "Ayuda",
                "visible": True,
                "image_available": True,
                "audio_available": False,
                "tts_enabled": True,
            }
        ],
    )
    manager.record_hotspot_activation(
        "hotspot-1",
        audio_played=True,
        tts_played=False,
        hotspot_text="Hola",
        typology="social",
        shape="ellipse",
        audio_available=True,
        tts_enabled=True,
    )
    manager.record_support_activation(
        "support-1",
        audio_played=False,
        tts_played=True,
        support_text="Ayuda",
        visible=True,
        image_available=True,
        audio_available=False,
        tts_enabled=True,
    )
    manager.record_continue(video_id="video-1", video_name="Vídeo 1", video_position_ms=1000)
    summary = manager.finish_session(
        status="completed",
        video_id="video-1",
        video_name="Vídeo 1",
        video_position_ms=1000,
        finish_reason="research_disabled",
    )

    events = _load_events(tmp_path / "sessions" / session.session_id)
    assert [event["event_index"] for event in events] == list(range(1, len(events) + 1))
    assert [event["elapsed_session_ms"] for event in events] == sorted(event["elapsed_session_ms"] for event in events)
    assert all(event["schema_version"] == 2 for event in events)
    assert all(event["is_anonymous"] is True for event in events)
    assert all(event["participant_id"] is None for event in events)
    assert events[0]["event_type"] == "session_started"
    assert events[-1]["event_type"] == "session_finished"
    assert events[-1]["duration_ms"] == summary["duration_ms"]
    assert events[-1]["finish_reason"] == "research_disabled"

    pause_event = next(event for event in events if event["event_type"] == "pause_event_presented")
    assert pause_event["pause_id"] == "pause-1"
    assert pause_event["presented_position_ms"] == 1000
    assert pause_event["is_repeated_presentation"] is False
    assert pause_event["hotspots_present"][0]["typology"] == "social"
    assert pause_event["hotspots_present"][0]["tts_enabled"] is True
    assert pause_event["supports_present"][0]["visible"] is True
    assert pause_event["supports_present"][0]["image_available"] is True

    hotspot_event = next(event for event in events if event["event_type"] == "hotspot_activated")
    support_event = next(event for event in events if event["event_type"] == "support_activated")
    assert hotspot_event["activation_order"] == 1
    assert support_event["activation_order"] == 1
    assert isinstance(hotspot_event["pause_elapsed_ms"], int)
    assert hotspot_event["audio_available"] is True
    assert hotspot_event["audio_played"] is True
    assert hotspot_event["tts_played"] is False
    assert support_event["image_available"] is True
    assert support_event["tts_played"] is True

    assert "Condición" not in json.dumps(events, ensure_ascii=False)
    assert "fase" not in json.dumps(events, ensure_ascii=False).casefold()
    assert "C:\\" not in json.dumps(events, ensure_ascii=False)


def test_export_accepts_legacy_and_schema_v2_events(tmp_path):
    sessions_root = tmp_path / "sessions"
    legacy_dir = sessions_root / "legacy"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "events.jsonl").write_text(
        json.dumps({"timestamp": "2026-01-01T00:00:00+00:00", "session_id": "legacy", "event_type": "video_started", "elapsed_session_ms": 0})
        + "\n",
        encoding="utf-8",
    )
    (legacy_dir / "summary.json").write_text(json.dumps({"session_id": "legacy", "project_id": "demo"}), encoding="utf-8")

    manager = ResearchSessionManager(sessions_root)
    manager.start_session(project_id="demo", project_name="Proyecto", video_id="video-2", video_name="Vídeo 2")
    manager.record_event("video_started", video_id="video-2", video_name="Vídeo 2", video_position_ms=0)
    manager.finish_session(video_id="video-2", video_name="Vídeo 2", video_position_ms=0)

    events_csv, summaries_csv = export_sessions_csv(sessions_root, tmp_path / "export")

    with events_csv.open(newline="", encoding="utf-8") as handle:
        event_rows = list(csv.DictReader(handle))
    with summaries_csv.open(newline="", encoding="utf-8") as handle:
        summary_rows = list(csv.DictReader(handle))

    assert any(row["session_id"] == "legacy" and row["event_index"] == "" for row in event_rows)
    assert any(row["schema_version"] == "2" and row["event_index"] == "1" for row in event_rows)
    assert any(row["session_id"] == "legacy" for row in summary_rows)
