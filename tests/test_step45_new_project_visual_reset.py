from PySide6.QtCore import QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QToolButton

from hotspot_editor import EditorWindow
from hotspot_model import PausePoint, VideoEntry


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_new_project_clears_all_previous_video_presentation() -> None:
    application = app()
    window = EditorWindow(auto_show=False)
    try:
        window.videos = [VideoEntry("video-old", "Old video", "old.mp4", [PausePoint("pause-old", 5_000)])]
        window.current_video_index = 0
        window.pauses = window.videos[0].pauses
        window.duration_ms = 10_000
        window.timeline.setRange(0, 10_000)
        window.timeline.setValue(5_000)
        window.timeline.set_pauses(window.pauses, 5_000)
        window.timeline.set_segment(2_000, 8_000)
        window.time_label.setText("00:00:05.000 / 00:00:10.000")
        old_frame = QPixmap(20, 20)
        old_frame.fill()
        window.poster_item.setPixmap(old_frame)
        window.poster_item.show()

        window.new_project()
        application.sendPostedEvents()
        application.processEvents()

        assert len(window.videos) == 1
        assert window.videos[0].source == ""
        visible_buttons = [
            window.video_nav_layout.itemAt(index).widget()
            for index in range(window.video_nav_layout.count())
            if isinstance(window.video_nav_layout.itemAt(index).widget(), QToolButton)
        ]
        assert len(visible_buttons) == 1
        assert visible_buttons[0].text() == "+"
        assert window.player.source() == QUrl()
        assert window.poster_item.pixmap().isNull()
        assert not window.poster_item.isVisible()
        assert window.duration_ms == 0
        assert window.time_label.text() == "00:00:00.000 / 00:00:00.000"
        assert window.timeline.value() == 0
        assert window.timeline.maximum() == 1
        assert window.timeline.pause_times == []
        assert window.timeline.segment_start_ms == 0
        assert window.timeline.segment_end_ms is None
        assert not window.segment_start_value.isEnabled()
        assert not window.segment_end_value.isEnabled()
        assert not window.save_segment_btn.isEnabled()
        assert not window.reset_segment_btn.isEnabled()
    finally:
        window.close()
