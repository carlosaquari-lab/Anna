from hotspot_model import Hotspot, PausePoint, SupportItem, VideoEntry, default_project, serialize_project, videos_from_project_payload
from playback_controller import PlaybackController


def test_exactly_500_ms_apart_pause_events_are_both_reachable():
    events = [PausePoint("first", 2000, [Hotspot("h1")]), PausePoint("second", 2500, [Hotspot("h2")])]
    controller = PlaybackController()
    controller.start_playback(1000, user_mode=True)
    first = controller.observe_position(2010, events, user_mode=True)
    assert first.crossed_event.pause_id == "first"
    controller.begin_interaction(2000)
    target = controller.begin_continue(2000, 5000)
    controller.observe_position(target, events, user_mode=True)
    second = controller.observe_position(2510, events, user_mode=True)
    assert second.crossed_event.pause_id == "second"


def test_multi_video_pause_event_support_isolation_round_trip():
    videos = [
        VideoEntry("v1", "Uno", "a.mp4", [PausePoint("e1", 1000, [Hotspot("h1")], [SupportItem("support_1", text="uno", visible=True)])]),
        VideoEntry("v2", "Dos", "b.mp4", [PausePoint("e2", 2000, [Hotspot("h2")], [SupportItem("support_1", text="dos", visible=False)])]),
    ]
    payload = serialize_project(default_project(), videos[0].pauses, 3000, videos, 1)
    restored = videos_from_project_payload(payload)
    assert restored[0].pauses[0].supports[0].text == "uno"
    assert restored[1].pauses[0].supports[0].text == "dos"
    assert restored[0].pauses[0].pause_id == "e1"
    assert restored[1].pauses[0].pause_id == "e2"
