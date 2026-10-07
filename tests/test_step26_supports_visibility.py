from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow, SupportConfigDialog  # noqa: E402
from hotspot_model import PausePoint, SupportItem  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step26-supports-visibility"])


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def _support_texts(window: EditorWindow) -> list[str]:
    texts: list[str] = []
    for index in range(window.support_buttons_layout.count()):
        widget = window.support_buttons_layout.itemAt(index).widget()
        if widget is None:
            continue
        buttons = widget.findChildren(QToolButton)
        texts.extend(button.text() for button in buttons)
    return texts


def test_user_mode_shows_only_visible_supports_and_preserves_visible_field() -> None:
    app = _app()
    window = EditorWindow()
    try:
        supports = [
            SupportItem("support_1", "Apoyo 1", "Agua", visible=True, position=0),
            SupportItem("support_2", "Apoyo 2", "Oculto", visible=False, position=1),
            SupportItem("support_3", "Apoyo 3", "Más", visible=True, position=2),
        ]
        pause = PausePoint("pause-1", 1000, supports=supports)
        window.pauses = [pause]
        window.current_video().pauses = window.pauses
        window.preview_mode = True
        window.active_event_id = "pause-1"

        window.refresh_support_panel()

        assert window.support_buttons_layout.count() == 2
        texts = _support_texts(window)
        assert texts == ["Agua", "Más"]
        assert "Oculto" not in texts
        assert all("Apoyo" not in text for text in texts)
        assert all("support_" not in text for text in texts)

        window.clear_active_interaction()

        assert window.support_buttons_layout.count() == 0

        snapshot = window.snapshot()
        saved_supports = snapshot["videos"][0]["pauses"][0]["supports"]
        assert [item["visible"] for item in saved_supports] == [True, False, True]

        restored = EditorWindow()
        try:
            restored.restore_snapshot(snapshot)
            restored_supports = restored.current_video().pauses[0].supports
            assert [support.visible for support in restored_supports] == [True, False, True]

            dialog = SupportConfigDialog(restored_supports[1], "Apoyo 2")
            try:
                assert dialog.visible.isChecked() is False
            finally:
                dialog.close()
                _pump(app)
        finally:
            restored.close()
            _pump(app)
    finally:
        window.close()
        _pump(app)
