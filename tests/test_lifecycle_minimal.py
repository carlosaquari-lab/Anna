from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow  # noqa: E402


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def test_editor_window_constructs_hidden_and_closes_cleanly() -> None:
    app = QApplication.instance() or QApplication(["test-anna-lifecycle"])
    window = EditorWindow(auto_show=False)
    try:
        assert not window.isVisible()
        assert window.videos
        assert window.current_video().pauses is window.pauses
        _pump(app, 0.05)
    finally:
        window.hotspot_audio_player.stop()
        window.player.stop()
        window.player.setVideoOutput(None)
        window.player.setAudioOutput(None)
        window.close()
        window.deleteLater()
        _pump(app, 0.1)
