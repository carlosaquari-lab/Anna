from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import EditorWindow, HotspotContentDialog, hotspot_shape_icon  # noqa: E402
from hotspot_model import HOTSPOT_PALETTE, Hotspot, PausePoint, pixel_to_normalized  # noqa: E402


def test_editor_window_constructs_with_five_tools_and_closes_cleanly():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        app.processEvents()
        assert set(window.tool_buttons) == {"select", "rectangle", "ellipse", "edit", "delete"}
        assert len(window.tool_buttons) == 5
        assert window.pauses == []
        assert window.output_label.text() == ""
        assert window.preview_btn.toolTip()
        for button in window.tool_buttons.values():
            assert button.accessibleName()
            assert button.toolTip()
        window.timeline.setRange(0, 100000)
        window.seek_from_click(50000)
        app.processEvents()
        assert window.selected_pause_ms is None
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            app.processEvents()
    finally:
        window.close()
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            app.processEvents()


def _pump(app, seconds=0.1):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def test_timeline_remains_navigable_after_hotspot_edit_delete_and_marker_cycles():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        window.timeline.setRange(0, 100000)
        window.pauses = [PausePoint("p1", 10000, [Hotspot("h1")]), PausePoint("p2", 50000, [Hotspot("h2")])]
        window.timeline.set_pauses(window.pauses, None)
        _pump(app)
        window.seek_from_click(10100)
        assert window.selected_pause_ms == 10000
        assert len(window.items) == 1
        window.select_hotspot("h1")
        window.begin_slider_seek()
        window.timeline.setValue(70000)
        window.seek_during_drag(70000)
        window.finish_slider_seek()
        assert window.selected_pause_ms is None
        assert window.items == {}
        window.goto_pause(50000)
        assert window.selected_pause_ms == 50000
        window.begin_slider_seek()
        window.timeline.setValue(1000)
        window.seek_during_drag(1000)
        window.finish_slider_seek()
        assert window.selected_pause_ms is None
        window.goto_pause(10000)
        window.delete_selected_hotspot = lambda: None  # avoid modal prompt in smoke path
        _pump(app)
    finally:
        window.close()
        _pump(app)


def test_user_mode_hides_authoring_controls_but_keeps_fixed_layout():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        assert window.tool_panel.minimumWidth() == 168
        assert window.tool_panel.maximumWidth() == 168
        assert window.support_panel.minimumWidth() == 224
        assert window.support_panel.maximumWidth() == 224

        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        assert window.preview_mode is True
        assert window.tool_panel.isHidden() is False
        assert all(not button.isVisible() for button in window.tool_buttons.values())
        assert all(not button.isEnabled() for button in window.tool_buttons.values())
        assert window.support_panel.isHidden() is False

        window.enter_edit_mode()
        assert window.preview_mode is False
        assert window.tool_panel.isHidden() is False
        assert all(not button.isHidden() for button in window.tool_buttons.values())
        assert all(button.isEnabled() for button in window.tool_buttons.values())
    finally:
        window.close()
        _pump(app)

def test_continue_clears_active_event_and_reaches_next_pause():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        window.duration_ms = 100000
        window.timeline.setRange(0, 100000)
        window.pauses = [
            PausePoint("p1", 10000, [Hotspot("h1", message_text="hola")]),
            PausePoint("p2", 11000, [Hotspot("h2")]),
        ]
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.playback_controller.start_playback(9000, user_mode=True)
        window.on_position_changed(10010)
        assert window.active_event_id == "p1"
        assert window._temporal_mode.name == "INTERACTION_PAUSED"

        window.output_label.setText("HOLA")
        window.continue_from_pause()
        assert window.active_event_id is None
        assert window.output_label.text() == ""
        assert window.items == {}
        window.on_position_changed(10200)
        window.on_position_changed(11010)
        assert window.active_event_id == "p2"
        assert window._temporal_mode.name == "INTERACTION_PAUSED"
    finally:
        window.close()
        _pump(app)

def test_continue_does_not_skip_second_pause_after_first_pause():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        window.duration_ms = 12000
        window.timeline.setRange(0, 12000)
        window.pauses = [
            PausePoint("a", 2000, [Hotspot("h1")]),
            PausePoint("b", 9000, [Hotspot("h2")]),
        ]
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.playback_controller.start_playback(1000, user_mode=True)
        window.on_position_changed(2010)
        assert window.active_event_id == "a"
        window.continue_from_pause()
        window.on_position_changed(2200)
        window.on_position_changed(9010)
        assert window.active_event_id == "b"

        window.continue_from_pause()
        window.on_position_changed(9200)
        window.seek_from_click(1000)
        window.playback_controller.start_playback(1000, user_mode=True)
        window.on_position_changed(2010)
        assert window.active_event_id == "a"
    finally:
        window.close()
        _pump(app)

def test_close_temporal_distances_merge_and_500_ms_events_remain_distinct():
    from hotspot_model import add_hotspot_to_time
    from playback_controller import PlaybackController

    for distance in (50, 100, 200, 250):
        pauses = []
        add_hotspot_to_time(pauses, 2000, Hotspot(f"a{distance}"))
        add_hotspot_to_time(pauses, 2000 + distance, Hotspot(f"b{distance}"))
        assert len(pauses) == 1
        assert len(pauses[0].hotspots) == 2

    for distance in (500, 1000):
        pauses = [
            PausePoint("a", 2000, [Hotspot("a")]),
            PausePoint("b", 2000 + distance, [Hotspot("b")]),
        ]
        controller = PlaybackController()
        controller.start_playback(1000, user_mode=True)
        first = controller.observe_position(2010, pauses, user_mode=True)
        assert first.crossed_event.pause_id == "a"
        controller.begin_interaction(2000)
        target = controller.begin_continue(2000, 10000)
        controller.observe_position(target, pauses, user_mode=True)
        second = controller.observe_position(2000 + distance + 10, pauses, user_mode=True)
        assert second.crossed_event.pause_id == "b"

def test_pause_rearms_when_navigating_back_or_marker_clicked():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        window.timeline.setRange(0, 100000)
        window.pauses = [PausePoint("p1", 10000, [Hotspot("h1")])]
        window.goto_pause(10000)
        assert window.selected_event_id == "p1"
        assert window.active_event_id is None
        assert window.pause_state(10000) == "armed"
        window.seek_from_click(9000)
        assert window.pause_state(10000) == "armed"
        window.goto_pause(10000)
        assert window.selected_event_id == "p1"
        assert window.active_event_id is None
    finally:
        window.close()
        _pump(app)


def test_continue_without_hotspot_activation_still_consumes_pause():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        window.duration_ms = 50000
        window.timeline.setRange(0, 50000)
        window.pauses = [PausePoint("p1", 10000, [Hotspot("h1")])]
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.pause_at_temporal_event(window.pauses[0])
        window.continue_from_pause()
        assert window.pause_state(10000) == "consumed_for_current_pass"
        assert window.output_label.text() == ""
    finally:
        window.close()
        _pump(app)


def test_delete_dialog_texts_follow_default_language_and_cancel_keeps_state():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    original_message_box = hotspot_editor.QMessageBox
    try:
        title, message, delete_text, cancel_text = window.delete_prompt_text(False)
        assert title == "Delete hotspot"
        assert "delete this hotspot" in message
        assert delete_text == "Delete"
        assert cancel_text == "Cancel"
        _, last_message, _, _ = window.delete_prompt_text(True)
        assert "also" in last_message
        assert "pause" in last_message
        shown_dialogs: list[dict[str, object]] = []

        class FakeMessageBox:
            ButtonRole = original_message_box.ButtonRole

            def __init__(self, parent=None) -> None:
                self.parent = parent
                self.title = ""
                self.text = ""
                self.buttons: list[tuple[str, object, object]] = []
                self.cancel_button = None

            def setWindowTitle(self, title: str) -> None:
                self.title = title

            def setText(self, text: str) -> None:
                self.text = text

            def addButton(self, text: str, role) -> object:
                button = object()
                self.buttons.append((text, role, button))
                if text == "Cancelar":
                    self.cancel_button = button
                return button

            def setDefaultButton(self, _button) -> None:
                pass

            def exec(self) -> int:
                shown_dialogs.append(
                    {
                        "title": self.title,
                        "text": self.text,
                        "buttons": [text for text, _role, _button in self.buttons],
                    }
                )
                return 0

            def clickedButton(self) -> object:
                return self.cancel_button

        pause = PausePoint("p1", 10000, [Hotspot("h1")])
        window.pauses = [pause]
        window.select_event(pause)
        window.reload_hotspots_for_pause()
        window.select_hotspot("h1")
        hotspot_editor.QMessageBox = FakeMessageBox
        window.delete_selected_hotspot()
        assert shown_dialogs == [
            {
                "title": "Delete hotspot",
                "text": last_message,
                "buttons": ["Delete", "Cancel"],
            }
        ]
        assert window.pauses == [pause]
        assert pause.hotspots[0].hotspot_id == "h1"
    finally:
        hotspot_editor.QMessageBox = original_message_box
        window.close()
        _pump(app)

def test_dialog_uses_multiline_message_popover_color_and_cancel_preserves_previous():
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    original = Hotspot("h1", message_text="Línea 1\nLínea 2", color="#45A84A")
    dialog = HotspotContentDialog(original)
    try:
        assert dialog.message.toPlainText() == "Línea 1\nLínea 2"
        assert len(dialog.color_actions) == 6
        assert dialog.change_color_btn.text() == "Change color…"
        assert dialog.color_swatch.width() <= 26
        dialog.select_color("#2A7FD1")
        assert dialog.result_hotspot().color == "#2A7FD1"
        dialog.reject()
        assert original.color == "#45A84A"
    finally:
        dialog.close()
        _pump(app)


def test_rectangle_and_ellipse_icons_are_custom_qt_icons():
    QApplication.instance() or QApplication(["test-hotspot-editor"])
    assert not hotspot_shape_icon("rectangle").isNull()
    assert not hotspot_shape_icon("ellipse").isNull()


def test_create_overlap_rejected_and_invalid_move_restored(monkeypatch):
    app = QApplication.instance() or QApplication(["test-hotspot-editor"])
    window = EditorWindow()
    try:
        monkeypatch.setattr(window, "overlap_message", lambda: None)
        first = Hotspot("h1", geometry=pixel_to_normalized((100, 100, 200, 120)))
        second = Hotspot("h2", geometry=pixel_to_normalized((360, 100, 120, 120)))
        window.pauses = [PausePoint("p1", 10000, [first, second])]
        window.select_event(window.pauses[0])
        window.reload_hotspots_for_pause()
        before_count = len(window.pauses[0].hotspots)
        window.player.setPosition(10000)
        window.create_hotspot(QRectF(150, 120, 80, 80), "rectangle")
        assert len(window.pauses[0].hotspots) == before_count
        second.geometry = pixel_to_normalized((140, 120, 100, 80))
        window.current_hotspot_id = "h2"
        window.on_hotspot_geometry_changed("h2", pixel_to_normalized((360, 100, 120, 120)), second.geometry)
        assert second.geometry == pixel_to_normalized((360, 100, 120, 120))
    finally:
        window.close()
        _pump(app)
