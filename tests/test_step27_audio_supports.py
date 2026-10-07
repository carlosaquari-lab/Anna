from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import EditorWindow, SupportConfigDialog  # noqa: E402
from hotspot_model import PausePoint, SupportItem  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step27-audio-supports"])


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


class FakeTts:
    def __init__(self) -> None:
        self.said: list[str] = []
        self.stops = 0

    def stop(self) -> None:
        self.stops += 1

    def say(self, text: str) -> None:
        self.said.append(text)


class StillRecordingAfterStop:
    def __init__(self) -> None:
        self.stops = 0

    def stop(self) -> None:
        self.stops += 1

    def recorderState(self):
        return hotspot_editor.QMediaRecorder.RecorderState.RecordingState


def test_support_activation_audio_tts_persistence_recording_and_delete(monkeypatch) -> None:
    app = _app()
    window = EditorWindow()
    fake_tts = FakeTts()
    requested_audio: list[Path | None] = []
    try:
        audio_support = SupportItem("support_1", "Audio", "Voz", audio_asset="assets/supports/audio/voice.wav", tts_enabled=True, visible=True, position=0)
        tts_support = SupportItem("support_2", "TTS", "Leer", tts_enabled=True, visible=True, position=1)
        silent_support = SupportItem("support_3", "Silencio", "Callar", tts_enabled=False, visible=True, position=2)
        pause = PausePoint("pause-1", 1000, supports=[audio_support, tts_support, silent_support])
        window.pauses = [pause]
        window.current_video().pauses = window.pauses
        window.preview_mode = True
        window.active_event_id = "pause-1"
        window.support_tts = fake_tts
        monkeypatch.setattr(window, "play_interaction_audio", lambda path: requested_audio.append(path) or True)

        window.activate_support(audio_support)
        window.activate_support(tts_support)
        window.activate_support(silent_support)

        assert requested_audio == [window.support_asset_path("assets/supports/audio/voice.wav")]
        assert fake_tts.said == ["Leer"]

        dialog = SupportConfigDialog(SupportItem("support_1", "Apoyo 1", "Texto", tts_enabled=False, visible=True), "Apoyo 1")
        try:
            assert dialog.tts_enabled.isChecked() is False
            result = dialog.result_support()
            assert result.tts_enabled is False
            restored = SupportItem.from_dict(result.to_dict())
            assert restored.tts_enabled is False
        finally:
            dialog.close()
            _pump(app)

        recording_dialog = SupportConfigDialog(SupportItem("support_1", "Apoyo 1", audio_asset="assets/supports/audio/recorded.wav", visible=True), "Apoyo 1")
        recorder = StillRecordingAfterStop()
        try:
            recording_dialog.recorder = recorder
            recording_dialog.update_audio_status()

            assert recording_dialog.record_btn.isChecked()
            assert recording_dialog.record_btn.isDown()
            assert recording_dialog.stop_record_btn.isEnabled()

            recording_dialog.stop_recording()

            assert recorder.stops == 1
            assert recording_dialog.recorder is None
            assert recording_dialog.audio_status.text() == "Audio ready"
            assert not recording_dialog.record_btn.isChecked()
            assert not recording_dialog.record_btn.isDown()
            assert recording_dialog.listen_btn.isEnabled()
            assert recording_dialog.delete_audio_btn.isEnabled()
            assert not recording_dialog.stop_record_btn.isEnabled()
            assert not recording_dialog.stop_record_btn.isChecked()
            assert not recording_dialog.stop_record_btn.isDown()
        finally:
            recording_dialog.close()
            _pump(app)

        delete_dialog = SupportConfigDialog(
            SupportItem(
                "support_1",
                "Apoyo 1",
                "Texto",
                image_asset="assets/supports/images/image.png",
                audio_asset="assets/supports/audio/delete.wav",
                tts_enabled=False,
                visible=True,
                communication_category="noun",
            ),
            "Apoyo 1",
        )
        try:
            delete_dialog.delete_audio()
            deleted = delete_dialog.result_support()

            assert deleted.audio_asset is None
            assert deleted.text == "Texto"
            assert deleted.image_asset == "assets/supports/images/image.png"
            assert deleted.communication_category == "noun_object"
            assert deleted.visible is True
            assert deleted.tts_enabled is False
            assert delete_dialog.audio_status.text() == "No audio"
            assert not delete_dialog.listen_btn.isEnabled()
            assert not delete_dialog.delete_audio_btn.isEnabled()
        finally:
            delete_dialog.close()
            _pump(app)
    finally:
        window.close()
        _pump(app)
