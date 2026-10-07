from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QToolButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import Hotspot, PausePoint, SupportItem, VideoEntry  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-pause-at-zero"])


def _support_texts(window: EditorWindow) -> list[str]:
    texts: list[str] = []
    for index in range(window.support_buttons_layout.count()):
        widget = window.support_buttons_layout.itemAt(index).widget()
        if widget is not None:
            texts.extend(button.text() for button in widget.findChildren(QToolButton))
    return texts


def _window_with_pause(pause: PausePoint, monkeypatch) -> EditorWindow:
    window = EditorWindow(auto_show=False)
    monkeypatch.setattr(window, "resolve_pending_segment_changes", lambda: True)
    window.pauses = [pause]
    window.current_video().pauses = window.pauses
    window.duration_ms = 5_000
    window.timeline.setRange(0, 5_000)
    monkeypatch.setattr(window.player, "setPosition", lambda _value: None)
    return window


def test_entering_user_mode_automatically_presents_zero_pause_hotspot(monkeypatch) -> None:
    _app()
    window = _window_with_pause(
        PausePoint("p0", 0, [Hotspot("h0", message_text="Inicio")]),
        monkeypatch,
    )
    try:
        window.preview_mode = True
        window.start_preview_pass()

        assert window.active_event_id == "p0"
        assert window.selected_event_id is None
        assert set(window.items) == {"h0"}
        assert window.continue_btn.isEnabled()
    finally:
        window.close()


def test_entering_user_mode_presents_support_only_zero_pause(monkeypatch) -> None:
    _app()
    support = SupportItem("support_1", "Apoyo 1", "Ayuda", visible=True, position=0)
    window = _window_with_pause(PausePoint("p0", 0, [], [support]), monkeypatch)
    try:
        window.preview_mode = True
        window.start_preview_pass()

        assert window.active_event_id == "p0"
        assert window.items == {}
        assert _support_texts(window) == ["Ayuda"]
        assert window.continue_btn.isEnabled()
    finally:
        window.close()


def test_entering_user_mode_loads_hotspot_and_support_at_zero(monkeypatch) -> None:
    _app()
    pause = PausePoint(
        "p0",
        0,
        [Hotspot("h0", message_text="Inicio")],
        [SupportItem("support_1", "Apoyo 1", "Ayuda", visible=True, position=0)],
    )
    window = _window_with_pause(pause, monkeypatch)
    try:
        window.preview_mode = True
        window.start_preview_pass()

        assert window.active_event_id == "p0"
        assert set(window.items) == {"h0"}
        assert _support_texts(window) == ["Ayuda"]
    finally:
        window.close()


def test_later_pause_still_activates_only_when_crossed(monkeypatch) -> None:
    _app()
    window = _window_with_pause(
        PausePoint("later", 1_000, [Hotspot("h1", message_text="Después")]),
        monkeypatch,
    )
    try:
        window.preview_mode = True
        window.start_preview_pass()
        assert window.active_event_id is None

        window.playback_controller.start_playback(0, user_mode=True)
        window.on_position_changed(1_000)
        assert window.active_event_id == "later"
        assert set(window.items) == {"h1"}
    finally:
        window.close()


def test_go_to_start_and_stop_rearm_and_present_zero_pause(monkeypatch) -> None:
    _app()
    window = _window_with_pause(
        PausePoint("p0", 0, [Hotspot("h0", message_text="Inicio")]),
        monkeypatch,
    )
    monkeypatch.setattr(window.player, "position", lambda: 2_000)
    try:
        window.preview_mode = True
        window.start_preview_pass()
        window.set_pause_state(0, "consumed_for_current_pass")
        window.clear_active_interaction()

        window.go_to_start()
        assert window.active_event_id == "p0"
        assert set(window.items) == {"h0"}

        window.set_pause_state(0, "consumed_for_current_pass")
        window.clear_active_interaction()
        window.stop_video()
        assert window.active_event_id == "p0"
        assert set(window.items) == {"h0"}
    finally:
        window.close()


@pytest.mark.parametrize(
    ("start", "hotspots", "supports", "expected_items", "expected_supports"),
    [
        (15_000, [Hotspot("h15", message_text="Inicio")], [], {"h15"}, []),
        (
            7_321,
            [],
            [SupportItem("support_1", "Apoyo 1", "Ayuda", visible=True, position=0)],
            set(),
            ["Ayuda"],
        ),
        (
            9_876,
            [Hotspot("h9", message_text="Inicio")],
            [SupportItem("support_1", "Apoyo 1", "Juntos", visible=True, position=0)],
            {"h9"},
            ["Juntos"],
        ),
    ],
)
def test_effective_segment_start_is_presented_automatically(
    monkeypatch, start, hotspots, supports, expected_items, expected_supports
) -> None:
    _app()
    pause = PausePoint(f"p{start}", start, hotspots, supports)
    window = _window_with_pause(pause, monkeypatch)
    try:
        window.current_video().start_time = start
        window.current_video().end_time = start + 4_000
        window.load_segment_draft()
        window.duration_ms = start + 5_000
        window.preview_mode = True

        window.start_preview_pass()

        assert window.effective_start_time() == start
        assert window.playback_controller.previous_ms == start
        assert window.active_event_id == pause.pause_id
        assert set(window.items) == expected_items
        assert _support_texts(window) == expected_supports
        assert window.continue_btn.isEnabled()
    finally:
        window.close()


@pytest.mark.parametrize("action", ["go_to_start", "stop_video"])
def test_segment_start_is_rearmed_and_presented_by_transport(monkeypatch, action) -> None:
    _app()
    start = 15_000
    pause = PausePoint("p15", start, [Hotspot("h15", message_text="Inicio")])
    window = _window_with_pause(pause, monkeypatch)
    monkeypatch.setattr(window.player, "position", lambda: 18_000)
    try:
        window.current_video().start_time = start
        window.current_video().end_time = 20_000
        window.load_segment_draft()
        window.duration_ms = 20_800
        window.preview_mode = True
        window.start_preview_pass()
        window.set_pause_state(start, "consumed_for_current_pass")
        window.clear_active_interaction()

        getattr(window, action)()

        assert window.active_event_id == "p15"
        assert set(window.items) == {"h15"}
    finally:
        window.close()


def test_play_while_armed_at_segment_start_uses_user_event_activation(monkeypatch) -> None:
    _app()
    start = 15_000
    pause = PausePoint("p15", start, [Hotspot("h15", message_text="Inicio")])
    window = _window_with_pause(pause, monkeypatch)
    try:
        window.current_video().start_time = start
        window.current_video().end_time = 20_000
        window.load_segment_draft()
        window.duration_ms = 20_800
        window.preview_mode = True
        window.pause_states = {start: "armed"}
        monkeypatch.setattr(window.player, "position", lambda: start)
        monkeypatch.setattr(
            window.player,
            "playbackState",
            lambda: QMediaPlayer.PlaybackState.StoppedState,
        )

        window.toggle_play()

        assert window.active_event_id == "p15"
        assert set(window.items) == {"h15"}
        assert window.continue_btn.isEnabled()
    finally:
        window.close()


def test_video_change_in_user_mode_presents_new_video_effective_start(monkeypatch) -> None:
    _app()
    start = 15_000
    target_pause = PausePoint("target", start, [Hotspot("target-h", message_text="Destino")])
    window = EditorWindow(auto_show=False)
    try:
        monkeypatch.setattr(window, "resolve_pending_segment_changes", lambda: True)
        window.videos = [
            VideoEntry("v1", "Uno", "", []),
            VideoEntry("v2", "Dos", "", [target_pause], start, 20_000),
        ]
        window.current_video_index = 0
        window.pauses = []
        window.preview_mode = True
        monkeypatch.setattr(window.player, "setPosition", lambda _value: None)
        monkeypatch.setattr(window.player, "setSource", lambda _value: None)

        window.select_video(1)

        assert window.effective_start_time() == start
        assert window.active_event_id == "target"
        assert set(window.items) == {"target-h"}
    finally:
        window.close()
