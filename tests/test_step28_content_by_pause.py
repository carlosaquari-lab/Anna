from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import Hotspot, PausePoint, SupportItem  # noqa: E402
from temporal_event_engine import PlaybackMode  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step28-content-by-pause"])


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


def test_pause_activation_cleans_and_rebuilds_only_its_own_content(monkeypatch) -> None:
    app = _app()
    window = EditorWindow()
    callbacks: list[callable] = []
    try:
        monkeypatch.setattr(window.player, "setPosition", lambda _value: None)
        monkeypatch.setattr(window.player, "play", lambda: None)
        monkeypatch.setattr("hotspot_editor.QTimer.singleShot", lambda _ms, callback: callbacks.append(callback))

        pause_1 = PausePoint(
            "pause-1",
            1000,
            [
                Hotspot("h1a", message_text="Uno A"),
                Hotspot("h1b", message_text="Uno B"),
            ],
            [
                SupportItem("support_1", "Apoyo 1", "Agua", visible=True, position=0),
                SupportItem("support_2", "Apoyo 2", "Más", visible=True, position=1),
                SupportItem("support_3", "Apoyo 3", "Oculto", visible=False, position=2),
            ],
        )
        pause_2 = PausePoint(
            "pause-2",
            1300,
            [Hotspot("h2a", message_text="Dos A")],
            [
                SupportItem("support_1", "Apoyo 1", "Pan", visible=True, position=0),
                SupportItem("support_2", "Apoyo 2", "", visible=False, position=1),
                SupportItem("support_3", "Apoyo 3", "", visible=False, position=2),
            ],
        )
        window.pauses = [pause_1, pause_2]
        window.current_video().pauses = window.pauses
        window.duration_ms = 5000
        window.timeline.setRange(0, 5000)
        window.preview_mode = True
        window.playback_controller.start_playback(0, user_mode=True)

        window.on_position_changed(1000)

        assert window.active_event_id == "pause-1"
        assert set(window.items) == {"h1a", "h1b"}
        assert window.support_buttons_layout.count() == 2
        assert _support_texts(window) == ["Agua", "Más"]

        window.activate_hotspot("h1a")

        assert window.active_event_id == "pause-1"
        assert set(window.items) == {"h1a", "h1b"}
        assert window.output_label.text() == "UNO A"

        window.activate_support(pause_1.supports[0])

        assert window.active_event_id == "pause-1"
        assert set(window.items) == {"h1a", "h1b"}
        assert window.support_buttons_layout.count() == 2
        assert window.continue_btn.isEnabled()

        window.continue_from_pause()

        assert window.active_event_id is None
        assert window.items == {}
        assert window.support_buttons_layout.count() == 0
        assert window.output_label.text() == ""
        assert not window.output_proxy.isVisible()
        assert not window.continue_btn.isEnabled()

        exit_position = window.playback_controller.pending_continue_position_ms
        assert exit_position is not None
        window.on_position_changed(exit_position)
        window.on_position_changed(1300)

        assert window.active_event_id == "pause-2"
        assert set(window.items) == {"h2a"}
        assert window.support_buttons_layout.count() == 1
        assert _support_texts(window) == ["Pan"]
        assert window.output_label.text() == ""

        window.clear_active_interaction()
        window.playback_controller.start_playback(0, user_mode=True)
        window.on_position_changed(1000)

        assert window.active_event_id == "pause-1"
        assert set(window.items) == {"h1a", "h1b"}
        assert len(window.items) == 2
        assert window.support_buttons_layout.count() == 2
        assert _support_texts(window) == ["Agua", "Más"]
    finally:
        window.close()
        _pump(app)
