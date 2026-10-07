from dataclasses import dataclass

from playback_controller import PlaybackController
from temporal_event_engine import PlaybackMode


@dataclass
class Event:
    time_ms: int


def test_controller_detects_event_during_user_playback():
    controller = PlaybackController()
    controller.start_playback(9000, user_mode=True)
    decision = controller.observe_position(10050, [Event(10000)], user_mode=True)
    assert decision.crossed_event.time_ms == 10000


def test_controller_does_not_detect_event_while_seeking():
    controller = PlaybackController()
    controller.begin_seek(9000)
    decision = controller.observe_position(11000, [Event(10000)], user_mode=True)
    assert decision.crossed_event is None


def test_controller_repeats_event_after_returning_before_it():
    controller = PlaybackController()
    controller.start_playback(9000, user_mode=True)
    assert controller.observe_position(10050, [Event(10000)], user_mode=True).crossed_event

    controller.begin_interaction(10000)
    controller.begin_continue(10000, 20000)
    controller.observe_position(10200, [Event(10000)], user_mode=True)

    controller.begin_seek(5000)
    controller.finish_seek(5000)
    controller.start_playback(5000, user_mode=True)
    decision = controller.observe_position(10020, [Event(10000)], user_mode=True)
    assert decision.crossed_event.time_ms == 10000


def test_continue_uses_200_ms_margin_and_waits_for_target():
    controller = PlaybackController()
    target = controller.begin_continue(10000, 20000)
    assert target == 10200
    assert controller.mode is PlaybackMode.SEEKING

    decision = controller.observe_position(10120, [], user_mode=True)
    assert not decision.continue_seek_completed
    decision = controller.observe_position(10200, [], user_mode=True)
    assert decision.continue_seek_completed
    assert controller.mode is PlaybackMode.PLAYING
