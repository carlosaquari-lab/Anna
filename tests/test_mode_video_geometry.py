from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow, FRAME_HEIGHT, FRAME_WIDTH, Hotspot, PausePoint  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-mode-video-geometry"])


def _settle(app: QApplication) -> None:
    for _ in range(4):
        app.processEvents()


def _geometry_snapshot(window: EditorWindow) -> tuple:
    transform = window.view.transform()
    top_left = window.view.mapToGlobal(window.view.mapFromScene(0, 0))
    bottom_right = window.view.mapToGlobal(
        window.view.mapFromScene(FRAME_WIDTH, FRAME_HEIGHT)
    )
    return (
        (bottom_right.x() - top_left.x(), bottom_right.y() - top_left.y()),
        round(transform.m11(), 8),
        round(transform.m22(), 8),
    )


def _set_user_mode(window: EditorWindow, enabled: bool, app: QApplication) -> None:
    window.preview_btn.setChecked(enabled)
    window.toggle_preview_mode()
    _settle(app)


def test_video_geometry_is_stable_across_repeated_mode_changes(monkeypatch) -> None:
    app = _app()
    window = EditorWindow(auto_show=False)
    try:
        pause = PausePoint("p0", 0, [Hotspot("h0", message_text="Inicio")])
        window.pauses = [pause]
        window.current_video().pauses = window.pauses
        window.duration_ms = 5_000
        monkeypatch.setattr(window.player, "setPosition", lambda _value: None)
        window.resize(1600, 900)
        window.show()
        _settle(app)

        professional = _geometry_snapshot(window)
        assert professional[1] == professional[2]

        for _ in range(3):
            _set_user_mode(window, True, app)
            assert _geometry_snapshot(window) == professional
            assert window.active_event_id == "p0"
            assert set(window.items) == {"h0"}
            assert window.view.mapFromScene(0, 0) != window.view.mapFromScene(FRAME_WIDTH, FRAME_HEIGHT)

            _set_user_mode(window, False, app)
            assert _geometry_snapshot(window) == professional

        assert window.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert window.scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert not window.scroll_area.horizontalScrollBar().isVisible()
        assert not window.scroll_area.verticalScrollBar().isVisible()
    finally:
        window.close()
