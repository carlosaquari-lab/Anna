from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import VideoEntry  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-video-thumbnail-retention"])


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def disconnect(self) -> None:
        self.callback = None


class _Sink:
    instances: list["_Sink"] = []

    def __init__(self, _parent=None) -> None:
        self.videoFrameChanged = _Signal()
        self.instances.append(self)

    def deleteLater(self) -> None:
        pass


class _Player:
    instances: list["_Player"] = []

    def __init__(self, _parent=None) -> None:
        self.instances.append(self)

    def setVideoOutput(self, _sink) -> None:
        pass

    def setSource(self, _source) -> None:
        pass

    def play(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def deleteLater(self) -> None:
        pass


class _Frame:
    def __init__(self, color: str) -> None:
        self.image = QImage(160, 90, QImage.Format.Format_RGB32)
        self.image.fill(QColor(color))

    def toImage(self) -> QImage:
        return self.image


def _nav_icons(window: EditorWindow) -> list[QPixmap]:
    return [
        button.icon().pixmap(button.iconSize())
        for button in window.video_nav.findChildren(QToolButton)
        if button.objectName() == "videoThumbButton"
    ]


def test_two_video_thumbnails_are_serialized_and_survive_all_nav_refreshes(monkeypatch, tmp_path) -> None:
    app = _app()
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mp4"
    first.touch()
    second.touch()
    window = EditorWindow(auto_show=False)
    try:
        _Sink.instances.clear()
        _Player.instances.clear()
        monkeypatch.setattr(hotspot_editor, "QVideoSink", _Sink)
        monkeypatch.setattr(hotspot_editor, "QMediaPlayer", _Player)
        monkeypatch.setattr(hotspot_editor.QTimer, "singleShot", lambda _ms, _callback: None)
        monkeypatch.setattr(window.player, "setSource", lambda _source: None)
        monkeypatch.setattr(window.player, "setPosition", lambda _position: None)
        monkeypatch.setattr(window.player, "position", lambda: 0)

        window.videos = [
            VideoEntry("video-1", "Video 1", str(first), []),
            VideoEntry("video-2", "Video 2", str(second), []),
        ]
        window.current_video_index = 0
        window.pauses = []
        window.video_thumbnails.clear()
        window.thumbnail_requests.clear()
        window.thumbnail_extractors.clear()

        window.refresh_video_nav()
        assert window.thumbnail_requests == {"video-1"}
        assert len(_Player.instances) == 1

        _Sink.instances[0].videoFrameChanged.callback(_Frame("red"))
        assert "video-1" in window.video_thumbnails
        assert window.thumbnail_requests == {"video-2"}
        assert len(_Player.instances) == 2

        _Sink.instances[1].videoFrameChanged.callback(_Frame("blue"))
        assert set(window.video_thumbnails) == {"video-1", "video-2"}
        assert window.thumbnail_requests == set()
        assert all(not pixmap.isNull() for pixmap in _nav_icons(window))

        for _ in range(3):
            window.select_video(1)
            window.select_video(0)
            window.preview_btn.setChecked(True)
            window.toggle_preview_mode()
            window.preview_btn.setChecked(False)
            window.toggle_preview_mode()
            window.refresh_video_nav()

        assert set(window.video_thumbnails) == {"video-1", "video-2"}
        assert len(_Player.instances) == 2
        assert all(not pixmap.isNull() for pixmap in _nav_icons(window))

        payload = window.snapshot()
        window.restore_snapshot(payload)
        assert window.thumbnail_requests == {"video-1"}
        _Sink.instances[2].videoFrameChanged.callback(_Frame("red"))
        _Sink.instances[3].videoFrameChanged.callback(_Frame("blue"))
        assert set(window.video_thumbnails) == {"video-1", "video-2"}
        assert all(not pixmap.isNull() for pixmap in _nav_icons(window))
    finally:
        window.close()
        app.processEvents()
