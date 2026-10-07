import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer

from hotspot_editor import EditorWindow
from hotspot_model import PausePoint, VideoEntry, default_project, serialize_project, videos_from_project_payload
from playback_controller import PlaybackController
from research_session import ResearchSessionManager


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_optional_segment_fields_round_trip_and_old_payload_stays_unchanged() -> None:
    bounded = VideoEntry("v1", "Uno", "uno.mp4", [], 1_000, 8_000)
    payload = serialize_project(default_project(), [], 10_000, [bounded], 0)
    assert payload["videos"][0]["start_time"] == 1_000
    assert payload["videos"][0]["end_time"] == 8_000
    restored = videos_from_project_payload(payload)[0]
    assert (restored.start_time, restored.end_time) == (1_000, 8_000)

    old = default_project()
    legacy = videos_from_project_payload(old)[0]
    assert legacy.start_time is None and legacy.end_time is None
    assert "start_time" not in legacy.to_dict() and "end_time" not in legacy.to_dict()


def test_multi_video_round_trip_preserves_distinct_segments_and_content() -> None:
    first_pause = PausePoint("p1", 2_000)
    second_pause = PausePoint("p2", 9_000)
    videos = [
        VideoEntry("v1", "Uno", "uno.mp4", [first_pause], 1_000, 5_000),
        VideoEntry("v2", "Dos", "dos.mp4", [second_pause], 7_000, 12_000),
    ]
    restored = videos_from_project_payload(serialize_project(default_project(), videos[0].pauses, 20_000, videos, 1))
    assert [(v.start_time, v.end_time) for v in restored] == [(1_000, 5_000), (7_000, 12_000)]
    assert [v.pauses[0].pause_id for v in restored] == ["p1", "p2"]


@pytest.mark.parametrize(
    "start,end,duration",
    [(-1, None, None), (None, -1, None), (5_000, 5_000, None), (6_000, 5_000, None), (10_000, None, 10_000), (None, 10_001, 10_000)],
)
def test_invalid_segments_are_rejected(start, end, duration) -> None:
    with pytest.raises(ValueError):
        VideoEntry("v", "Vídeo", "v.mp4", [], start, end).validate_bounds(duration)


def test_outside_pauses_are_inactive_but_never_deleted_and_recover_on_expansion() -> None:
    pauses = [PausePoint("before", 1_000), PausePoint("start", 2_000), PausePoint("inside", 2_001), PausePoint("end", 5_000)]
    video = VideoEntry("v", "Vídeo", "v.mp4", pauses, 2_000, 5_000)
    assert [p.pause_id for p in pauses if video.pause_is_active(p, 10_000)] == ["start", "inside"]
    assert [p.pause_id for p in video.pauses] == ["before", "start", "inside", "end"]
    video.start_time, video.end_time = 0, 6_000
    assert [p.pause_id for p in pauses if video.pause_is_active(p, 10_000)] == ["before", "start", "inside", "end"]


def test_playback_controller_only_receives_active_pauses_and_crosses_first_inside() -> None:
    video = VideoEntry("v", "Vídeo", "v.mp4", [PausePoint("old", 1_000), PausePoint("inside", 2_001), PausePoint("end", 5_000)], 2_000, 5_000)
    active = [p for p in video.pauses if video.pause_is_active(p, 10_000)]
    controller = PlaybackController()
    controller.start_playback(2_000, user_mode=True)
    decision = controller.observe_position(2_010, active, user_mode=True)
    assert decision.crossed_event.pause_id == "inside"
    assert all(p.pause_id != "end" for p in active)


def test_pause_exactly_at_start_is_presented_when_user_starts_playback(monkeypatch) -> None:
    app()
    window = EditorWindow(auto_show=False)
    activated: list[str] = []
    try:
        pause = PausePoint("at-start", 2_000)
        window.current_video().start_time = 2_000
        window.current_video().end_time = 5_000
        window.load_segment_draft()
        window.duration_ms = 10_000
        window.pauses = [pause]
        window.current_video().pauses = window.pauses
        window.preview_mode = True
        monkeypatch.setattr(window.player, "position", lambda: 2_000)
        monkeypatch.setattr(window.player, "playbackState", lambda: QMediaPlayer.PlaybackState.StoppedState)
        monkeypatch.setattr(window, "pause_at_temporal_event", lambda item: activated.append(item.pause_id))
        window.toggle_play()
        assert activated == ["at-start"]
    finally:
        window.close()


def test_continue_is_clamped_before_effective_end() -> None:
    controller = PlaybackController()
    assert controller.begin_continue(4_950, 5_000) == 4_999


def test_professional_controls_edit_apply_and_reset_segment(monkeypatch) -> None:
    app()
    window = EditorWindow(auto_show=False)
    try:
        window.duration_ms = 10_000
        window.update_segment_controls()
        window.segment_start_value.setText("00:00:02.000")
        window.segment_end_value.setText("00:00:08.000")
        assert window.save_segment() is True
        assert (window.current_video().start_time, window.current_video().end_time) == (2_000, 8_000)
        window.reset_segment()
        assert window.draft_start is None and window.draft_end is None
        assert window.current_video().start_time is None and window.current_video().end_time is None
        window.discard_segment_draft()
    finally:
        window.close()


def test_user_mode_starts_and_stop_home_return_to_effective_start(monkeypatch) -> None:
    app()
    window = EditorWindow(auto_show=False)
    positions: list[int] = []
    try:
        window.current_video().start_time = 3_000
        window.load_segment_draft()
        window.duration_ms = 10_000
        monkeypatch.setattr(window.player, "setPosition", lambda value: positions.append(int(value)))
        monkeypatch.setattr(window.player, "position", lambda: 7_000)
        window.start_preview_pass()
        window.stop_video()
        window.go_to_start()
        assert positions[-3:] == [3_000, 3_000, 3_000]
        assert window.playback_controller.previous_ms == 3_000
    finally:
        window.close()


def test_video_change_loads_its_own_start_and_logs_absolute_target(monkeypatch) -> None:
    app()
    window = EditorWindow(auto_show=False)
    positions: list[int] = []
    try:
        window.videos = [VideoEntry("v1", "Uno", "", [], 1_000, 4_000), VideoEntry("v2", "Dos", "", [], 6_000, 9_000)]
        window.current_video_index = 0
        window.pauses = window.videos[0].pauses
        window.load_segment_draft()
        monkeypatch.setattr(window.player, "setPosition", lambda value: positions.append(int(value)))
        monkeypatch.setattr(window, "resolved_video_path", lambda _video: Path("missing.mp4"))
        window.select_video(1)
        assert window.effective_start_time() == 6_000
        assert positions[-1] == 6_000
    finally:
        window.close()


def test_crossing_segment_end_completes_once_and_does_not_activate_end_pause(monkeypatch, tmp_path) -> None:
    app()
    window = EditorWindow(auto_show=False)
    recorded: list[str] = []
    activated: list[str] = []
    try:
        window.current_video().start_time = 1_000
        window.current_video().end_time = 5_000
        window.load_segment_draft()
        window.duration_ms = 10_000
        window.pauses = [PausePoint("end", 5_000)]
        window.current_video().pauses = window.pauses
        monkeypatch.setattr(window.research, "record_event", lambda event_type, **_payload: recorded.append(event_type))
        monkeypatch.setattr(window, "pause_at_temporal_event", lambda pause: activated.append(pause.pause_id))
        monkeypatch.setattr(window.player, "setPosition", lambda _value: None)
        window.on_position_changed(5_500)
        window.on_position_changed(5_000)
        assert recorded.count("video_completed") == 1
        assert activated == []
    finally:
        window.close()


def test_research_log_keeps_absolute_positions_and_optional_bounds(tmp_path) -> None:
    manager = ResearchSessionManager(tmp_path)
    manager.elapsed_override_ms = 1_000
    manager.start_session(project_id="p", project_name="P", video_id="v", video_position_ms=3_000, start_time=3_000, end_time=8_000)
    event = manager.events[0]
    assert event["video_position_ms"] == 3_000
    assert event["start_time"] == 3_000 and event["end_time"] == 8_000


def test_sample_project_remains_legacy_compatible() -> None:
    path = Path(__file__).parents[1] / "demo_project" / "washing_hands.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    videos = videos_from_project_payload(payload)
    assert videos and all(video.start_time is None and video.end_time is None for video in videos)
