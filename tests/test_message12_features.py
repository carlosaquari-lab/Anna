from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import Hotspot, PausePoint, SupportItem, VideoEntry, default_project, serialize_project, videos_from_project_payload  # noqa: E402


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def test_legacy_project_is_exposed_as_first_video() -> None:
    payload = default_project()
    payload["pauses"] = [PausePoint("p1", 4000, [Hotspot("h1")]).to_dict()]
    videos = videos_from_project_payload(payload)
    assert len(videos) == 1
    assert videos[0].video_id == "video-1"
    assert videos[0].pauses[0].time_ms == 4000


def test_multi_video_project_serializes_isolated_pause_events_and_supports() -> None:
    first = PausePoint(
        "p1",
        4000,
        [Hotspot("h1")],
        [SupportItem("support_1", "Texto", "Ayuda", visible=True)],
    )
    second = PausePoint(
        "p2",
        12000,
        [Hotspot("h2")],
        [SupportItem("support_1", "Texto", "Otra ayuda", visible=False)],
    )
    videos = [
        VideoEntry("v1", "Vídeo 1", "../../circular.mp4", [first]),
        VideoEntry("v2", "Vídeo 2", "../../circular.mp4", [second]),
    ]
    payload = serialize_project(default_project(), videos[0].pauses, 20000, videos, 1)

    assert payload["current_video_index"] == 1
    assert payload["videos"][0]["pause_events"][0]["event_id"] == "p1"
    assert payload["videos"][1]["pause_events"][0]["event_id"] == "p2"
    assert payload["videos"][0]["pause_events"][0]["supports"][0]["text"] == "Ayuda"
    assert payload["videos"][1]["pause_events"][0]["supports"][0]["text"] == "Otra ayuda"
    assert payload["pause_events"][0]["event_id"] == "p2"

    restored = videos_from_project_payload(payload)
    assert restored[0].pauses[0].supports[0].text == "Ayuda"
    assert restored[1].pauses[0].supports[0].text == "Otra ayuda"

def test_mode_controls_video_nav_and_user_events_are_available() -> None:
    app = QApplication.instance() or QApplication(["test-message12"])
    window = EditorWindow()
    try:
        menus = [action.text() for action in window.menuBar().actions()]
        assert menus[0] == "File"
        assert menus[1] == "Mode"
        assert menus[-2:] == ["Language", "Help"]
        assert len(menus) == 5
        assert "Proyecto" not in menus
        assert window.tool_buttons["rectangle"].text().startswith("Rect")
        assert window.tool_buttons["ellipse"].text() == "Ellipse"
        assert window.mode_quick_btn.toolTip() == "User mode"
        assert window.professional_annotation_buttons["turn"].isHidden() is False
        assert window.tool_panel.isHidden() is False
        assert window.add_video_btn is None or window.add_video_btn.isHidden() is False
        assert window.add_video_btn is None or window.add_video_btn.text() == "+"
        assert window.add_video_btn is None or window.add_video_btn.toolTip()
        assert window.last_primed_video_id == window.current_video().video_id
        assert window.navigation_visibility.isHidden() is False
        assert window.show_hotspots_toggle.isHidden() is False
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        assert window.preview_mode is True
        assert window.professional_annotation_buttons["turn"].isHidden() is False
        assert window.mode_quick_btn.isHidden() is False
        assert window.tool_panel.isHidden() is False
        assert window.add_video_btn is None or window.add_video_btn.isHidden() is True
        assert window.navigation_visibility.isHidden() is True
        assert window.show_hotspots_toggle.isHidden() is True
        window.record_user_event("turn")
        window.enter_edit_mode()
        assert window.preview_mode is False
        assert window.mode_quick_btn.isHidden() is False
        assert window.tool_panel.isHidden() is False
        assert window.add_video_btn is None or window.add_video_btn.isHidden() is False
    finally:
        window.close()
        _pump(app)

def test_first_frame_is_requested_when_selecting_another_video() -> None:
    app = QApplication.instance() or QApplication(["test-message14-frame"])
    window = EditorWindow()
    try:
        window.videos.append(VideoEntry("video-2", "Vídeo 2", str(Path(__file__).resolve().parents[3] / "circular.mp4"), []))
        window.select_video(1)
        assert window.current_video().video_id == "video-2"
        assert window.player.position() == 0
        assert window.timeline.value() == 0
        assert window.player.playbackState().name != "PlayingState"
    finally:
        window.close()
        _pump(app)


def test_support_panel_keeps_fixed_space_when_empty_or_disabled() -> None:
    app = QApplication.instance() or QApplication(["test-message12-supports"])
    window = EditorWindow()
    try:
        assert window.support_panel.isHidden() is False
        assert window.support_panel.minimumWidth() == 224
        assert window.support_panel.maximumWidth() == 224

        window.support_visibility.setChecked(False)
        _pump(app)
        assert window.support_panel.isHidden() is False
        assert window.support_buttons_layout.count() == 0

        window.support_visibility.setChecked(True)
        window.clear_selected_event()
        window.refresh_support_panel()
        assert window.support_panel.isHidden() is False
        assert window.support_panel.minimumWidth() == 224
    finally:
        window.close()
        _pump(app)

def test_support_panel_uses_edit_cards_and_user_visible_filter() -> None:
    app = QApplication.instance() or QApplication(["test-message14-supports"])
    window = EditorWindow()
    try:
        pause = PausePoint(
            "pause-supports",
            4000,
            [],
            [
                SupportItem("support_1", "Apoyo 1", "Texto listo", visible=True, position=0),
                SupportItem("support_2", "Apoyo 2", "", image_asset="assets/supports/images/image.png", visible=True, position=1),
                SupportItem("support_3", "Apoyo 3", "", visible=False, position=2),
            ],
        )
        window.pauses = [pause]
        window.current_video().pauses = window.pauses
        window.select_event(pause)
        window.refresh_support_panel(4000)
        assert window.support_buttons_layout.count() == 3
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.pause_at_temporal_event(pause)
        assert window.support_panel.isHidden() is False
        assert window.support_buttons_layout.count() == 2
        pause.supports[0].visible = False
        pause.supports[1].visible = False
        window.refresh_support_panel(4000)
        assert window.support_buttons_layout.count() == 0
    finally:
        window.close()
        _pump(app)

def test_hotspot_message_bubble_is_attached_to_active_hotspot_and_clamped_to_video() -> None:
    app = QApplication.instance() or QApplication(["test-message12"])
    window = EditorWindow()
    try:
        hotspot = Hotspot(
            "h1",
            message_text="Mensaje cerca del hotspot",
            geometry={"x": 0.88, "y": 0.88, "width": 0.1, "height": 0.08},
        )
        pause = PausePoint("p1", 4000, [hotspot])
        window.pauses = [pause]
        window.select_event(pause)
        window.reload_hotspots_for_pause()
        window.activate_hotspot("h1")

        assert window.active_hotspot_id == "h1"
        assert window.output_proxy.isVisible()
        assert "\n" not in window.output_label.text()
        assert window.output_label.font().pixelSize() == 26
        assert window.output_label.font().bold()
        assert window.output_label.height() >= 34
        assert "#111111" in window.output_label.styleSheet()
        assert "#FFFF00" in window.output_label.styleSheet()
        assert 0 <= window.output_proxy.pos().x() <= 1536 - window.output_label.width()
        assert 0 <= window.output_proxy.pos().y() <= 864 - window.output_label.height()
        window.clear_output_text()
        assert not window.output_proxy.isVisible()
    finally:
        window.close()
        _pump(app)
