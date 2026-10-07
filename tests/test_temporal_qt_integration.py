from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import Hotspot, PausePoint  # noqa: E402
from temporal_event_engine import PlaybackMode  # noqa: E402


def _pump(app: QApplication, seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def _make_window() -> tuple[QApplication, EditorWindow]:
    app = QApplication.instance() or QApplication(["test-temporal-qt-integration"])
    window = EditorWindow()
    window.duration_ms = 20000
    window.timeline.setRange(0, 20000)
    window.pauses = [
        PausePoint("p4000", 4000, [Hotspot("h4000", message_text="primera")]),
        PausePoint("p12000", 12000, [Hotspot("h12000", message_text="segunda")]),
    ]
    window.timeline.set_pauses(window.pauses, None)
    return app, window


def _close_window(app: QApplication, window: EditorWindow) -> None:
    try:
        window.hotspot_audio_player.stop()
        window.player.stop()
        window.player.setVideoOutput(None)
        window.player.setAudioOutput(None)
    finally:
        window.close()
        _pump(app)


def test_temporal_state_cycle_separates_edit_selection_and_active_user_event() -> None:
    app, window = _make_window()
    try:
        # En edición, cruzar un evento no lo activa.
        window.playback_controller.start_playback(0, user_mode=False)
        window.on_position_changed(4250)
        assert window.preview_mode is False
        assert window.selected_event_id is None
        assert window.active_event_id is None

        # La selección de edición no se convierte en evento activo.
        window.goto_pause(4000)
        assert window.selected_event_id == "p4000"
        assert window.active_event_id is None

        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        assert window.preview_mode is True
        assert window.selected_event_id == "p4000"
        assert window.active_event_id is None
        assert window.items == {}

        # Reproducción: activa el primer evento exclusivamente mediante active_event_id.
        window.playback_controller.start_playback(0, user_mode=True)
        window.on_position_changed(4250)
        assert window.selected_event_id is None
        assert window.active_event_id == "p4000"
        assert window.output_label.text() == ""
        window.activate_hotspot("h4000")
        assert window.output_label.text() == "PRIMERA"

        # Continuar limpia y permite activar el segundo evento.
        window.continue_from_pause()
        assert window.active_event_id is None
        assert window.output_label.text() == ""
        window.on_position_changed(4200)
        window.on_position_changed(12100)
        assert window.active_event_id == "p12000"

        # Seek hacia atrás no activa durante navegación y permite repetir después.
        window.continue_from_pause()
        window.on_position_changed(12200)
        window.begin_slider_seek()
        window.timeline.setValue(1000)
        window.seek_during_drag(1000)
        window.finish_slider_seek()
        assert window.active_event_id is None
        assert window.selected_event_id is None

        window.playback_controller.start_playback(1000, user_mode=True)
        window.on_position_changed(4250)
        assert window.active_event_id == "p4000"

        # Volver a edición elimina el estado de reproducción.
        window.enter_edit_mode()
        assert window.preview_mode is False
        assert window.active_event_id is None
        assert window.selected_event_id is None
    finally:
        _close_window(app, window)


def test_continue_from_close_pause_exits_before_next_pause() -> None:
    app = QApplication.instance() or QApplication(["test-temporal-close-pauses"])
    window = EditorWindow()
    window.duration_ms = 5000
    window.timeline.setRange(0, 5000)
    window.pauses = [
        PausePoint("p1000", 1000, [Hotspot("h1000", message_text="primera")]),
        PausePoint("p1100", 1100, [Hotspot("h1100", message_text="segunda")]),
    ]
    window.timeline.set_pauses(window.pauses, None)
    try:
        window.preview_mode = True
        window.active_event_id = "p1000"
        window.playback_controller.begin_interaction(1000)

        window.continue_from_pause()

        exit_position = window.playback_controller.pending_continue_position_ms
        assert exit_position is not None
        assert 1000 < exit_position < 1100

        window.on_position_changed(exit_position)
        window.on_position_changed(1100)

        assert window.active_event_id == "p1100"
    finally:
        _close_window(app, window)


def test_continue_fallback_resumes_when_position_changed_does_not_confirm(monkeypatch) -> None:
    app = QApplication.instance() or QApplication(["test-temporal-continue-fallback"])
    window = EditorWindow()
    callbacks: list[callable] = []
    play_calls: list[bool] = []
    set_positions: list[int] = []
    window.duration_ms = 5000
    window.timeline.setRange(0, 5000)
    window.pauses = [PausePoint("p1000", 1000, [Hotspot("h1000", message_text="primera")])]
    window.timeline.set_pauses(window.pauses, None)
    try:
        monkeypatch.setattr(hotspot_editor.QTimer, "singleShot", lambda _ms, callback: callbacks.append(callback))
        monkeypatch.setattr(window.player, "setPosition", lambda value: set_positions.append(int(value)))
        monkeypatch.setattr(window.player, "play", lambda: play_calls.append(True))

        window.preview_mode = True
        window.active_event_id = "p1000"
        window.playback_controller.begin_interaction(1000)

        window.continue_from_pause()

        exit_position = set_positions[-1]
        assert window.playback_controller.pending_continue_position_ms == exit_position
        assert window.playback_controller.mode is PlaybackMode.SEEKING
        assert play_calls == []

        callbacks.pop(0)()

        assert window.playback_controller.pending_continue_position_ms is None
        assert window.playback_controller.mode is PlaybackMode.PLAYING
        assert window.playback_controller.previous_ms == exit_position
        assert play_calls == [True]

        window.resume_continue_if_still_pending(exit_position, window.current_video().video_id)

        assert play_calls == [True]
    finally:
        _close_window(app, window)


def test_late_position_changed_does_not_rebound_manual_seek_target() -> None:
    app = QApplication.instance() or QApplication(["test-temporal-manual-seek-target"])
    window = EditorWindow()
    window.duration_ms = 5000
    window.timeline.setRange(0, 5000)
    try:
        window.timeline.setValue(2100)
        window.finish_slider_seek()

        assert window._manual_seek_target_ms == 2100
        assert window.timeline.value() == 2100

        window.on_position_changed(2000)

        assert window.timeline.value() == 2100
        assert window._manual_seek_target_ms == 2100

        window.on_position_changed(2090)

        assert window._manual_seek_target_ms is None

        window.on_position_changed(2200)

        assert window.timeline.value() == 2200
    finally:
        _close_window(app, window)
