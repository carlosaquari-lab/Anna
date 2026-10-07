from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtMultimedia import QMediaRecorder
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow, HotspotContentDialog  # noqa: E402
from hotspot_model import HOTSPOT_MESSAGE_MAX_CHARS, HOTSPOT_PALETTE, Hotspot, PausePoint, clamp_hotspot_message, default_project, message_counter_text, serialize_project, validate_project_payload, wrap_long_preview_words  # noqa: E402


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


class RecordingRecorder:
    def recorderState(self):
        return QMediaRecorder.RecorderState.RecordingState


def test_dialog_message_limit_counter_and_long_paste() -> None:
    app = QApplication.instance() or QApplication(["test-hotspot-dialog"])
    dialog = HotspotContentDialog(Hotspot("h1"))
    try:
        dialog.message.setPlainText("a" * 81)
        assert dialog.message.toPlainText() == "a" * HOTSPOT_MESSAGE_MAX_CHARS
        assert dialog.message_counter.text() == "40/40"
        dialog.message.setPlainText("hola")
        assert dialog.message_counter.text() == "4/40"
    finally:
        dialog.close()
        _pump(app)


def test_message_helpers_support_counter_and_preview_wrapping() -> None:
    assert clamp_hotspot_message("x" * 90) == "x" * 40
    assert message_counter_text("hola") == "4/40"
    one_line = wrap_long_preview_words("Quiero jugar")
    two_lines = wrap_long_preview_words("Quiero jugar\nahora")
    long_word = wrap_long_preview_words("supercalifragilistico" * 3, chunk_size=12)
    assert one_line == "Quiero jugar"
    assert "ahora" in two_lines
    assert "\u200b" in long_word


def test_dialog_has_compact_color_selector_with_six_menu_options() -> None:
    app = QApplication.instance() or QApplication(["test-hotspot-dialog"])
    dialog = HotspotContentDialog(Hotspot("h1"))
    try:
        assert list(HOTSPOT_PALETTE.values()) == ["#00A6C8", "#2A7FD1", "#45A84A", "#FF8C24", "#D94A9C", "#D94848"]
        assert dialog.color_swatch.width() <= 26
        assert dialog.change_color_btn.text() == "Change color…"
        assert len(dialog.color_actions) == 6
        assert {action.toolTip() for action in dialog.color_actions.values()} == {
            "Turquoise", "Blue", "Green", "Orange", "Pink", "Red"
        }
        dialog.select_color("#2A7FD1")
        assert dialog.result_hotspot().color == "#2A7FD1"
    finally:
        dialog.close()
        _pump(app)


def test_dialog_loads_and_returns_message_category_visibility_color_and_audio() -> None:
    app = QApplication.instance() or QApplication(["test-hotspot-dialog"])
    hotspot = Hotspot("h1", message_text="Quiero jugar\nahora", communication_category="verb_action", show_message_text=False, color="#45A84A", audio_asset="assets/audio/test.wav")
    dialog = HotspotContentDialog(hotspot)
    try:
        assert dialog.message.toPlainText() == "Quiero jugar\nahora"
        expected_len = len("Quiero jugar\nahora")
        assert dialog.message_counter.text() == f"{expected_len}/40"
        assert dialog.category.currentData() == "verb_action"
        assert dialog.show_message.isChecked() is False
        assert dialog.hotspot.color == "#45A84A"
        assert dialog.pending_audio_asset == "assets/audio/test.wav"
        dialog.message.setPlainText("Nuevo mensaje")
        dialog.category.setCurrentIndex(dialog.category.findData("social_expression"))
        dialog.show_message.setChecked(True)
        updated = dialog.result_hotspot()
        assert updated.message_text == "Nuevo mensaje"
        assert updated.communication_category == "social_expression"
        assert updated.show_message_text is True
        assert updated.audio_asset == "assets/audio/test.wav"
    finally:
        dialog.close()
        _pump(app)


def test_dialog_does_not_trim_existing_long_message_until_saved_or_edited() -> None:
    app = QApplication.instance() or QApplication(["test-hotspot-dialog"])
    long_text = "b" * 90
    dialog = HotspotContentDialog(Hotspot("h1", message_text=long_text))
    try:
        assert dialog.message.toPlainText() == long_text
        assert dialog.message_counter.text() == "40/40"
        assert dialog.result_hotspot().message_text == "b" * 40
    finally:
        dialog.close()
        _pump(app)


def test_category_visibility_and_color_round_trip_through_json() -> None:
    hotspot = Hotspot("h1", communication_category="noun_object", show_message_text=False, color="#D94A9C")
    payload = serialize_project(default_project(), [PausePoint("p1", 1000, [hotspot])])
    loaded = validate_project_payload(payload)[0].hotspots[0]
    assert loaded.communication_category == "noun_object"
    assert loaded.show_message_text is False
    assert loaded.color == "#D94A9C"


def test_audio_buttons_follow_audio_state() -> None:
    app = QApplication.instance() or QApplication(["test-hotspot-dialog"])
    dialog = HotspotContentDialog(Hotspot("h1"))
    try:
        dialog.pending_audio_asset = None
        dialog.recorder = None
        dialog.update_audio_status()
        assert dialog.audio_status.text() == "No audio"
        assert dialog.listen_btn.isEnabled() is False
        assert dialog.delete_audio_btn.isEnabled() is False
        assert dialog.stop_record_btn.isEnabled() is False

        dialog.pending_audio_asset = "assets/audio/test.wav"
        dialog.update_audio_status()
        assert dialog.audio_status.text() == "Audio ready"
        assert dialog.listen_btn.isEnabled() is True
        assert dialog.delete_audio_btn.isEnabled() is True

        dialog.recorder = RecordingRecorder()
        dialog.update_audio_status()
        assert dialog.audio_status.text() == "Recording…"
        assert dialog.stop_record_btn.isEnabled() is True
    finally:
        dialog.close()
        _pump(app)


def test_cancel_edit_does_not_modify_existing_hotspot() -> None:
    app = QApplication.instance() or QApplication(["test-hotspot-dialog"])
    hotspot = Hotspot("h1", message_text="Original", color="#00A6C8", communication_category="other", show_message_text=True)
    dialog = HotspotContentDialog(hotspot)
    try:
        dialog.message.setPlainText("Cambiado")
        dialog.select_color("#D94848")
        dialog.show_message.setChecked(False)
        dialog.reject()
        assert hotspot.message_text == "Original"
        assert hotspot.color == "#00A6C8"
        assert hotspot.communication_category == "other"
        assert hotspot.show_message_text is True
    finally:
        dialog.close()
        _pump(app)


def test_cancel_creation_removes_provisional_hotspot_and_empty_pause() -> None:
    app = QApplication.instance() or QApplication(["test-hotspot-dialog"])
    window = EditorWindow()
    try:
        hotspot = Hotspot("h1")
        pause = PausePoint("p1", 1000, [hotspot])
        window.pauses = [pause]
        window.selected_pause_ms = 1000
        removed_pause = window.cancel_provisional_hotspot(pause, hotspot)
        assert removed_pause is True
        assert window.pauses == []
        assert window.selected_pause_ms is None
    finally:
        window.close()
        _pump(app)
