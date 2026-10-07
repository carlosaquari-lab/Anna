
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except (ImportError, ModuleNotFoundError):
    pytest.skip(
        "Prueba Qt opcional: PySide6 completo no está disponible.",
        allow_module_level=True,
    )

from hotspot_editor import EditorWindow
from playback_controller import PlaybackController

@pytest.mark.qt_integration
def test_editor_window_starts_with_expected_controller_and_layout():
    app = QApplication.instance() or QApplication([])
    window = EditorWindow()
    try:
        assert isinstance(window.playback_controller, PlaybackController)
        assert window.tool_panel.minimumWidth() == 168
        assert window.tool_panel.maximumWidth() == 168
        assert window.support_panel.minimumWidth() == 224
        assert window.support_panel.maximumWidth() == 224
    finally:
        window.close()
        app.processEvents()
