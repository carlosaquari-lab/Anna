from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow, SupportConfigDialog  # noqa: E402
from hotspot_model import HOTSPOT_MESSAGE_MAX_CHARS, Hotspot, PausePoint, SupportItem  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-message16"])


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def test_layout_uses_compact_adaptive_bands_without_large_fixed_heights() -> None:
    app = _app()
    window = EditorWindow()
    try:
        window.refresh_video_nav()
        window.refresh_support_panel()

        assert window.timeline.minimumHeight() <= 42
        assert window.video_nav_layout.contentsMargins().top() <= 5
        assert window.video_nav.findChildren(QToolButton)[0].height() <= 70
        support_card = window.support_buttons_layout.itemAt(0).widget()
        assert support_card is not None
        support_button = support_card.findChildren(QToolButton)[0]
        assert support_button.height() <= 116
        assert window.scroll_area.widgetResizable() is True
    finally:
        window.close()
        _pump(app)


def test_inicio_resets_player_timeline_pause_state_text_hotspot_and_audio() -> None:
    app = _app()
    window = EditorWindow()
    try:
        _pump(app)
        hotspot = Hotspot("h1", message_text="Hola")
        window.pauses = [PausePoint("p1", 4000, [hotspot]), PausePoint("p2", 9000, [])]
        window.pause_states = {4000: "active", 9000: "consumed_for_current_pass"}
        window.selected_pause_ms = 4000
        window.active_hotspot_id = "h1"
        window.current_hotspot_id = "h1"
        window.reload_hotspots_for_pause()
        window.output_label.setText("Mensaje")
        window.output_proxy.show()
        window.timeline.setValue(4000)
        window.continue_btn.setEnabled(True)

        window.go_to_start()
        _pump(app)

        assert window.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
        assert window.timeline.value() == 0
        assert window.selected_pause_ms is None
        assert window.active_hotspot_id is None
        assert window.current_hotspot_id is None
        assert window.output_label.text() == ""
        assert window.output_proxy.isVisible() is False
        assert window.pause_states == {4000: "armed", 9000: "armed"}
        assert window.continue_btn.isEnabled() is False
    finally:
        window.close()
        _pump(app)


def test_support_dialog_preserves_each_type_and_label_without_internal_asset_names() -> None:
    app = _app()
    dialogs: list[SupportConfigDialog] = []
    try:
        text_dialog = SupportConfigDialog(SupportItem("support_1", "Texto clave", "leer", visible=True), "Apoyo 1")
        dialogs.append(text_dialog)
        assert text_dialog.result_support().text == "leer"

        image_dialog = SupportConfigDialog(SupportItem("support_2", "Foto", "", image_asset="assets/supports/images/support_abc123.png", visible=True), "Apoyo 2")
        dialogs.append(image_dialog)
        image_result = image_dialog.result_support()
        assert image_result.label == "Apoyo 2"
        assert image_result.image_asset == "assets/supports/images/support_abc123.png"

        audio_dialog = SupportConfigDialog(SupportItem("support_3", "Voz", "", audio_asset="assets/supports/audio/support_def456.wav", visible=True), "Apoyo 3")
        dialogs.append(audio_dialog)
        audio_result = audio_dialog.result_support()
        assert audio_result.label == "Apoyo 3"
        assert audio_result.audio_asset == "assets/supports/audio/support_def456.wav"

        window = EditorWindow()
        try:
            card = window.make_support_card(image_result, 1)
            button = card.findChildren(QToolButton)[0]
            assert button.text() == ""
            assert "support_" not in button.text()
        finally:
            window.close()
            _pump(app)
    finally:
        for dialog in dialogs:
            dialog.close()
        _pump(app)


def test_cancel_support_dialog_does_not_mutate_existing_support() -> None:
    app = _app()
    support = SupportItem("support_1", "Original", "hola", visible=True)
    dialog = SupportConfigDialog(support, "Apoyo 1")
    try:
        dialog.text_edit.setPlainText("adios")
        dialog.reject()

        assert support.label == "Original"
        assert support.text == "hola"
        assert support.visible is True
    finally:
        dialog.close()
        _pump(app)


def test_empty_support_cannot_appear_in_user_mode_even_if_marked_visible() -> None:
    app = _app()
    window = EditorWindow()
    try:
        pause = PausePoint(
            "pause-empty-supports",
            1000,
            [],
            [
                SupportItem("support_1", "Apoyo 1", "", visible=True, position=0),
                SupportItem("support_2", "Apoyo 2", "", visible=True, position=1),
                SupportItem("support_3", "Apoyo 3", "", visible=True, position=2),
            ],
        )
        window.pauses = [pause]
        window.current_video().pauses = window.pauses
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.pause_at_temporal_event(pause)

        assert window.support_panel.isHidden() is False
        assert window.support_buttons_layout.count() == 0
    finally:
        window.close()
        _pump(app)

def test_real_hotspot_bubble_widget_uses_black_yellow_single_line_inside_video() -> None:
    app = _app()
    window = EditorWindow()
    try:
        hotspot = Hotspot(
            "h1",
            message_text="Mensaje heredado muy largo " * 8,
            geometry={"x": 0.86, "y": 0.86, "width": 0.12, "height": 0.1},
        )
        pause = PausePoint("p1", 4000, [hotspot])
        window.pauses = [pause]
        window.current_video().pauses = window.pauses
        window.select_event(pause)
        window.reload_hotspots_for_pause()
        window.activate_hotspot("h1")

        assert HOTSPOT_MESSAGE_MAX_CHARS == 40
        assert window.output_proxy.widget() is window.output_label
        assert "#111111" in window.output_label.styleSheet()
        assert "#FFFF00" in window.output_label.styleSheet()
        assert "\n" not in window.output_label.text()
        assert window.output_label.font().bold()
        assert 0 <= window.output_proxy.pos().x() <= 1536 - window.output_label.width()
        assert 0 <= window.output_proxy.pos().y() <= 864 - window.output_label.height()
    finally:
        window.close()
        _pump(app)
