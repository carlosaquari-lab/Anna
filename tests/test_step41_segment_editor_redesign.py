from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from hotspot_editor import EditorWindow
from hotspot_model import PausePoint, VideoEntry


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_window(duration: int = 10_000) -> EditorWindow:
    app()
    window = EditorWindow(auto_show=False)
    window.duration_ms = duration
    window.load_segment_draft()
    window.update_segment_controls()
    return window


def close_clean(window: EditorWindow) -> None:
    window.discard_segment_draft()
    window.close()


def test_natural_values_and_initial_button_states() -> None:
    window = make_window()
    try:
        assert window.segment_start_value.text() == "00:00:00.000"
        assert window.segment_end_value.text() == "00:00:10.000"
        assert window.reset_segment_btn.isEnabled()
        assert not window.save_segment_btn.isEnabled()
        assert not window.support_panel.isAncestorOf(window.segment_controls)
    finally:
        close_clean(window)


def test_unknown_duration_has_neutral_end_and_disables_unverifiable_actions() -> None:
    window = make_window(0)
    try:
        assert window.segment_end_value.text() == "--:--:--.---"
        assert not window.reset_segment_btn.isEnabled()
        assert not window.save_segment_btn.isEnabled()
    finally:
        close_clean(window)


def test_valid_manual_operations_change_only_draft_until_explicit_apply(monkeypatch) -> None:
    window = make_window()
    try:
        window.segment_start_value.setText("00:00:02.000")
        assert window.commit_segment_text(True)
        window.segment_end_value.setText("00:00:08.000")
        assert window.commit_segment_text(False)
        assert (window.draft_start, window.draft_end) == (2_000, 8_000)
        assert (window.current_video().start_time, window.current_video().end_time) == (None, None)
        assert window.reset_segment_btn.isEnabled()
        assert window.save_segment_btn.isEnabled()
    finally:
        close_clean(window)


def test_reset_immediately_restores_full_video() -> None:
    window = make_window()
    try:
        window.current_video().start_time = 1_000
        window.current_video().end_time = 9_000
        window.load_segment_draft()
        window.reset_segment()
        assert (window.draft_start, window.draft_end) == (None, None)
        assert (window.current_video().start_time, window.current_video().end_time) == (None, None)
    finally:
        close_clean(window)


def test_save_copies_draft_marks_history_but_never_writes_project(monkeypatch) -> None:
    window = make_window()
    events: list[str] = []
    disk_saves: list[bool] = []
    try:
        window.draft_start, window.draft_end = 2_000, 8_000
        window.update_segment_controls()
        monkeypatch.setattr(window, "push_history", events.append)
        monkeypatch.setattr(window, "save_json", lambda *_args, **_kwargs: disk_saves.append(True))
        assert window.save_segment()
        assert (window.current_video().start_time, window.current_video().end_time) == (2_000, 8_000)
        assert events == ["video_segment_saved"]
        assert disk_saves == []
        assert not window.segment_has_pending_changes()
        assert not window.save_segment_btn.isEnabled()
    finally:
        close_clean(window)


@pytest.mark.parametrize("position", [1_000, 8_000, 9_000])
def test_save_repositions_outside_head_to_start_without_false_completion(monkeypatch, position) -> None:
    window = make_window()
    positions: list[int] = []
    research_events: list[str] = []
    try:
        window.draft_start, window.draft_end = 2_000, 8_000
        window.update_segment_controls()
        monkeypatch.setattr(window.player, "position", lambda: position)
        monkeypatch.setattr(window.player, "setPosition", lambda value: positions.append(int(value)))
        monkeypatch.setattr(window.research, "record_event", lambda event_type, **_payload: research_events.append(event_type))
        assert window.save_segment()
        assert positions[-1] == 2_000
        assert "video_completed" not in research_events
    finally:
        close_clean(window)


def test_save_keeps_head_when_already_inside(monkeypatch) -> None:
    window = make_window()
    positions: list[int] = []
    try:
        window.draft_start, window.draft_end = 2_000, 8_000
        window.update_segment_controls()
        monkeypatch.setattr(window.player, "position", lambda: 5_000)
        monkeypatch.setattr(window.player, "setPosition", lambda value: positions.append(int(value)))
        assert window.save_segment()
        assert positions == []
    finally:
        close_clean(window)


def test_pending_decisions_save_discard_and_cancel() -> None:
    window = make_window()
    try:
        window.draft_start = 2_000
        assert window.resolve_pending_segment_changes("cancel") is False
        assert window.draft_start == 2_000 and window.current_video().start_time is None
        assert window.resolve_pending_segment_changes("discard") is True
        assert window.draft_start is None
        window.draft_start = 3_000
        window.update_segment_controls()
        assert window.resolve_pending_segment_changes("save") is True
        assert window.current_video().start_time == 3_000
    finally:
        close_clean(window)


def test_video_change_cancel_keeps_current_video_and_draft(monkeypatch) -> None:
    window = make_window()
    try:
        window.videos.append(VideoEntry("v2", "Dos", "", [], None, 9_000))
        window.draft_start = 2_000
        monkeypatch.setattr(window, "resolve_pending_segment_changes", lambda: False)
        window.select_video(1)
        assert window.current_video_index == 0
        assert window.draft_start == 2_000
    finally:
        close_clean(window)


def test_each_video_loads_its_saved_limits_without_visual_reuse(monkeypatch) -> None:
    window = make_window()
    try:
        window.videos = [
            VideoEntry("v1", "Uno", "", [], None, None),
            VideoEntry("v2", "Dos", "", [], 2_000, None),
            VideoEntry("v3", "Tres", "", [], None, 8_000),
            VideoEntry("v4", "Cuatro", "", [], 3_000, 7_000),
        ]
        window.current_video_index = 0
        window.pauses = window.videos[0].pauses
        window.load_segment_draft()
        monkeypatch.setattr(window, "resolved_video_path", lambda _video: Path("missing.mp4"))
        expected = [(None, None), (2_000, None), (None, 8_000), (3_000, 7_000)]
        for index, limits in enumerate(expected):
            window.select_video(index)
            window.duration_ms = 10_000
            window.update_segment_controls()
            assert (window.draft_start, window.draft_end) == limits
    finally:
        close_clean(window)


def test_user_mode_hides_segment_block_and_cancelled_transition_keeps_professional(monkeypatch) -> None:
    window = make_window()
    try:
        window.draft_start = 2_000
        window.preview_btn.setChecked(True)
        monkeypatch.setattr(window, "resolve_pending_segment_changes", lambda: False)
        window.toggle_preview_mode()
        assert not window.preview_mode
        assert not window.preview_btn.isChecked()
        window.discard_segment_draft()
        monkeypatch.setattr(window, "resolve_pending_segment_changes", lambda: True)
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        assert window.preview_mode
        assert window.segment_controls.isHidden()
    finally:
        window.preview_mode = False
        close_clean(window)


def test_pause_times_and_contents_survive_segment_save() -> None:
    window = make_window()
    try:
        pauses = [PausePoint("before", 1_000), PausePoint("start", 2_000), PausePoint("end", 8_000)]
        window.pauses = pauses
        window.current_video().pauses = pauses
        original = [(pause.pause_id, pause.time_ms, pause.hotspots, pause.supports) for pause in pauses]
        window.draft_start, window.draft_end = 2_000, 8_000
        window.update_segment_controls()
        assert window.save_segment()
        assert [(pause.pause_id, pause.time_ms, pause.hotspots, pause.supports) for pause in pauses] == original
        assert [pause.pause_id for pause in window.active_pauses()] == ["start"]
    finally:
        close_clean(window)


def test_new_video_has_no_explicit_limits() -> None:
    video = VideoEntry("new", "Nuevo", "new.mp4")
    assert video.start_time is None and video.end_time is None
