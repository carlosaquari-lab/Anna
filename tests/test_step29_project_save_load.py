from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QLabel, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import (  # noqa: E402
    Hotspot,
    PausePoint,
    SupportItem,
    VideoEntry,
    default_project,
    serialize_project,
    videos_from_project_payload,
)
from temporal_event_engine import PlaybackMode  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step29-project-save-load"])


def test_project_payload_round_trips_complete_pause_content_and_load_clears_transient_state(monkeypatch) -> None:
    pause_1 = PausePoint(
        "pause-1000",
        1000,
        [
            Hotspot(
                "rect-1",
                name="Rectangulo",
                shape="rectangle",
                geometry={"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                color="#FF0000",
                fill_opacity=40,
                message_text="Hola",
                hotspot_label="Saludo",
                show_message_text=True,
                communication_category="social_expression",
                audio_asset="assets/audio/hotspots/hola.wav",
                font_family="Segoe UI",
                font_size_px=28,
                font_bold=True,
                uppercase=False,
                text_color="#111111",
                background_color="#FFFF00",
                background_opacity=75,
                tts_enabled=False,
            ),
            Hotspot(
                "ellipse-1",
                shape="ellipse",
                geometry={"x": 0.5, "y": 0.2, "width": 0.2, "height": 0.2},
                message_text="Mas",
                communication_category="noun_object",
                tts_enabled=True,
            ),
        ],
        [
            SupportItem(
                "support_1",
                "Apoyo 1",
                "Agua",
                image_asset="assets/supports/images/agua.png",
                audio_asset="assets/supports/audio/agua.wav",
                tts_enabled=False,
                visible=True,
                position=0,
                communication_category="noun_object",
            ),
            SupportItem("support_2", "Apoyo 2", "Oculto", visible=False, position=1),
        ],
    )
    pause_2 = PausePoint(
        "pause-2000",
        2000,
        [Hotspot("rect-2", message_text="Adios", tts_enabled=True)],
        [SupportItem("support_1", "Apoyo 1", "Pan", visible=True, position=0)],
    )
    video_1 = VideoEntry("video-1", "Video uno", "media/video-uno.mp4", [pause_1, pause_2])
    video_2 = VideoEntry(
        "video-2",
        "Video dos",
        "media/video-dos.mp4",
        [
            PausePoint(
                "pause-3000",
                3000,
                [Hotspot("ellipse-2", shape="ellipse", message_text="Segundo video", tts_enabled=False)],
                [SupportItem("support_1", "Apoyo 1", "Listo", visible=True, position=0)],
            )
        ],
    )

    payload = serialize_project(default_project(), video_1.pauses, 6000, [video_1, video_2], 1)
    restored_videos = videos_from_project_payload(payload)

    restored_pause = restored_videos[0].pauses[0]
    restored_hotspot = restored_pause.hotspots[0]
    assert restored_hotspot.shape == "rectangle"
    assert restored_hotspot.message_text == "Hola"
    assert restored_hotspot.communication_category == "social_expression"
    assert restored_hotspot.audio_asset == "assets/audio/hotspots/hola.wav"
    assert restored_hotspot.tts_enabled is False
    assert restored_pause.hotspots[1].shape == "ellipse"
    assert restored_pause.supports[0].visible is True
    assert restored_pause.supports[0].audio_asset == "assets/supports/audio/agua.wav"
    assert restored_pause.supports[0].tts_enabled is False
    assert restored_pause.supports[1].visible is False
    assert restored_videos[1].pauses[0].hotspots[0].tts_enabled is False

    legacy_hotspot = Hotspot.from_dict({"hotspot_id": "legacy-hotspot"})
    legacy_support = SupportItem.from_dict({"support_id": "support_1", "text": "Legacy"})
    assert legacy_hotspot.tts_enabled is True
    assert legacy_support.tts_enabled is True
    assert legacy_support.visible is True

    app = _app()
    window = EditorWindow()
    try:
        monkeypatch.setattr(window.player, "setSource", lambda _url: None)
        monkeypatch.setattr(window, "prime_current_video_frame", lambda: None)
        window.active_event_id = "old-pause"
        window.selected_event_id = "old-pause"
        window.selected_pause_ms = 999
        window.current_hotspot_id = "old-hotspot"
        window.active_hotspot_id = "old-hotspot"
        window.pause_states = {999: "consumed"}
        window._manual_seek_target_ms = 999
        window.output_label.setText("RESIDUAL")
        window.output_proxy.show()

        window.restore_snapshot(payload)

        assert window.current_video_index == 1
        assert [video.video_id for video in window.videos] == ["video-1", "video-2"]
        assert [pause.pause_id for pause in window.pauses] == ["pause-3000"]
        assert window.active_event_id is None
        assert window.selected_event_id is None
        assert window.current_hotspot_id is None
        assert window.active_hotspot_id is None
        assert window.pause_states == {}
        assert window._manual_seek_target_ms is None
        assert window.output_label.text() == ""
        assert not window.output_proxy.isVisible()
        assert window.items == {}
        assert window.support_buttons_layout.count() == 3

        saved_to: list[Path] = []
        project_path = Path("project.json")
        window.project_path = project_path
        monkeypatch.setattr(Path, "write_text", lambda self, *_args, **_kwargs: saved_to.append(self) or 0)
        monkeypatch.setattr("hotspot_editor.QFileDialog.getSaveFileName", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Guardar no debe abrir dialogo si ya hay ruta")))

        window.save_json()

        assert saved_to == [project_path]
        assert window.project_path == project_path
    finally:
        window.close()
        app.processEvents()


def test_selecting_another_video_resets_playback_and_clears_visible_state(monkeypatch) -> None:
    app = _app()
    window = EditorWindow()
    position = {"value": 1400}
    paused: list[bool] = []
    played: list[bool] = []
    sources: list[QUrl] = []
    set_positions: list[int] = []
    try:
        monkeypatch.setattr(window.player, "pause", lambda: paused.append(True))
        monkeypatch.setattr(window.player, "play", lambda: played.append(True))
        monkeypatch.setattr(window.player, "position", lambda: position["value"])

        def set_position(value: int) -> None:
            position["value"] = int(value)
            set_positions.append(int(value))

        monkeypatch.setattr(window.player, "setPosition", set_position)
        monkeypatch.setattr(window.player, "setSource", lambda url: sources.append(url))

        window.preview_mode = True
        window.videos = [
            VideoEntry("video-1", "Video uno", "media/video-uno.mp4", [PausePoint("pause-1", 1000, [Hotspot("old-hotspot")], [SupportItem("support_1", "Apoyo 1", "Viejo", visible=True, position=0)])]),
            VideoEntry("video-2", "Video dos", "media/video-dos.mp4", []),
        ]
        window.current_video_index = 0
        window.pauses = window.videos[0].pauses
        window.timeline.setRange(0, 5000)
        window.timeline.setValue(1400)
        window.playback_controller.start_playback(1400, user_mode=True)
        window.playback_controller.pending_continue_position_ms = 1600
        window._manual_seek_target_ms = 1400
        window.active_event_id = "pause-1"
        window.current_hotspot_id = "old-hotspot"
        window.active_hotspot_id = "old-hotspot"
        window.add_hotspot_item(window.pauses[0].hotspots[0])
        window.support_buttons_layout.addWidget(QLabel("Residual"))
        window.output_label.setText("RESIDUAL")
        window.output_proxy.show()

        window.select_video(1)

        assert position["value"] == 0
        assert set_positions[-1] == 0
        assert window.timeline.value() == 0
        assert window.playback_controller.mode is PlaybackMode.STOPPED
        assert window.playback_controller.pending_continue_position_ms is None
        assert window._manual_seek_target_ms is None
        assert window.active_event_id is None
        assert window.current_hotspot_id is None
        assert window.active_hotspot_id is None
        assert window.items == {}
        assert window.support_buttons_layout.count() == 0
        assert window.output_label.text() == ""
        assert not window.output_proxy.isVisible()
        assert paused
        assert played == []
        assert sources

        add_buttons = [
            button
            for button in window.video_nav.findChildren(QToolButton)
            if button.objectName() == "addVideoButton"
        ]
        assert add_buttons
        assert all(button.text() == "+" for button in add_buttons)
        assert all(button.toolTip() in {"", "Añadir vídeo"} for button in add_buttons)
    finally:
        window.close()
        app.processEvents()
