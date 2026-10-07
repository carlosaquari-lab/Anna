from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import DialogAudioController, EditorWindow, HotspotContentDialog, SupportConfigDialog  # noqa: E402
from hotspot_model import Hotspot, PausePoint, SupportItem  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step24-audio-hotspots"])


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


def test_hotspot_without_audio_saves_without_route() -> None:
    app = _app()
    dialog = HotspotContentDialog(Hotspot("h1"))
    try:
        result = dialog.result_hotspot()
        assert result.audio_asset is None
        assert getattr(result, "tts_enabled") is True
        assert dialog.audio_status.text() == "No audio"
        assert not dialog.listen_btn.isEnabled()
    finally:
        dialog.close()
        _pump(app)


def test_hotspot_stop_recording_finishes_ui_with_one_click() -> None:
    app = _app()
    dialog = HotspotContentDialog(Hotspot("h1"))
    recorder = StillRecordingAfterStop()
    try:
        dialog.recorder = recorder
        dialog.pending_audio_asset = "assets/audio/recorded.wav"
        dialog.update_audio_status()

        assert dialog.record_btn.isChecked()
        assert dialog.record_btn.isDown()
        assert dialog.stop_record_btn.isEnabled()

        dialog.stop_recording()

        assert recorder.stops == 1
        assert dialog.recorder is None
        assert dialog.audio_status.text() == "Audio ready"
        assert not dialog.record_btn.isChecked()
        assert not dialog.record_btn.isDown()
        assert dialog.listen_btn.isEnabled()
        assert dialog.delete_audio_btn.isEnabled()
        assert not dialog.stop_record_btn.isEnabled()
        assert not dialog.stop_record_btn.isChecked()
        assert not dialog.stop_record_btn.isDown()
        assert recorder in dialog._finished_recorders
    finally:
        dialog.close()
        _pump(app)


def test_hotspot_selected_audio_is_portable_and_persisted(tmp_path: Path) -> None:
    app = _app()
    source = tmp_path / "voice.wav"
    source.write_bytes(b"RIFF----WAVEfmt ")
    dialog = HotspotContentDialog(Hotspot("h1"))
    copied: Path | None = None
    try:
        asset = dialog.audio_controller.make_portable_asset(source)
        dialog.set_pending_audio_asset(asset)
        dialog.update_audio_status()
        copied = ROOT / asset

        result = dialog.result_hotspot()

        assert result.audio_asset == asset
        assert asset.startswith("assets/audio/hotspot_audio_")
        assert dialog.audio_status.text() == "Audio ready"
        assert dialog.listen_btn.isEnabled()
    finally:
        dialog.close()
        if copied and copied.exists():
            copied.unlink()
        _pump(app)


def test_reopening_hotspot_dialog_shows_previously_saved_audio() -> None:
    app = _app()
    dialog = HotspotContentDialog(Hotspot("h1", audio_asset="assets/audio/existing.wav"))
    try:
        assert dialog.pending_audio_asset == "assets/audio/existing.wav"
        assert dialog.audio_status.text() == "Audio ready"
        assert dialog.listen_btn.isEnabled()
    finally:
        dialog.close()
        _pump(app)


def test_hotspot_tts_checkbox_can_be_saved_and_reopened() -> None:
    app = _app()
    dialog = HotspotContentDialog(Hotspot("h1"))
    try:
        assert dialog.tts_enabled.isChecked() is True
        dialog.tts_enabled.setChecked(False)
        result = dialog.result_hotspot()
    finally:
        dialog.close()
        _pump(app)

    reopened = HotspotContentDialog(result)
    try:
        assert reopened.tts_enabled.isChecked() is False
        assert getattr(reopened.result_hotspot(), "tts_enabled") is False
    finally:
        reopened.close()
        _pump(app)


def test_deleting_hotspot_audio_clears_saved_route() -> None:
    app = _app()
    dialog = HotspotContentDialog(Hotspot("h1", audio_asset="assets/audio/existing.wav"))
    try:
        dialog.delete_audio()
        result = dialog.result_hotspot()

        assert result.audio_asset is None
        assert dialog.audio_status.text() == "No audio"
        assert not dialog.listen_btn.isEnabled()
    finally:
        dialog.close()
        _pump(app)


def test_hotspot_and_support_dialogs_use_same_audio_controller() -> None:
    app = _app()
    hotspot_dialog = HotspotContentDialog(Hotspot("h1"))
    support_dialog = SupportConfigDialog(SupportItem("support_1"), "Apoyo 1")
    try:
        assert isinstance(hotspot_dialog.audio_controller, DialogAudioController)
        assert isinstance(support_dialog.audio_controller, DialogAudioController)
        assert hotspot_dialog.audio_controller.play_audio.__func__ is support_dialog.audio_controller.play_audio.__func__
        assert hotspot_dialog.audio_controller.update_audio_status.__func__ is support_dialog.audio_controller.update_audio_status.__func__
    finally:
        hotspot_dialog.close()
        support_dialog.close()
        _pump(app)


def test_hotspot_click_requests_configured_audio_playback(monkeypatch, tmp_path: Path) -> None:
    app = _app()
    window = EditorWindow()
    audio_path = ROOT / "assets" / "audio" / "step24_click.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFF----WAVEfmt ")
    requested: list[Path | None] = []
    fake_tts = FakeTts()
    try:
        hotspot = Hotspot("h1", audio_asset="assets/audio/step24_click.wav")
        window.pauses = [PausePoint("p1", 1000, [hotspot])]
        window.preview_mode = True
        window.active_event_id = "p1"
        window.support_tts = fake_tts
        monkeypatch.setattr(window, "play_interaction_audio", lambda path: requested.append(path) or True)

        window.activate_hotspot("h1")

        assert requested == [audio_path]
        assert fake_tts.said == []
    finally:
        window.close()
        if audio_path.exists():
            audio_path.unlink()
        _pump(app)


def test_hotspot_without_audio_uses_tts_when_enabled() -> None:
    app = _app()
    window = EditorWindow()
    fake_tts = FakeTts()
    try:
        hotspot = Hotspot("h1", message_text="Hola mundo")
        setattr(hotspot, "tts_enabled", True)
        window.pauses = [PausePoint("p1", 1000, [hotspot])]
        window.preview_mode = True
        window.active_event_id = "p1"
        window.support_tts = fake_tts

        window.activate_hotspot("h1")

        assert fake_tts.said == ["Hola mundo"]
    finally:
        window.close()
        _pump(app)


def test_hotspot_without_audio_and_tts_disabled_stays_silent() -> None:
    app = _app()
    window = EditorWindow()
    fake_tts = FakeTts()
    try:
        hotspot = Hotspot("h1", message_text="Hola mundo")
        setattr(hotspot, "tts_enabled", False)
        window.pauses = [PausePoint("p1", 1000, [hotspot])]
        window.preview_mode = True
        window.active_event_id = "p1"
        window.support_tts = fake_tts

        window.activate_hotspot("h1")

        assert fake_tts.said == []
    finally:
        window.close()
        _pump(app)


def test_hotspot_tts_value_is_included_in_editor_snapshot() -> None:
    app = _app()
    window = EditorWindow()
    try:
        hotspot = Hotspot("h1", message_text="Hola")
        setattr(hotspot, "tts_enabled", False)
        window.pauses = [PausePoint("p1", 1000, [hotspot])]
        snapshot = window.snapshot()

        saved_hotspot = snapshot["videos"][0]["pauses"][0]["hotspots"][0]
        assert saved_hotspot["tts_enabled"] is False

        restored = EditorWindow()
        try:
            restored.restore_snapshot(snapshot)
            restored_hotspot = restored.current_video().pauses[0].hotspots[0]
            assert getattr(restored_hotspot, "tts_enabled") is False
        finally:
            restored.close()
            _pump(app)
    finally:
        window.close()
        _pump(app)


def test_missing_hotspot_audio_path_does_not_raise() -> None:
    app = _app()
    window = EditorWindow()
    try:
        window.pauses = [PausePoint("p1", 1000, [Hotspot("h1", audio_asset="assets/audio/missing.wav")])]
        window.preview_mode = True
        window.active_event_id = "p1"

        window.activate_hotspot("h1")
    finally:
        window.close()
        _pump(app)
