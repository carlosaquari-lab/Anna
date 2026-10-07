import inspect

from PySide6.QtWidgets import QApplication, QPushButton

from hotspot_editor import EditorWindow, format_time, parse_segment_time


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_window(duration: int = 10_000) -> EditorWindow:
    app()
    window = EditorWindow(auto_show=False)
    window.duration_ms = duration
    window.load_segment_draft()
    window.update_segment_controls()
    return window


def test_segment_parser_is_strict_and_supports_unlimited_hours() -> None:
    assert parse_segment_time("00:00:01.250") == 1_250
    assert parse_segment_time("27:03:04.005") == 97_384_005
    assert parse_segment_time("00:60:00.000") is None
    assert parse_segment_time("00:00:60.000") is None
    assert parse_segment_time("00:00:01.25") is None
    assert "QTime" not in inspect.getsource(parse_segment_time)


def test_invalid_manual_text_keeps_last_valid_draft(monkeypatch) -> None:
    window = make_window()
    messages = []
    try:
        window.draft_start = 2_000
        window.update_segment_controls()
        window.segment_start_value.setText("00:61:00.000")
        monkeypatch.setattr(window, "show_segment_error", messages.append)
        assert not window.commit_segment_text(True)
        assert window.draft_start == 2_000
        assert messages
    finally:
        window.discard_segment_draft()
        window.close()


def test_manual_edit_changes_only_the_draft(monkeypatch) -> None:
    window = make_window()
    try:
        window.segment_start_value.setText("00:00:02.000")
        assert window.commit_segment_text(True)
        assert window.draft_start == 2_000
        assert window.current_video().start_time is None
        assert window.effective_start_time() == 0
        assert window.timeline.segment_start_ms == 0

    finally:
        window.discard_segment_draft()
        window.close()


def test_natural_and_normalized_limits_have_no_false_dirty_state() -> None:
    window = make_window()
    try:
        window.draft_start = 0
        window.draft_end = window.duration_ms
        assert not window.segment_has_pending_changes()
        window.update_segment_controls()
        assert window.save_segment()
        assert (window.current_video().start_time, window.current_video().end_time) == (None, None)

        window.draft_start, window.draft_end = 2_000, 8_000
        window.reset_segment()
        assert (window.draft_start, window.draft_end) == (None, None)
    finally:
        window.discard_segment_draft()
        window.close()


def test_interface_has_one_reset_and_apply_without_legacy_labels() -> None:
    window = make_window()
    try:
        buttons = window.segment_controls.findChildren(QPushButton)
        labels = [button.text() for button in buttons]
        assert labels.count("Reset") == 1
        assert "Apply" in labels
        assert "Use current" not in labels
        assert "Natural" not in labels
        assert "Clear" not in labels
        assert "Save segment" not in labels
    finally:
        window.close()


def test_reset_of_delimited_segment_applies_full_video_immediately() -> None:
    window = make_window()
    try:
        video = window.current_video()
        video.start_time, video.end_time = 2_000, 8_000
        window.load_segment_draft()
        window.update_segment_controls()
        window.reset_segment()
        assert (window.draft_start, window.draft_end) == (None, None)
        assert (video.start_time, video.end_time) == (None, None)
        assert not window.save_segment_btn.isEnabled()
        assert window.segment_start_value.text() == "00:00:00.000"
        assert window.segment_end_value.text() == "00:00:10.000"
    finally:
        window.discard_segment_draft()
        window.close()


def test_reset_creates_one_history_entry_only_when_applied_segment_exists(monkeypatch) -> None:
    window = make_window()
    events = []
    try:
        monkeypatch.setattr(window, "push_history", events.append)
        window.reset_segment()
        assert events == []

        video = window.current_video()
        video.start_time, video.end_time = 2_000, 8_000
        window.load_segment_draft()
        window.update_segment_controls()
        window.reset_segment()
        assert events == ["video_segment_reset"]
        assert (video.start_time, video.end_time) == (None, None)
        assert window.timeline.segment_start_ms == 0
        assert window.timeline.segment_end_ms is None
    finally:
        window.close()


def test_reset_returns_player_counter_and_playhead_to_physical_start(monkeypatch) -> None:
    window = make_window()
    positions = []
    try:
        video = window.current_video()
        video.start_time, video.end_time = 5_000, 8_000
        window.load_segment_draft()
        window.update_segment_controls()
        window.timeline.setValue(5_000)
        window.time_label.setText("00:00:05.000 / 00:00:10.000")
        monkeypatch.setattr(window.player, "setPosition", lambda value: positions.append(int(value)))

        window.reset_segment()

        assert positions[-1] == 0
        assert window.playback_controller.previous_ms == 0
        assert window.timeline.value() == 0
        assert window.time_label.text() == "00:00:00.000 / 00:00:10.000"
        assert window.segment_start_value.text() == "00:00:00.000"
        assert window.segment_end_value.text() == "00:00:10.000"
        assert all(state == "armed" for state in window.pause_states.values())
    finally:
        window.close()


def test_save_rejects_invalid_intervals_without_changing_model(monkeypatch) -> None:
    window = make_window()
    try:
        monkeypatch.setattr(window, "show_segment_error", lambda _message: None)
        for start, end in ((5_000, 5_000), (6_000, 5_000), (10_000, 10_000), (0, 10_001)):
            window.segment_start_value.setText(format_time(start))
            window.segment_end_value.setText(format_time(end))
            assert not window.save_segment()
            assert (window.current_video().start_time, window.current_video().end_time) == (None, None)
    finally:
        window.discard_segment_draft()
        window.close()


def test_save_commits_once_and_unknown_duration_disables_whole_editor(monkeypatch) -> None:
    window = make_window()
    events = []
    try:
        window.segment_start_value.setText("00:00:02.000")
        window.segment_end_value.setText("00:00:08.000")
        monkeypatch.setattr(window, "push_history", events.append)
        assert window.save_segment()
        assert (window.current_video().start_time, window.current_video().end_time) == (2_000, 8_000)
        assert events == ["video_segment_saved"]
        assert window.timeline.segment_start_ms == 2_000
        assert window.timeline.segment_end_ms == 8_000

        window.duration_ms = 0
        window.update_segment_controls()
        for widget in (
            window.segment_start_value, window.segment_end_value,
            window.reset_segment_btn, window.save_segment_btn,
        ):
            assert not widget.isEnabled()
    finally:
        window.discard_segment_draft()
        window.close()
