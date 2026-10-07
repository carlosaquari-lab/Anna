from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import Hotspot, PausePoint, SupportItem, VideoEntry  # noqa: E402
from temporal_event_engine import PlaybackMode  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step30-video-management"])


def _install_player_spies(monkeypatch, window: EditorWindow) -> tuple[dict[str, int], list[bool], list[bool], list[QUrl], list[int]]:
    position = {"value": 1250}
    paused: list[bool] = []
    played: list[bool] = []
    sources: list[QUrl] = []
    set_positions: list[int] = []

    monkeypatch.setattr(window.player, "pause", lambda: paused.append(True))
    monkeypatch.setattr(window.player, "play", lambda: played.append(True))
    monkeypatch.setattr(window.player, "position", lambda: position["value"])

    def set_position(value: int) -> None:
        position["value"] = int(value)
        set_positions.append(int(value))

    monkeypatch.setattr(window.player, "setPosition", set_position)
    monkeypatch.setattr(window.player, "setSource", lambda url: sources.append(url))
    return position, paused, played, sources, set_positions


def _populate_project(window: EditorWindow) -> None:
    window.videos = [
        VideoEntry("video-1", "Vídeo 1", "media/uno.mp4", []),
        VideoEntry(
            "video-2",
            "Vídeo 2",
            "media/dos.mp4",
            [
                PausePoint(
                    "pause-2",
                    1000,
                    [Hotspot("hotspot-2", message_text="Dos")],
                    [SupportItem("support_1", "Apoyo 1", "Dos", visible=True, position=0)],
                )
            ],
        ),
        VideoEntry("video-3", "Vídeo 3", "media/tres.mp4", [PausePoint("pause-3", 1500, [Hotspot("hotspot-3")], [])]),
    ]
    window.current_video_index = 0
    window.pauses = window.videos[0].pauses
    window.timeline.setRange(0, 5000)


def _dirty_visible_state(window: EditorWindow) -> None:
    window.preview_mode = True
    window.timeline.setValue(1250)
    window.playback_controller.start_playback(1250, user_mode=True)
    window.playback_controller.pending_continue_position_ms = 1450
    window._manual_seek_target_ms = 1250
    window.active_event_id = "pause-2"
    window.current_hotspot_id = "hotspot-2"
    window.active_hotspot_id = "hotspot-2"
    window.items["residual"] = object()
    window.support_buttons_layout.addWidget(QLabel("Residual"))
    window.output_label.setText("RESIDUAL")
    window.output_proxy.show()


def test_video_thumbnail_management_selects_replaces_deletes_and_keeps_target_identity(monkeypatch) -> None:
    app = _app()
    window = EditorWindow()
    position, paused, played, sources, set_positions = _install_player_spies(monkeypatch, window)
    try:
        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: True)
        monkeypatch.setattr(window, "request_video_thumbnail", lambda _video: None)
        monkeypatch.setattr(window.scene, "removeItem", lambda _item: None)
        _populate_project(window)

        _dirty_visible_state(window)
        window.select_video(1)

        assert window.current_video().video_id == "video-2"
        assert position["value"] == 0
        assert set_positions[-1] == 0
        assert window.timeline.value() == 0
        assert window.playback_controller.mode is PlaybackMode.STOPPED
        assert window.playback_controller.pending_continue_position_ms is None
        assert window.active_event_id is None
        assert window.items == {}
        assert window.support_buttons_layout.count() == 0
        assert window.output_label.text() == ""
        assert not window.output_proxy.isVisible()
        assert paused
        assert played == []
        assert sources

        add_buttons = [button for button in window.video_nav.findChildren(QToolButton) if button.objectName() == "addVideoButton"]
        assert add_buttons
        assert all(button.text() == "+" for button in add_buttons)
        assert all(button.objectName() == "addVideoButton" for button in add_buttons)

        window.preview_mode = False
        monkeypatch.setattr(window, "confirm_replace_video_content_removal", lambda: False)
        monkeypatch.setattr(hotspot_editor.QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("No debe abrir selector si se cancela la confirmación")))
        original_video_2 = window.videos[1]

        window.replace_video(1)

        assert window.videos[1] is original_video_2
        assert window.videos[1].pauses

        monkeypatch.setattr(window, "confirm_replace_video_content_removal", lambda: True)
        monkeypatch.setattr(hotspot_editor.QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: ("media/dos-nuevo.mp4", ""))

        window.replace_video(1)

        assert window.current_video_index == 1
        assert window.videos[1].video_id == "video-2"
        assert window.videos[1].source == str(Path("media/dos-nuevo.mp4"))
        assert window.videos[1].pauses == []
        assert window.pauses == []
        assert window.timeline.pause_times == []
        assert position["value"] == 0

        deleted_snapshot = [video.video_id for video in window.videos]
        monkeypatch.setattr(hotspot_editor.QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.No)

        window.delete_video(1)

        assert [video.video_id for video in window.videos] == deleted_snapshot

        monkeypatch.setattr(hotspot_editor.QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes)
        window.current_video_index = 0

        window.delete_video(1)

        assert [video.video_id for video in window.videos] == ["video-1", "video-3"]
        assert window.current_video().video_id == "video-3"
        assert all(video.video_id != "video-2" for video in window.videos)
        assert all(pause.pause_id != "pause-2" for video in window.videos for pause in video.pauses)
        assert position["value"] == 0

        class FakeMenu:
            next_label = "Delete video"
            last_labels: list[str] = []

            class FakeAction:
                def __init__(self) -> None:
                    self.enabled = True

                def setEnabled(self, enabled: bool) -> None:
                    self.enabled = enabled

            def __init__(self, _parent=None) -> None:
                self.actions: dict[str, object] = {}

            def addAction(self, label: str):
                action = self.FakeAction()
                self.actions[label] = action
                FakeMenu.last_labels.append(label)
                return action

            def exec(self, _global_pos):
                return self.actions[self.next_label]

        monkeypatch.setattr(hotspot_editor, "QMenu", FakeMenu)
        window.videos = [
            VideoEntry("video-1", "Vídeo 1", "media/uno.mp4", []),
            VideoEntry("video-3", "Vídeo 3", "media/tres.mp4", []),
        ]
        window.current_video_index = 0

        window.show_video_context_menu("video-3", None)

        assert [video.video_id for video in window.videos] == ["video-1"]
        assert FakeMenu.last_labels == ["Rename video…", "Replace video…", "Delete video"]

        infos: list[str] = []
        monkeypatch.setattr(hotspot_editor.QMessageBox, "information", lambda _parent, _title, text: infos.append(text))

        window.delete_video(0)

        assert [video.video_id for video in window.videos] == ["video-1"]
        assert infos == ["The project must contain at least one video."]
        assert window.timeline.value() == 0
        assert position["value"] == 0
    finally:
        window.close()
        app.processEvents()


def test_replacing_video_clears_only_that_entry_and_survives_save_load(monkeypatch, tmp_path) -> None:
    app = _app()
    window = EditorWindow()
    position, paused, played, sources, set_positions = _install_player_spies(monkeypatch, window)
    try:
        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: True)
        monkeypatch.setattr(window, "request_video_thumbnail", lambda _video: None)
        monkeypatch.setattr(window.scene, "removeItem", lambda _item: None)
        _populate_project(window)

        confirm_calls: list[bool] = []

        def unexpected_confirmation() -> bool:
            confirm_calls.append(True)
            raise AssertionError("No debe pedir confirmacion si la entrada no contiene pausas")

        monkeypatch.setattr(window, "confirm_replace_video_content_removal", unexpected_confirmation)
        monkeypatch.setattr(hotspot_editor.QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: ("media/uno-nuevo.mp4", ""))

        window.replace_video(0)

        assert confirm_calls == []
        assert window.videos[0].source == str(Path("media/uno-nuevo.mp4"))
        assert window.videos[0].pauses == []
        assert [pause.pause_id for pause in window.videos[1].pauses] == ["pause-2"]
        assert [pause.pause_id for pause in window.videos[2].pauses] == ["pause-3"]

        window.select_video(1)
        window.active_event_id = "pause-2"
        window.selected_event_id = "pause-2"
        window.selected_pause_ms = 1000
        window.current_hotspot_id = "hotspot-2"
        window.active_hotspot_id = "hotspot-2"
        window.active_support_id = "support_1"
        window.playback_controller.start_playback(1000, user_mode=True)
        window.playback_controller.pending_continue_position_ms = 1200
        window._manual_seek_target_ms = 1000
        window.timeline.set_pauses(window.pauses, 1000)

        monkeypatch.setattr(window, "confirm_replace_video_content_removal", lambda: False)
        monkeypatch.setattr(hotspot_editor.QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("No debe abrir selector si se cancela")))
        original_source = window.videos[1].source
        original_pauses = window.videos[1].pauses

        window.replace_video(1)

        assert window.videos[1].source == original_source
        assert window.videos[1].pauses is original_pauses
        assert window.active_event_id == "pause-2"
        assert window.playback_controller.pending_continue_position_ms == 1200

        monkeypatch.setattr(window, "confirm_replace_video_content_removal", lambda: True)
        monkeypatch.setattr(hotspot_editor.QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: ("media/dos-nuevo.mp4", ""))

        window.replace_video(1)

        assert window.current_video().video_id == "video-2"
        assert window.current_video().source == str(Path("media/dos-nuevo.mp4"))
        assert window.current_video().pauses == []
        assert window.pauses == []
        assert window.timeline.pause_times == []
        assert window.selected_event_id is None
        assert window.selected_pause_ms is None
        assert window.active_event_id is None
        assert window.current_hotspot_id is None
        assert window.active_hotspot_id is None
        assert window.active_support_id is None
        assert window.playback_controller.mode is PlaybackMode.STOPPED
        assert window.playback_controller.pending_continue_position_ms is None
        assert window._manual_seek_target_ms is None
        assert window.duration_ms == 0
        assert position["value"] == 0
        assert set_positions[-1] == 0
        assert paused
        assert played == []
        assert sources
        assert [pause.pause_id for pause in window.videos[2].pauses] == ["pause-3"]

        monkeypatch.setattr(hotspot_editor.QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes)
        window.delete_video(2)

        assert [video.video_id for video in window.videos] == ["video-1", "video-2"]
        assert window.current_video().video_id == "video-2"
        assert window.current_video().pauses == []
        assert all(pause.pause_id != "pause-3" for video in window.videos for pause in video.pauses)
        assert window.timeline.pause_times == []

        saved_path = tmp_path / "replaced_project.json"
        saved_path.write_text(json.dumps(window.snapshot(), ensure_ascii=False), encoding="utf-8")

        loaded = EditorWindow()
        try:
            monkeypatch.setattr(loaded, "request_video_thumbnail", lambda _video: None)
            monkeypatch.setattr(loaded.scene, "removeItem", lambda _item: None)
            loaded.restore_snapshot(json.loads(saved_path.read_text(encoding="utf-8")))

            assert [video.video_id for video in loaded.videos] == ["video-1", "video-2"]
            assert loaded.videos[0].source == str(Path("media/uno-nuevo.mp4"))
            assert loaded.videos[1].source == str(Path("media/dos-nuevo.mp4"))
            assert loaded.videos[1].pauses == []
            assert loaded.pauses == []
            assert loaded.timeline.pause_times == []
        finally:
            loaded.close()
            app.processEvents()
    finally:
        window.close()
        app.processEvents()


def test_deleting_video_rebuilds_timeline_with_only_remaining_active_video_pauses(monkeypatch) -> None:
    app = _app()
    window = EditorWindow()
    position, _paused, _played, _sources, _set_positions = _install_player_spies(monkeypatch, window)
    try:
        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: True)
        monkeypatch.setattr(window, "request_video_thumbnail", lambda _video: None)
        monkeypatch.setattr(window.scene, "removeItem", lambda _item: None)
        monkeypatch.setattr(hotspot_editor.QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes)

        window.videos = [
            VideoEntry("video-1", "Vídeo 1", "media/uno.mp4", [PausePoint("pause-1000", 1000, [Hotspot("hotspot-1")], [])]),
            VideoEntry("video-2", "Vídeo 2", "media/dos.mp4", [PausePoint("pause-2000", 2000, [Hotspot("hotspot-2")], [])]),
            VideoEntry("video-3", "Vídeo 3", "media/tres.mp4", [PausePoint("pause-3000", 3000, [Hotspot("hotspot-3")], [])]),
        ]
        window.current_video_index = 1
        window.pauses = window.videos[1].pauses
        window.timeline.setRange(0, 5000)
        window.timeline.set_pauses(window.pauses, None)

        window.delete_video(1)

        assert [video.video_id for video in window.videos] == ["video-1", "video-3"]
        assert window.current_video().video_id == "video-3"
        assert [pause.time_ms for pause in window.pauses] == [3000]
        assert window.timeline.pause_times == [3000]
        assert 2000 not in window.timeline.pause_times
        assert position["value"] == 0

        window.delete_video(1)

        assert [video.video_id for video in window.videos] == ["video-1"]
        assert window.current_video().video_id == "video-1"
        assert [pause.time_ms for pause in window.pauses] == [1000]
        assert window.timeline.pause_times == [1000]
        assert 2000 not in window.timeline.pause_times
        assert 3000 not in window.timeline.pause_times

        infos: list[str] = []
        monkeypatch.setattr(hotspot_editor.QMessageBox, "information", lambda _parent, _title, text: infos.append(text))

        window.delete_video(0)

        assert [video.video_id for video in window.videos] == ["video-1"]
        assert window.timeline.pause_times == [1000]
        assert infos == ["The project must contain at least one video."]
    finally:
        window.close()
        app.processEvents()
