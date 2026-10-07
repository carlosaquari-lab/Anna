from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow, HotspotContentDialog  # noqa: E402
from hotspot_model import HOTSPOT_MESSAGE_MAX_CHARS, Hotspot, PausePoint, SupportItem  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-message15"])


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def test_edit_support_panel_has_three_slots_without_general_title() -> None:
    app = _app()
    window = EditorWindow()
    try:
        window.refresh_support_panel()
        labels = [label.text() for label in window.support_panel.findChildren(QLabel)]

        assert "Apoyos" not in labels
        assert window.support_panel.isHidden() is False
        assert window.support_buttons_layout.count() == 3
    finally:
        window.close()
        _pump(app)


def test_user_support_panel_shows_only_configured_visible_supports() -> None:
    app = _app()
    window = EditorWindow()
    try:
        window.current_video().supports = [
            SupportItem("support_1", label="Texto", text="Clave", visible=True),
            SupportItem("support_2", label="Imagen", image_asset="assets/supports/images/card.png", visible=False, position=1),
            SupportItem("support_3", label="Audio", visible=True, position=2),
        ]
        pause = PausePoint("p1", 4000, [Hotspot("h1")], window.current_video().supports)
        window.pauses = [pause]
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.pause_at_temporal_event(pause)

        assert window.support_panel.isHidden() is False
        buttons = []
        for index in range(window.support_buttons_layout.count()):
            card = window.support_buttons_layout.itemAt(index).widget()
            if card is not None:
                buttons.extend(card.findChildren(QToolButton))
        visible_buttons = [button for button in buttons if not button.isHidden() and button.isEnabled()]
        assert len(visible_buttons) == 1
        assert visible_buttons[0].text() == "Clave"
    finally:
        window.close()
        _pump(app)


def test_hotspot_dialog_clamps_new_saved_text_to_40_characters() -> None:
    app = _app()
    dialog = HotspotContentDialog(Hotspot("h1", message_text="x" * 60))
    try:
        assert dialog.message_counter.toolTip() == f"Maximum {HOTSPOT_MESSAGE_MAX_CHARS} characters"
        assert dialog.result_hotspot().message_text == "x" * HOTSPOT_MESSAGE_MAX_CHARS
    finally:
        dialog.close()
        _pump(app)


def test_hotspot_bubble_elides_legacy_long_text_and_stays_inside_video() -> None:
    app = _app()
    window = EditorWindow()
    try:
        hotspot = Hotspot(
            "h1",
            message_text="Mensaje heredado demasiado largo " * 8,
            geometry={"x": 0.86, "y": 0.86, "width": 0.12, "height": 0.1},
        )
        pause = PausePoint("p1", 4000, [hotspot])
        window.pauses = [pause]
        window.select_event(pause)
        window.reload_hotspots_for_pause()
        window.activate_hotspot("h1")

        assert window.output_proxy.isVisible()
        assert "\n" not in window.output_label.text()
        assert len(hotspot.message_text) > HOTSPOT_MESSAGE_MAX_CHARS
        assert window.output_label.text().endswith("…")
        assert window.output_label.font().bold()
        assert window.output_label.font().pixelSize() == 26
        assert 0 <= window.output_proxy.pos().x() <= 1536 - window.output_label.width()
        assert 0 <= window.output_proxy.pos().y() <= 864 - window.output_label.height()
    finally:
        window.close()
        _pump(app)
