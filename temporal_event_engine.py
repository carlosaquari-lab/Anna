from __future__ import annotations

from enum import Enum
from typing import Protocol, Sequence, TypeVar


POST_EVENT_MARGIN_MS = 200


class PlaybackMode(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    SEEKING = "seeking"
    INTERACTION_PAUSED = "interaction_paused"


class TemporalEvent(Protocol):
    """Minimal interface required by the temporal engine."""

    time_ms: int


EventT = TypeVar("EventT", bound=TemporalEvent)


def find_crossed_pause_event(
    previous_ms: int,
    current_ms: int,
    events: Sequence[EventT],
    mode: PlaybackMode,
) -> EventT | None:
    """Return the first event crossed during normal forward playback.

    Seeking, stopped playback, interaction pauses, stationary updates, and
    backwards movement never activate events.
    """
    previous = int(previous_ms)
    current = int(current_ms)

    if mode is not PlaybackMode.PLAYING:
        return None
    if current <= previous:
        return None

    for event in sorted(events, key=lambda item: int(item.time_ms)):
        event_time = int(event.time_ms)
        if previous < event_time <= current:
            return event
    return None


def continue_position(
    event_time_ms: int,
    *,
    duration_ms: int = 0,
    margin_ms: int = POST_EVENT_MARGIN_MS,
) -> int:
    """Return the safe playback position after closing a PauseEvent."""
    event_time = max(0, int(event_time_ms))
    margin = max(0, int(margin_ms))
    target = event_time + margin

    if duration_ms > 0:
        target = min(target, max(0, int(duration_ms) - 1))
    return target
