from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from temporal_event_engine import (
    PlaybackMode,
    continue_position,
    find_crossed_pause_event,
)


class TimedEvent(Protocol):
    time_ms: int


@dataclass(frozen=True)
class PositionDecision:
    previous_ms: int
    current_ms: int
    moved_backward: bool = False
    continue_seek_completed: bool = False
    continue_target_ms: int | None = None
    crossed_event: TimedEvent | None = None


class PlaybackController:
    """Estado y decisiones temporales independientes de Qt y de la interfaz."""

    def __init__(self) -> None:
        self.mode = PlaybackMode.STOPPED
        self.previous_ms = 0
        self.pending_continue_position_ms: int | None = None
        self.seek_start_ms = 0
        self.seeking = False
        self.running = False

    def reset(self, position_ms: int = 0) -> None:
        position_ms = int(position_ms)
        self.mode = PlaybackMode.STOPPED
        self.previous_ms = position_ms
        self.pending_continue_position_ms = None
        self.seek_start_ms = position_ms
        self.seeking = False
        self.running = False

    def start_playback(self, position_ms: int, *, user_mode: bool) -> None:
        self.previous_ms = int(position_ms)
        self.running = bool(user_mode)
        self.mode = PlaybackMode.PLAYING if user_mode else PlaybackMode.STOPPED

    def stop_playback(self, position_ms: int | None = None) -> None:
        if position_ms is not None:
            self.previous_ms = int(position_ms)
        self.mode = PlaybackMode.STOPPED
        self.running = False
        self.pending_continue_position_ms = None

    def begin_seek(self, position_ms: int) -> None:
        position_ms = int(position_ms)
        self.pending_continue_position_ms = None
        self.seeking = True
        self.running = False
        self.mode = PlaybackMode.SEEKING
        self.seek_start_ms = position_ms
        self.previous_ms = position_ms

    def finish_seek(self, position_ms: int) -> None:
        position_ms = int(position_ms)
        self.seeking = False
        self.mode = PlaybackMode.STOPPED
        self.running = False
        self.previous_ms = position_ms

    def begin_interaction(self, event_time_ms: int) -> None:
        event_time_ms = int(event_time_ms)
        self.mode = PlaybackMode.INTERACTION_PAUSED
        self.running = False
        self.previous_ms = event_time_ms

    def begin_continue(self, event_time_ms: int, duration_ms: int | None = None) -> int:
        target = continue_position(int(event_time_ms), duration_ms=duration_ms)
        self.mode = PlaybackMode.SEEKING
        self.running = False
        self.pending_continue_position_ms = target
        return target

    def observe_position(
        self,
        position_ms: int,
        events: Iterable[TimedEvent],
        *,
        user_mode: bool,
    ) -> PositionDecision:
        position_ms = int(position_ms)

        if self.pending_continue_position_ms is not None:
            target = int(self.pending_continue_position_ms)
            completed = abs(position_ms - target) <= 35 or position_ms >= target
            if completed:
                self.pending_continue_position_ms = None
                self.previous_ms = target
                self.mode = PlaybackMode.PLAYING
                self.running = True
            return PositionDecision(
                previous_ms=self.previous_ms,
                current_ms=position_ms,
                continue_seek_completed=completed,
                continue_target_ms=target,
            )

        previous = int(self.previous_ms)
        moved_backward = position_ms < previous
        if moved_backward:
            self.mode = PlaybackMode.STOPPED if user_mode else self.mode

        crossed = None
        if user_mode:
            crossed = find_crossed_pause_event(
                previous,
                position_ms,
                events,
                self.mode,
            )

        if crossed is None:
            self.previous_ms = position_ms

        return PositionDecision(
            previous_ms=previous,
            current_ms=position_ms,
            moved_backward=moved_backward,
            crossed_event=crossed,
        )
