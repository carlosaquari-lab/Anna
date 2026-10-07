from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import hotspot_editor
from hotspot_model import Hotspot, PausePoint, SupportItem
from research_session import ResearchSessionManager


def app() -> QApplication:
    return QApplication.instance() or QApplication(["research-qt"])


def load_events(session_dir):
    return [
        json.loads(line)
        for line in (session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_editor_records_research_pause_interactions_and_repeat(tmp_path, monkeypatch):
    app()
    monkeypatch.setattr(hotspot_editor.EditorWindow, "request_video_thumbnail", lambda self, index: None)
    monkeypatch.setattr(hotspot_editor.EditorWindow, "prime_current_video_frame", lambda self: None)

    window = hotspot_editor.EditorWindow()
    window.research = ResearchSessionManager(tmp_path / "sessions")
    window.duration_ms = 5000
    window.research.start_session(
        project_id="demo",
        project_name=window.project_display_name(),
        video_id=window.current_video().video_id,
        video_name=window.current_video().name,
        video_position_ms=0,
    )
    window.preview_mode = True
    window.update_research_controls()

    hotspot = Hotspot(
        "hotspot-1",
        shape="ellipse",
        geometry={"x": 0.25, "y": 0.2, "width": 0.3, "height": 0.25},
        message_text="Hola",
        communication_category="social",
    )
    support = SupportItem(
        "support-1",
        text="Apoyo",
        visible=True,
        tts_enabled=False,
        position=0,
        communication_category="noun",
    )
    pause = PausePoint(pause_id="pause-1", time_ms=1000, hotspots=[hotspot], supports=[support])
    window.pauses = [pause]
    window.pause_states = {pause.time_ms: "armed"}

    window.pause_at_temporal_event(pause)
    assert window.active_event_id == "pause-1"
    assert window.current_pause() == pause
    assert len(window.items) == 1
    item = next(iter(window.items.values()))
    assert item.hotspot.shape == "ellipse"
    assert item.isVisible()

    window.activate_hotspot("hotspot-1")
    window.activate_support(support)
    window.record_user_event("turn")
    window.record_user_event("adequate")
    window.continue_from_pause()

    window.research.record_event(
        "video_seeked",
        video_id=window.current_video().video_id,
        video_name=window.current_video().name,
        from_ms=1200,
        to_ms=500,
        direction="backward",
        seek_action="slider_drag",
        video_position_ms=500,
    )
    window._last_position_ms = 1200
    window.pause_states[pause.time_ms] = "consumed_for_current_pass"
    window.rearm_pauses_before_or_at(500)
    window.pause_at_temporal_event(pause)
    window.record_user_event("review")
    summary = window.research.finish_session()

    events = load_events(tmp_path / "sessions" / window.research.events[0]["session_id"])
    event_types = [event["event_type"] for event in events]
    assert event_types.count("pause_event_presented") == 2
    assert [event["event_index"] for event in events] == list(range(1, len(events) + 1))
    assert all(event["schema_version"] == 2 for event in events)
    assert "hotspot_activated" in event_types
    assert "support_activated" in event_types
    assert "continue_pressed" in event_types
    assert "pause_rearmed" in event_types
    assert "professional_turn_marked" in event_types
    assert "response_marked_adequate" in event_types
    assert "review_marked" in event_types
    pause_event = next(event for event in events if event["event_type"] == "pause_event_presented")
    assert pause_event["pause_id"] == "pause-1"
    assert pause_event["hotspots_present"][0]["typology"] == "social"
    assert pause_event["hotspots_present"][0]["shape"] == "ellipse"
    assert pause_event["hotspots_present"][0]["tts_enabled"] is True
    assert pause_event["supports_present"][0]["visible"] is True
    hotspot_event = next(event for event in events if event["event_type"] == "hotspot_activated")
    support_event = next(event for event in events if event["event_type"] == "support_activated")
    assert hotspot_event["typology"] == "social"
    assert hotspot_event["shape"] == "ellipse"
    assert hotspot_event["activation_order"] == 1
    assert support_event["visible"] is True
    assert support_event["activation_order"] == 1
    mark_event = next(event for event in events if event["event_type"] == "professional_turn_marked")
    assert mark_event["target_type"] == "support"
    assert mark_event["target_id"] == "support-1"
    assert summary["repeated_presentations"] == 1
    assert summary["pauses_without_interaction"] == 1
