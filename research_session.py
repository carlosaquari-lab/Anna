from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from research_models import PausePresentation, ResearchSession, utc_now_iso


def looks_like_absolute_path(value: Any) -> bool:
    text = str(value or "")
    normalized = text.replace("/", "\\")
    return (
        ":\\" in normalized
        or normalized.startswith("\\\\")
        or text.startswith("/")
        or "\\Users\\" in normalized
        or "\\OneDrive\\" in normalized
        or "\\Documents\\" in normalized
        or "\\Desktop\\" in normalized
    )


def privacy_safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: privacy_safe_value(item)
            for key, item in value.items()
            if not looks_like_absolute_path(item)
        }
    if isinstance(value, list):
        return [privacy_safe_value(item) for item in value if not looks_like_absolute_path(item)]
    if looks_like_absolute_path(value):
        return None
    return value


class ResearchSessionManager:
    SCHEMA_VERSION = 2

    def __init__(self, sessions_root: Path) -> None:
        self.sessions_root = sessions_root
        self.active_session: ResearchSession | None = None
        self.session_dir: Path | None = None
        self.events_path: Path | None = None
        self.summary_path: Path | None = None
        self.started_monotonic_ms = 0
        self.elapsed_override_ms: int | None = None
        self.events: list[dict[str, Any]] = []
        self.presentations: list[PausePresentation] = []
        self.active_pause: PausePresentation | None = None
        self.pause_counts: Counter[str] = Counter()
        self.rearm_counts: Counter[str] = Counter()

    @property
    def is_active(self) -> bool:
        return self.active_session is not None and self.active_session.status == "active"

    @property
    def session_id(self) -> str | None:
        return self.active_session.session_id if self.active_session else None

    def _now_ms(self) -> int:
        if self.elapsed_override_ms is not None:
            return int(self.elapsed_override_ms)
        return int(datetime.now().timestamp() * 1000)

    def _elapsed_ms(self) -> int:
        if self.active_session is None:
            return 0
        return max(0, self._now_ms() - self.started_monotonic_ms)

    def start_session(
        self,
        *,
        project_id: str,
        project_name: str,
        video_id: str,
        video_name: str = "",
        video_position_ms: int = 0,
        user_id: str = "",
        user_name: str = "",
        session_type: str = "participant",
        is_anonymous: bool = False,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> ResearchSession:
        if self.is_active:
            raise RuntimeError("research session already active")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8]
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self.session_dir = self.sessions_root / session_id
        self.session_dir.mkdir(parents=False, exist_ok=False)
        self.events_path = self.session_dir / "events.jsonl"
        self.summary_path = self.session_dir / "summary.json"
        self.started_monotonic_ms = self._now_ms()
        self.events = []
        self.presentations = []
        self.active_pause = None
        self.pause_counts = Counter()
        self.rearm_counts = Counter()
        self.active_session = ResearchSession(
            session_id=session_id,
            started_at=utc_now_iso(),
            project_id=str(project_id or ""),
            project_name=str(project_name or ""),
            video_id=str(video_id or ""),
            schema_version=self.SCHEMA_VERSION,
            video_name=str(video_name or ""),
            user_id=str(user_id or ""),
            user_name=str(user_name or ""),
            session_type=str(session_type or "participant"),
            is_anonymous=bool(is_anonymous),
        )
        self._write_session()
        self.record_event(
            "session_started",
            video_id=video_id,
            video_name=video_name,
            video_position_ms=int(video_position_ms),
            start_time=start_time,
            end_time=end_time,
        )
        return self.active_session

    def _write_session(self) -> None:
        if self.active_session is None or self.session_dir is None:
            return
        (self.session_dir / "session.json").write_text(
            json.dumps(self.active_session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record_event(self, event_type: str, **payload: Any) -> dict[str, Any] | None:
        if not self.is_active or self.events_path is None or self.active_session is None:
            return None
        pause_id = payload.pop("pause_id", payload.pop("pause_event_id", None))
        video_id = payload.pop("video_id", self.active_session.video_id)
        video_name = payload.pop("video_name", self.active_session.video_name)
        video_position_ms = payload.pop("video_position_ms", None)
        elapsed_ms = self._elapsed_ms()
        if self.events:
            elapsed_ms = max(elapsed_ms, int(self.events[-1].get("elapsed_session_ms", 0)))
        participant_id = self.active_session.user_id or None
        participant_name = self.active_session.user_name or None
        event = {
            "schema_version": self.SCHEMA_VERSION,
            "timestamp": utc_now_iso(),
            "session_id": self.active_session.session_id,
            "event_index": len(self.events) + 1,
            "event_type": str(event_type),
            "project_id": self.active_session.project_id,
            "project_name": self.active_session.project_name or None,
            "participant_id": participant_id,
            "participant_name": participant_name,
            "user_id": self.active_session.user_id,
            "user_name": self.active_session.user_name,
            "is_anonymous": bool(self.active_session.is_anonymous),
            "video_id": video_id or None,
            "video_name": video_name or None,
            "video_position_ms": int(video_position_ms) if video_position_ms is not None else None,
            "pause_id": pause_id or None,
            "pause_event_id": pause_id or None,
            "elapsed_session_ms": int(elapsed_ms),
        }
        for key, value in payload.items():
            safe_value = privacy_safe_value(value)
            if safe_value is not None and safe_value != "":
                event[key] = safe_value
        self.events.append(event)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def present_pause(
        self,
        *,
        pause_event_id: str,
        video_id: str,
        video_name: str = "",
        scheduled_time_ms: int,
        activated_position_ms: int,
        hotspots_present: list[dict[str, Any]],
        supports_present: list[dict[str, Any]],
    ) -> PausePresentation | None:
        if not self.is_active:
            return None
        self.pause_counts[pause_event_id] += 1
        presentation = PausePresentation(
            presentation_key=f"{pause_event_id}:{self.pause_counts[pause_event_id]}",
            pause_event_id=pause_event_id,
            video_id=video_id,
            scheduled_time_ms=int(scheduled_time_ms),
            activated_position_ms=int(activated_position_ms),
            presentation_index=self.pause_counts[pause_event_id],
            started_elapsed_ms=self._elapsed_ms(),
            hotspots_present=hotspots_present,
            supports_present=supports_present,
        )
        self.presentations.append(presentation)
        self.active_pause = presentation
        self.record_event("pause_event_presented", video_name=video_name, **presentation.to_event_payload())
        return presentation

    def record_pause_rearmed(
        self,
        *,
        pause_event_id: str,
        video_id: str,
        video_name: str = "",
        scheduled_time_ms: int,
        from_ms: int,
        to_ms: int,
        video_position_ms: int | None = None,
    ) -> dict[str, Any] | None:
        if self.pause_counts[pause_event_id] <= 0:
            return None
        self.rearm_counts[pause_event_id] += 1
        return self.record_event(
            "pause_rearmed",
            pause_id=pause_event_id,
            video_id=video_id,
            video_name=video_name,
            video_position_ms=video_position_ms if video_position_ms is not None else to_ms,
            scheduled_time_ms=int(scheduled_time_ms),
            from_ms=int(from_ms),
            to_ms=int(to_ms),
            rearm_index=self.rearm_counts[pause_event_id],
        )

    def _record_interaction(
        self,
        *,
        event_type: str,
        item_key: str,
        item_id: str,
        audio_played: bool,
        tts_played: bool,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.is_active:
            return None

        requested_pause_id = str(payload.pop("pause_id", payload.pop("pause_event_id", "")) or "")
        presentation = self.active_pause
        if presentation is not None and requested_pause_id and presentation.pause_event_id != requested_pause_id:
            return None
        if presentation is None and not requested_pause_id:
            return None

        if presentation is not None:
            activations = (
                presentation.hotspot_activations
                if event_type == "hotspot_activated"
                else presentation.support_activations
            )
            order = len(activations) + 1
            pause_elapsed = max(0, self._elapsed_ms() - presentation.started_elapsed_ms)
            activations.append({item_key: item_id, "activation_order": order, "pause_elapsed_ms": pause_elapsed})
            pause_event_id = presentation.pause_event_id
        else:
            # El clic real aporta el identificador de pausa. Se conserva aunque la
            # presentación haya perdido su referencia interna, evitando resúmenes
            # falsamente vacíos sin inventar una activación posterior.
            pause_event_id = requested_pause_id
            order = 1 + sum(
                1
                for event in self.events
                if event.get("event_type") == event_type
                and event.get("pause_event_id") == pause_event_id
                and event.get(item_key) == item_id
            )
            pause_elapsed = 0

        return self.record_event(
            event_type,
            pause_event_id=pause_event_id,
            **{item_key: item_id},
            activation_order=order,
            pause_elapsed_ms=pause_elapsed,
            audio_played=bool(audio_played),
            tts_played=bool(tts_played),
            target_type="hotspot" if event_type == "hotspot_activated" else "support",
            target_id=item_id,
            **payload,
        )

    def record_hotspot_activation(self, hotspot_id: str, *, audio_played: bool = False, tts_played: bool = False, **payload: Any) -> dict[str, Any] | None:
        return self._record_interaction(
            event_type="hotspot_activated",
            item_key="hotspot_id",
            item_id=hotspot_id,
            audio_played=audio_played,
            tts_played=tts_played,
            payload=payload,
        )

    def record_support_activation(self, support_id: str, *, audio_played: bool = False, tts_played: bool = False, **payload: Any) -> dict[str, Any] | None:
        return self._record_interaction(
            event_type="support_activated",
            item_key="support_id",
            item_id=support_id,
            audio_played=audio_played,
            tts_played=tts_played,
            payload=payload,
        )

    def record_continue(self, *, video_position_ms: int | None = None, **payload: Any) -> None:
        if self.active_pause is None:
            self.record_event("continue_pressed", video_position_ms=video_position_ms, **payload)
            return
        pause_elapsed = self._elapsed_ms() - self.active_pause.started_elapsed_ms
        self.active_pause.continued_elapsed_ms = self._elapsed_ms()
        first_interactions = [
            item["pause_elapsed_ms"]
            for item in [*self.active_pause.hotspot_activations, *self.active_pause.support_activations]
        ]
        self.record_event(
            "continue_pressed",
            pause_event_id=self.active_pause.pause_event_id,
            video_position_ms=video_position_ms,
            **payload,
            pause_elapsed_ms=pause_elapsed,
            pause_duration_ms=pause_elapsed,
            presentation_index=self.active_pause.presentation_index,
            time_to_first_interaction_ms=min(first_interactions) if first_interactions else None,
            hotspot_activation_count=len(self.active_pause.hotspot_activations),
            support_activation_count=len(self.active_pause.support_activations),
            no_interaction=not first_interactions,
        )
        self.active_pause = None

    def finish_session(
        self,
        *,
        status: str = "completed",
        video_id: str | None = None,
        video_name: str = "",
        video_position_ms: int | None = None,
        finish_reason: str | None = None,
    ) -> dict[str, Any]:
        if self.active_session is None:
            raise RuntimeError("no active research session")
        final_duration_ms = self._elapsed_ms()
        self.record_event(
            "session_finished",
            status=status,
            duration_ms=final_duration_ms,
            video_id=video_id or self.active_session.video_id,
            video_name=video_name or self.active_session.video_name,
            video_position_ms=video_position_ms,
            finish_reason=finish_reason or status,
        )
        self.active_session.status = status
        self.active_session.finished_at = utc_now_iso()
        self.active_session.duration_ms = final_duration_ms
        summary = self.build_summary()
        if self.summary_path is not None:
            self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_session()
        self.active_session = None
        self.active_pause = None
        return summary

    def build_summary(self) -> dict[str, Any]:
        session = self.active_session
        if session is None:
            return {}
        event_counts = Counter(event["event_type"] for event in self.events)
        pause_durations = [
            max(0, (p.continued_elapsed_ms or self._elapsed_ms()) - p.started_elapsed_ms)
            for p in self.presentations
        ]
        first_times: list[int] = []
        for presentation in self.presentations:
            interactions = [
                item["pause_elapsed_ms"]
                for item in [*presentation.hotspot_activations, *presentation.support_activations]
            ]
            if interactions:
                first_times.append(min(interactions))

        hotspot_ids = {
            event.get("hotspot_id") for event in self.events
            if event.get("event_type") == "hotspot_activated"
        }
        support_ids = {
            event.get("support_id") for event in self.events
            if event.get("event_type") == "support_activated"
        }
        pause_ids = [presentation.pause_event_id for presentation in self.presentations]

        video_names: dict[str, str] = {}
        per_video: dict[str, dict[str, Any]] = {}

        def video_row(video_id: str) -> dict[str, Any]:
            key = str(video_id or session.video_id or "video")
            if key not in per_video:
                per_video[key] = {
                    "video_id": key,
                    "video_name": video_names.get(key, key),
                    "time_ms": 0,
                    "pauses_presented": 0,
                    "repeated_presentations": 0,
                    "hotspots_available": 0,
                    "hotspots_activated": 0,
                    "supports_available": 0,
                    "supports_activated": 0,
                    "manual_seeks": 0,
                    "backward_seeks": 0,
                    "forward_seeks": 0,
                    "continue_presses": 0,
                    "professional_turn_marked": 0,
                    "response_marked_adequate": 0,
                    "review_marked": 0,
                }
            return per_video[key]

        presentation_counts: Counter[tuple[str, str]] = Counter()
        for presentation in self.presentations:
            row = video_row(presentation.video_id)
            row["pauses_presented"] += 1
            row["hotspots_available"] += len(presentation.hotspots_present)
            row["supports_available"] += len(presentation.supports_present)
            presentation_counts[(presentation.video_id, presentation.pause_event_id)] += 1

        for (video_id, _pause_id), count in presentation_counts.items():
            video_row(video_id)["repeated_presentations"] += max(0, count - 1)

        # Distribución temporal por vídeo a partir de la secuencia real de eventos.
        # Cada intervalo se atribuye al vídeo del evento que lo inicia.
        ordered_events = sorted(self.events, key=lambda item: int(item.get("elapsed_session_ms", 0)))
        session_end_ms = self._elapsed_ms()
        for index, event in enumerate(ordered_events):
            start_ms = int(event.get("elapsed_session_ms", 0))
            end_ms = (
                int(ordered_events[index + 1].get("elapsed_session_ms", start_ms))
                if index + 1 < len(ordered_events)
                else session_end_ms
            )
            video_id = str(event.get("video_id") or session.video_id or "video")
            video_row(video_id)["time_ms"] += max(0, end_ms - start_ms)

        mark_fields = {
            "professional_turn_marked": "professional_turn_marked",
            "response_marked_adequate": "response_marked_adequate",
            "review_marked": "review_marked",
        }
        hotspot_activity: Counter[tuple[str, str, str, str]] = Counter()
        support_activity: Counter[tuple[str, str, str, str, str]] = Counter()
        support_audio_played: Counter[tuple[str, str, str, str, str]] = Counter()
        support_tts_played: Counter[tuple[str, str, str, str, str]] = Counter()

        for event in self.events:
            video_id = str(event.get("video_id") or session.video_id or "video")
            video_name = str(event.get("video_name") or "")
            if video_name:
                video_names[video_id] = video_name
            row = video_row(video_id)
            if video_name:
                row["video_name"] = video_name
            event_type = str(event.get("event_type") or "")
            if event_type == "hotspot_activated":
                row["hotspots_activated"] += 1
                hotspot_activity[(
                    video_id,
                    str(event.get("hotspot_id") or ""),
                    str(event.get("hotspot_text") or event.get("message_text") or event.get("hotspot_id") or "Hotspot"),
                    str(event.get("typology") or event.get("communication_category") or event.get("category") or "Sin categoría"),
                )] += 1
            elif event_type == "support_activated":
                row["supports_activated"] += 1
                support_key = (
                    video_id,
                    str(event.get("support_id") or ""),
                    str(event.get("support_text") or event.get("text") or event.get("support_id") or "Apoyo"),
                    str(event.get("typology") or event.get("communication_category") or event.get("category") or "Sin categoría"),
                    str(event.get("support_type") or "apoyo"),
                )
                if event.get("audio_played"):
                    support_audio_played[support_key] += 1
                if event.get("tts_played"):
                    support_tts_played[support_key] += 1
                support_activity[(
                    video_id,
                    str(event.get("support_id") or ""),
                    str(event.get("support_text") or event.get("text") or event.get("support_id") or "Apoyo"),
                    str(event.get("typology") or event.get("communication_category") or event.get("category") or "Sin categoría"),
                    str(event.get("support_type") or "apoyo"),
                )] += 1
            elif event_type == "video_seeked":
                row["manual_seeks"] += 1
                direction = event.get("direction")
                if direction == "backward":
                    row["backward_seeks"] += 1
                elif direction == "forward":
                    row["forward_seeks"] += 1
            elif event_type == "continue_pressed":
                row["continue_presses"] += 1
            elif event_type in mark_fields:
                row[mark_fields[event_type]] += 1

        hotspot_rows = [
            {
                "video_id": video_id,
                "video_name": video_names.get(video_id, per_video.get(video_id, {}).get("video_name", video_id)),
                "hotspot_id": hotspot_id,
                "text": text,
                "category": category,
                "typology": category,
                "count": count,
            }
            for (video_id, hotspot_id, text, category), count in sorted(hotspot_activity.items())
        ]
        support_rows = [
            {
                "video_id": video_id,
                "video_name": video_names.get(video_id, per_video.get(video_id, {}).get("video_name", video_id)),
                "support_id": support_id,
                "text": text,
                "category": category,
                "typology": category,
                "type": support_type,
                "count": count,
                "audio_played_count": support_audio_played[(video_id, support_id, text, category, support_type)],
                "tts_played_count": support_tts_played[(video_id, support_id, text, category, support_type)],
            }
            for (video_id, support_id, text, category, support_type), count in sorted(support_activity.items())
        ]

        return {
            "schema_version": self.SCHEMA_VERSION,
            "session_id": session.session_id,
            "status": session.status,
            "started_at": session.started_at,
            "finished_at": session.finished_at,
            "duration_ms": session.duration_ms or self._elapsed_ms(),
            "project_id": session.project_id,
            "project_name": session.project_name,
            "video_id": session.video_id,
            "user_id": session.user_id,
            "user_name": session.user_name,
            "session_type": session.session_type,
            "is_anonymous": session.is_anonymous,
            "videos_used": sorted({event.get("video_id") for event in self.events if event.get("video_id")}),
            "pauses_presented": len(self.presentations),
            "repeated_presentations": sum(max(0, count - 1) for count in Counter(pause_ids).values()),
            "total_pause_duration_ms": sum(pause_durations),
            "mean_pause_duration_ms": round(sum(pause_durations) / len(pause_durations), 2) if pause_durations else 0,
            "mean_time_to_first_interaction_ms": round(sum(first_times) / len(first_times), 2) if first_times else None,
            "hotspots_available": sum(len(p.hotspots_present) for p in self.presentations),
            "hotspots_activated": event_counts["hotspot_activated"],
            "distinct_hotspots_activated": len([item for item in hotspot_ids if item]),
            "supports_available": sum(len(p.supports_present) for p in self.presentations),
            "supports_activated": event_counts["support_activated"],
            "distinct_supports_activated": len([item for item in support_ids if item]),
            "manual_seeks": event_counts["video_seeked"],
            "backward_seeks": len([e for e in self.events if e.get("event_type") == "video_seeked" and e.get("direction") == "backward"]),
            "forward_seeks": len([e for e in self.events if e.get("event_type") == "video_seeked" and e.get("direction") == "forward"]),
            "go_to_start_seeks": len([e for e in self.events if e.get("event_type") == "video_seeked" and e.get("seek_action") == "go_to_start"]),
            "slider_drag_seeks": len([e for e in self.events if e.get("event_type") == "video_seeked" and e.get("seek_action") == "slider_drag"]),
            "timeline_click_seeks": len([e for e in self.events if e.get("event_type") == "video_seeked" and e.get("seek_action") == "timeline_click"]),
            "video_changes": event_counts["video_changed"],
            "continue_presses": event_counts["continue_pressed"],
            "professional_turn_marked": event_counts["professional_turn_marked"],
            "response_marked_adequate": event_counts["response_marked_adequate"],
            "review_marked": event_counts["review_marked"],
            "pauses_without_interaction": len([p for p in self.presentations if not p.hotspot_activations and not p.support_activations]),
            "per_video": list(per_video.values()),
            "hotspot_activity": hotspot_rows,
            "support_activity": support_rows,
        }
