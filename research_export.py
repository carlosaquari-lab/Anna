from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

EXCLUDED_EXPORT_FIELDS = {"notes", "group"}
NAME_FIELDS = {"participant_name", "user_name"}


EVENT_FIELDS = [
    "schema_version",
    "timestamp",
    "session_id",
    "event_index",
    "elapsed_session_ms",
    "event_type",
    "project_id",
    "project_name",
    "participant_id",
    "participant_name",
    "user_id",
    "user_name",
    "is_anonymous",
    "video_id",
    "video_name",
    "video_position_ms",
    "pause_id",
    "pause_event_id",
    "hotspot_id",
    "support_id",
    "pause_elapsed_ms",
    "target_type",
    "target_id",
]

SUMMARY_FIELDS = [
    "schema_version",
    "session_id",
    "status",
    "started_at",
    "finished_at",
    "duration_ms",
    "project_id",
    "project_name",
    "video_id",
    "pauses_presented",
    "repeated_presentations",
    "hotspots_activated",
    "supports_activated",
    "manual_seeks",
    "continue_presses",
    "professional_turn_marked",
    "response_marked_adequate",
    "review_marked",
    "pauses_without_interaction",
]


def _json_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


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


def sanitize_export_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_export_value(item)
            for key, item in value.items()
            if key not in EXCLUDED_EXPORT_FIELDS and not looks_like_absolute_path(item)
        }
    if isinstance(value, list):
        return [sanitize_export_value(item) for item in value if not looks_like_absolute_path(item)]
    if looks_like_absolute_path(value):
        return ""
    return value


def sanitize_export_row(row: dict[str, Any], *, anonymized: bool = False) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in row.items():
        if key in EXCLUDED_EXPORT_FIELDS:
            continue
        if anonymized and key in NAME_FIELDS:
            sanitized[key] = ""
            continue
        sanitized[key] = sanitize_export_value(value)
    return sanitized


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _json_value(row.get(field, "")) for field in fields})


def export_sessions_csv(sessions_root: Path, export_dir: Path, *, anonymized: bool = False) -> tuple[Path, Path]:
    events: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for session_dir in sorted(path for path in sessions_root.glob("*") if path.is_dir()):
        events_path = session_dir / "events.jsonl"
        if events_path.exists():
            for line in events_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(sanitize_export_row(json.loads(line), anonymized=anonymized))
        summary_path = session_dir / "summary.json"
        if summary_path.exists():
            summaries.append(sanitize_export_row(json.loads(summary_path.read_text(encoding="utf-8")), anonymized=anonymized))
    event_fields = list(dict.fromkeys(EVENT_FIELDS + [key for row in events for key in row if key not in EXCLUDED_EXPORT_FIELDS]))
    summary_fields = list(dict.fromkeys(SUMMARY_FIELDS + [key for row in summaries for key in row if key not in EXCLUDED_EXPORT_FIELDS]))
    events_csv = export_dir / ("events_anonymized.csv" if anonymized else "events.csv")
    summaries_csv = export_dir / ("session_summaries_anonymized.csv" if anonymized else "session_summaries.csv")
    write_csv(events_csv, events, event_fields)
    write_csv(summaries_csv, summaries, summary_fields)
    return events_csv, summaries_csv


def export_sessions_csv_anonymized(sessions_root: Path, export_dir: Path) -> tuple[Path, Path]:
    return export_sessions_csv(sessions_root, export_dir, anonymized=True)
