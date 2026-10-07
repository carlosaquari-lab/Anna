from dataclasses import dataclass

from temporal_event_engine import (
    POST_EVENT_MARGIN_MS,
    PlaybackMode,
    continue_position,
    find_crossed_pause_event,
)


@dataclass(frozen=True)
class Event:
    event_id: str
    time_ms: int


EVENTS = [
    Event("a", 10_000),
    Event("b", 25_000),
    Event("c", 40_000),
]


def test_crossing_during_playback_activates_first_event():
    assert find_crossed_pause_event(9_972, 10_018, EVENTS, PlaybackMode.PLAYING) == EVENTS[0]


def test_exact_previous_position_does_not_reactivate_same_event():
    assert find_crossed_pause_event(10_000, 10_040, EVENTS, PlaybackMode.PLAYING) is None


def test_seek_forward_does_not_activate_event():
    assert find_crossed_pause_event(5_000, 20_000, EVENTS, PlaybackMode.SEEKING) is None


def test_seek_backward_does_not_activate_event():
    assert find_crossed_pause_event(20_000, 5_000, EVENTS, PlaybackMode.SEEKING) is None


def test_backward_playback_update_does_not_activate_event():
    assert find_crossed_pause_event(20_000, 5_000, EVENTS, PlaybackMode.PLAYING) is None


def test_stopped_and_interaction_paused_do_not_activate_events():
    assert find_crossed_pause_event(9_000, 11_000, EVENTS, PlaybackMode.STOPPED) is None
    assert find_crossed_pause_event(9_000, 11_000, EVENTS, PlaybackMode.INTERACTION_PAUSED) is None


def test_large_update_returns_earliest_crossed_event():
    assert find_crossed_pause_event(9_000, 30_000, EVENTS, PlaybackMode.PLAYING) == EVENTS[0]


def test_repeating_after_returning_before_event_needs_no_rearm_state():
    first = find_crossed_pause_event(9_000, 10_100, EVENTS, PlaybackMode.PLAYING)
    repeated = find_crossed_pause_event(8_000, 10_050, EVENTS, PlaybackMode.PLAYING)
    assert first == EVENTS[0]
    assert repeated == EVENTS[0]


def test_event_at_zero_requires_playback_to_start_before_zero_and_is_not_triggered_normally():
    zero_event = [Event("zero", 0)]
    assert find_crossed_pause_event(0, 20, zero_event, PlaybackMode.PLAYING) is None


def test_continue_uses_fixed_200_ms_margin():
    assert POST_EVENT_MARGIN_MS == 200
    assert continue_position(10_000) == 10_200


def test_continue_is_clamped_before_video_end():
    assert continue_position(9_950, duration_ms=10_000) == 9_999
