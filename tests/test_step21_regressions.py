from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from hotspot_editor import EditorWindow
from hotspot_model import Hotspot, PausePoint, SupportItem
from research_session import ResearchSessionManager


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_real_clicks_keep_content_category_and_video_in_summary(tmp_path: Path) -> None:
    manager = ResearchSessionManager(tmp_path / "sessions")
    manager.elapsed_override_ms = 1000
    manager.start_session(project_id="p", project_name="Proyecto", video_id="video-1")
    manager.present_pause(
        pause_event_id="pause-1",
        video_id="video-1",
        video_name="VÃ­deo 1",
        scheduled_time_ms=1200,
        activated_position_ms=1200,
        hotspots_present=[{"hotspot_id": "h1", "message_text": "Beber", "category": "verb"}],
        supports_present=[{"support_id": "s1", "text": "Agua", "category": "noun", "type": "texto"}],
    )
    manager.elapsed_override_ms = 1300
    manager.record_hotspot_activation(
        "h1",
        pause_event_id="pause-1",
        video_id="video-1",
        video_name="VÃ­deo 1",
        hotspot_text="Beber",
        communication_category="verb",
    )
    manager.elapsed_override_ms = 1500
    manager.record_support_activation(
        "s1",
        pause_event_id="pause-1",
        video_id="video-1",
        video_name="VÃ­deo 1",
        support_text="Agua",
        communication_category="noun",
        support_type="texto",
    )

    summary = manager.build_summary()
    assert summary["hotspots_activated"] == 1
    assert summary["supports_activated"] == 1
    hotspot_activity = summary["hotspot_activity"][0]
    assert hotspot_activity["video_id"] == "video-1"
    assert hotspot_activity["hotspot_id"] == "h1"
    assert hotspot_activity["text"] == "Beber"
    assert hotspot_activity["category"] == "verb"
    assert hotspot_activity["count"] == 1
    support_activity = summary["support_activity"][0]
    assert support_activity["video_id"] == "video-1"
    assert support_activity["support_id"] == "s1"
    assert support_activity["text"] == "Agua"
    assert support_activity["category"] == "noun"
    assert support_activity["type"] == "texto"
    assert support_activity["count"] == 1
    assert summary["per_video"][0]["hotspots_activated"] == 1
    assert summary["per_video"][0]["supports_activated"] == 1

def test_editor_hotspot_and_support_clicks_feed_same_active_pause(tmp_path: Path) -> None:
    app()
    window = EditorWindow(auto_show=False)
    window.research = ResearchSessionManager(tmp_path / "sessions")
    window.research.elapsed_override_ms = 1000
    window.research.start_session(project_id="p", project_name="Proyecto", video_id="video-1")

    hotspot = Hotspot(
        hotspot_id="h1",
        message_text="Quiero",
        communication_category="verb",
        show_message_text=False,
    )
    support = SupportItem(
        support_id="s1",
        text="Ayuda",
        visible=True,
        communication_category="noun",
        tts_enabled=False,
    )
    pause = PausePoint(pause_id="pause-1", time_ms=1000, hotspots=[hotspot], supports=[support])
    window.pauses = [pause]
    window.current_video().pauses = window.pauses
    window.preview_mode = True
    window.active_event_id = pause.pause_id
    window.research.present_pause(
        pause_event_id=pause.pause_id,
        video_id="video-1",
        video_name="Vídeo 1",
        scheduled_time_ms=1000,
        activated_position_ms=1000,
        hotspots_present=window.research_hotspots_for_pause(pause),
        supports_present=window.research_supports_for_pause(pause),
    )

    window.activate_hotspot("h1")
    window.activate_support(support)
    summary = window.research.build_summary()
    assert summary["hotspots_activated"] == 1
    assert summary["supports_activated"] == 1
    assert summary["hotspot_activity"][0]["text"] == "Quiero"
    assert summary["hotspot_activity"][0]["category"] == "verb"
    assert summary["support_activity"][0]["text"] == "Ayuda"
    assert summary["support_activity"][0]["category"] == "noun"
    window.close()


def test_user_mode_disables_restricted_actions_and_buttons_do_not_change_text(tmp_path: Path) -> None:
    app()
    window = EditorWindow(auto_show=False)
    window.research = ResearchSessionManager(tmp_path / "sessions")
    window.research.start_session(project_id="p", project_name="Proyecto", video_id="video-1")
    window.preview_mode = True
    window.update_mode_controls()

    for menu in (window.file_menu, window.mode_menu, window.research_menu, window.language_menu, window.help_menu):
        assert menu.menuAction().isVisible()
        assert menu.menuAction().isEnabled()

    assert all(not action.isEnabled() for action in window.project_edit_actions)
    assert window.exit_action.isEnabled()
    assert all(not action.isEnabled() for action in window.research_actions)
    assert window.mode_edit_action.isEnabled()
    assert not window.mode_user_action.isEnabled()

    before = {key: button.text() for key, button in window.professional_annotation_buttons.items()}
    window.handle_professional_annotation("turn")
    after = {key: button.text() for key, button in window.professional_annotation_buttons.items()}
    assert after == before
    window.close()

def test_edit_context_is_cleared_when_playhead_leaves_pause() -> None:
    app()
    window = EditorWindow(auto_show=False)
    first = PausePoint(
        pause_id="pause-1",
        time_ms=0,
        hotspots=[Hotspot(hotspot_id="h1")],
        supports=[SupportItem(support_id="s1", text="Primero", visible=True)],
    )
    second = PausePoint(
        pause_id="pause-2",
        time_ms=2000,
        hotspots=[Hotspot(hotspot_id="h2")],
        supports=[SupportItem(support_id="s2", text="Segundo", visible=True)],
    )
    window.pauses = [first, second]
    window.current_video().pauses = window.pauses
    window.select_event(first)
    window.reload_hotspots_for_pause()
    assert set(window.items) == {"h1"}

    window.on_position_changed(1000)
    assert window.selected_event_id is None
    assert window.items == {}
    window.close()

def test_summary_text_contains_total_per_video_and_activated_details() -> None:
    summary = {
        "user_name": "Carlos",
        "session_type": "participant",
        "status": "active",
        "duration_ms": 2000,
        "videos_used": ["video-1"],
        "pauses_presented": 1,
        "hotspots_available": 1,
        "hotspots_activated": 1,
        "supports_available": 1,
        "supports_activated": 1,
        "per_video": [{
            "video_id": "video-1", "video_name": "VÃ­deo 1", "time_ms": 2000,
            "pauses_presented": 1, "hotspots_available": 1, "hotspots_activated": 1,
            "supports_available": 1, "supports_activated": 1,
        }],
        "hotspot_activity": [{"video_name": "VÃ­deo 1", "text": "Beber", "category": "verbo", "count": 1}],
        "support_activity": [{"video_name": "VÃ­deo 1", "text": "Agua", "category": "sustantivo", "type": "texto", "count": 1}],
    }
    text = EditorWindow._format_research_summary(summary)
    assert "SESSION SUMMARY" in text
    assert "BREAKDOWN BY VIDEO" in text
    assert "Time used: 2 s" in text
    assert "Beber" in text
    assert "Agua" in text
    assert "Activations: 1 activation" in text
