
from __future__ import annotations
from dataclasses import dataclass, field
from playback_controller import PlaybackController
from temporal_event_engine import PlaybackMode

@dataclass
class Event:
    time_ms: int
    event_id: str
    hotspots: list[str] = field(default_factory=list)
    supports: list[str] = field(default_factory=list)

class FakeMediaPlayer:
    def __init__(self):
        self.position_ms = 0
        self.playing = False
    def play(self): self.playing = True
    def pause(self): self.playing = False
    def set_position(self, value): self.position_ms = int(value)

class FakeView:
    def __init__(self):
        self.active_event_id = None
        self.hotspots = []
        self.supports = []
        self.continue_enabled = False
    def show(self, event):
        self.active_event_id = event.event_id
        self.hotspots = list(event.hotspots)
        self.supports = list(event.supports)
        self.continue_enabled = True
    def clear(self):
        self.active_event_id = None
        self.hotspots = []
        self.supports = []
        self.continue_enabled = False

class Harness:
    def __init__(self, events, duration_ms=60000):
        self.events = events
        self.duration_ms = duration_ms
        self.controller = PlaybackController()
        self.player = FakeMediaPlayer()
        self.view = FakeView()
        self.active_event = None
    def play_from(self, position):
        self.player.set_position(position)
        self.controller.start_playback(position, user_mode=True)
        self.player.play()
    def report(self, position):
        self.player.position_ms = int(position)
        decision = self.controller.observe_position(position, self.events, user_mode=True)
        if decision.continue_seek_completed:
            self.player.play()
            return
        if decision.crossed_event is not None:
            event = decision.crossed_event
            self.active_event = event
            self.controller.begin_interaction(event.time_ms)
            self.player.pause()
            self.player.set_position(event.time_ms)
            self.view.show(event)
    def continue_event(self):
        target = self.controller.begin_continue(self.active_event.time_ms, self.duration_ms)
        self.active_event = None
        self.view.clear()
        self.player.set_position(target)
        return target
    def seek(self, target):
        self.controller.begin_seek(self.player.position_ms)
        self.active_event = None
        self.view.clear()
        self.player.pause()
        self.player.set_position(target)
        self.controller.finish_seek(target)
    def home(self):
        self.active_event = None
        self.view.clear()
        self.controller.reset(0)
        self.player.pause()
        self.player.set_position(0)

def event(time_ms=10000, event_id="event-1"):
    return Event(time_ms, event_id, ["hotspot-a"], ["support-visible"])

def test_full_pause_continue_flow():
    h = Harness([event()])
    h.play_from(9000)
    h.report(10050)
    assert h.controller.mode is PlaybackMode.INTERACTION_PAUSED
    assert h.player.position_ms == 10000
    assert h.view.active_event_id == "event-1"
    assert h.view.hotspots == ["hotspot-a"]
    assert h.view.supports == ["support-visible"]
    target = h.continue_event()
    assert target == 10200
    assert h.view.active_event_id is None
    h.report(target)
    assert h.controller.mode is PlaybackMode.PLAYING
    assert h.player.playing

def test_repeat_after_seek_backward():
    h = Harness([event()])
    h.play_from(9000); h.report(10050)
    target = h.continue_event(); h.report(target)
    h.seek(5000); h.play_from(5000); h.report(10020)
    assert h.view.active_event_id == "event-1"

def test_seek_over_event_does_not_activate():
    h = Harness([event()])
    h.play_from(5000)
    h.seek(15000)
    assert h.controller.mode is PlaybackMode.STOPPED
    assert h.view.active_event_id is None

def test_two_events_activate_in_order():
    h = Harness([event(10000, "event-1"), event(12000, "event-2")])
    h.play_from(9000); h.report(12500)
    assert h.view.active_event_id == "event-1"
    target = h.continue_event(); h.report(target); h.report(12050)
    assert h.view.active_event_id == "event-2"

def test_home_clears_everything():
    h = Harness([event()])
    h.play_from(9000); h.report(10050); h.home()
    assert h.controller.mode is PlaybackMode.STOPPED
    assert h.controller.previous_ms == 0
    assert h.player.position_ms == 0
    assert h.view.active_event_id is None
    assert h.view.hotspots == []
    assert h.view.supports == []
