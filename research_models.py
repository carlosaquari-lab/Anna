from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class ResearchSession:
    session_id: str
    started_at: str
    project_id: str
    project_name: str
    video_id: str
    schema_version: int = 2
    video_name: str = ""
    user_id: str = ""
    user_name: str = ""
    session_type: str = "participant"
    is_anonymous: bool = False
    status: str = "active"
    finished_at: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass
class PausePresentation:
    presentation_key: str
    pause_event_id: str
    video_id: str
    scheduled_time_ms: int
    activated_position_ms: int
    presentation_index: int
    started_elapsed_ms: int
    hotspots_present: list[dict[str, Any]] = field(default_factory=list)
    supports_present: list[dict[str, Any]] = field(default_factory=list)
    hotspot_activations: list[dict[str, Any]] = field(default_factory=list)
    support_activations: list[dict[str, Any]] = field(default_factory=list)
    continued_elapsed_ms: int | None = None

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "pause_id": self.pause_event_id,
            "pause_event_id": self.pause_event_id,
            "video_id": self.video_id,
            "scheduled_time_ms": self.scheduled_time_ms,
            "presented_position_ms": self.activated_position_ms,
            "activated_position_ms": self.activated_position_ms,
            "presentation_index": self.presentation_index,
            "is_repeated_presentation": self.presentation_index > 1,
            "hotspots_present": self.hotspots_present,
            "supports_present": self.supports_present,
            "pause_started_elapsed_ms": self.started_elapsed_ms,
        }
