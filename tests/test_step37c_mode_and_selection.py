from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import Hotspot, PausePoint  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step37c-mode-and-selection"])


def _window_with_pauses(monkeypatch) -> EditorWindow:
    window = EditorWindow()
    position = {"value": 0}
    monkeypatch.setattr(window.player, "pause", lambda: None)
    monkeypatch.setattr(window.player, "play", lambda: None)
    monkeypatch.setattr(window.player, "position", lambda: position["value"])

    def set_position(value: int) -> None:
        position["value"] = int(value)

    monkeypatch.setattr(window.player, "setPosition", set_position)
    window.duration_ms = 20000
    window.timeline.setRange(0, 20000)
    window.pauses = [
        PausePoint("pause-4000", 4000, [Hotspot("hotspot-4000")]),
        PausePoint("pause-12000", 12000, [Hotspot("hotspot-12000")]),
    ]
    window.timeline.set_pauses(window.pauses, None)
    return window


def test_goto_pause_in_edit_mode_selects_requested_event_without_activating_user_interaction(monkeypatch) -> None:
    app = _app()
    window = _window_with_pauses(monkeypatch)
    try:
        window.goto_pause(12000)

        assert window.preview_mode is False
        assert window.selected_event_id == "pause-12000"
        assert window.selected_pause_ms == 12000
        assert window.active_event_id is None
        assert window.current_pause().pause_id == "pause-12000"
        assert set(window.items) == {"hotspot-12000"}
        assert window.timeline.value() == 12000

        window.goto_pause(4000)

        assert window.selected_event_id == "pause-4000"
        assert window.selected_pause_ms == 4000
        assert window.active_event_id is None
        assert set(window.items) == {"hotspot-4000"}
    finally:
        window.close()
        app.processEvents()


def test_goto_pause_in_user_mode_activates_event_without_leaving_edit_selection(monkeypatch) -> None:
    app = _app()
    window = _window_with_pauses(monkeypatch)
    try:
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()

        window.goto_pause(4000)

        assert window.preview_mode is True
        assert window.mode == "select"
        assert window.active_event_id == "pause-4000"
        assert window.selected_event_id is None
        assert window.selected_pause_ms is None
        assert set(window.items) == {"hotspot-4000"}
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("initial_mode", ["rectangle", "ellipse", "edit", "delete"])
def test_entering_user_mode_from_authoring_tools_forces_select_and_preserves_edit_selection(
    monkeypatch, initial_mode: str
) -> None:
    app = _app()
    window = _window_with_pauses(monkeypatch)
    try:
        window.goto_pause(12000)
        window.set_mode(initial_mode)

        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()

        assert window.preview_mode is True
        assert window.mode == "select"
        assert window.selected_event_id == "pause-12000"
        assert window.active_event_id is None
        assert all(not button.isEnabled() for button in window.tool_buttons.values())

        window.enter_edit_mode()

        assert window.preview_mode is False
        assert window.mode == "select"
        assert window.selected_event_id == "pause-12000"
        assert window.selected_pause_ms == 12000
        assert window.current_pause().pause_id == "pause-12000"
        assert set(window.items) == {"hotspot-12000"}
    finally:
        window.close()
        app.processEvents()
