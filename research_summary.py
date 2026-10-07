from __future__ import annotations

from datetime import datetime
from typing import Any


COMMUNICATION_LABELS = {
    "request": "Petición",
    "comment": "Comentario",
    "response": "Respuesta",
    "social": "Social",
    "noun": "Nombre",
    "verb": "Verbo",
    "adjective": "Adjetivo",
    "unspecified": "No especificado",
    "Sin categoría": "No especificado",
    "Sin categoria": "No especificado",
}


def value(summary: dict[str, Any], key: str, default: Any = 0) -> Any:
    item = summary.get(key, default)
    return default if item in (None, "") else item


def int_value(summary: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(value(summary, key, default) or 0)
    except (TypeError, ValueError):
        return default


def plural(count: int, singular: str, plural_text: str) -> str:
    return singular if count == 1 else plural_text


def count_label(count: int, singular: str, plural_text: str) -> str:
    return f"{count} {plural(count, singular, plural_text)}"


def none_or_count_label(count: int, singular: str, plural_text: str, none_text: str = "Ninguna") -> str:
    return none_text if count == 0 else count_label(count, singular, plural_text)


def presented_activated_phrase(presented: int, activated: int, singular: str, plural_text: str) -> str:
    item_word = singular if presented == 1 else plural_text
    presented_word = "presentado" if presented == 1 else "presentados"
    activated_word = "activado" if activated == 1 else "activados"
    return f"{presented} {item_word} {presented_word}, {activated} {activated_word}"


def format_duration(ms: Any) -> str:
    try:
        total_seconds = max(0, round(int(ms or 0) / 1000))
    except (TypeError, ValueError):
        total_seconds = 0
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    if seconds or not parts:
        parts.append(f"{seconds} s")
    return " ".join(parts)


def format_date(value_: Any) -> str:
    text = str(value_ or "").strip()
    if not text:
        return "No disponible"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:10] if len(text) >= 10 else text
    return parsed.strftime("%d/%m/%Y")


def typology_label(code: Any) -> str:
    text = str(code or "unspecified").strip()
    return COMMUNICATION_LABELS.get(text, text or "No especificado")


def clean_text(value_: Any, fallback: str) -> str:
    text = " ".join(str(value_ or "").split())
    return text if text else fallback


def video_count(summary: dict[str, Any]) -> int:
    videos_used = summary.get("videos_used")
    if isinstance(videos_used, list):
        return len([item for item in videos_used if item])
    per_video = summary.get("per_video")
    if isinstance(per_video, list):
        return len([item for item in per_video if isinstance(item, dict)])
    return 0


def support_audio_tts_text(row: dict[str, Any]) -> str:
    audio_count = int(row.get("audio_played_count", 0) or 0)
    tts_count = int(row.get("tts_played_count", 0) or 0)
    details = []
    if audio_count:
        details.append(f"audio {count_label(audio_count, 'vez', 'veces')}")
    if tts_count:
        details.append(f"TTS {count_label(tts_count, 'vez', 'veces')}")
    return f"  Uso: {', '.join(details)}" if details else ""


def activity_count(rows: list[dict[str, Any]], id_key: str) -> int:
    identifiers = {str(row.get(id_key) or "") for row in rows if row.get(id_key)}
    return len(identifiers) if identifiers else len(rows)


def pause_reference(row: dict[str, Any]) -> str:
    for key in ("pause_time_ms", "scheduled_time_ms", "presented_position_ms"):
        if key in row:
            try:
                return f"pausa {format_duration(int(row[key]))}"
            except (TypeError, ValueError):
                pass
    return clean_text(row.get("pause_label"), "")


def duplicate_text_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (
            clean_text(row.get("video_name") or row.get("video_id"), "Vídeo").casefold(),
            clean_text(row.get("text"), "").casefold(),
        )
        if key[1]:
            counts[key] = counts.get(key, 0) + 1
    return {key for key, count in counts.items() if count > 1}


def activity_title(row: dict[str, Any], fallback: str, duplicate_keys: set[tuple[str, str]]) -> str:
    video = clean_text(row.get("video_name") or row.get("video_id"), "Vídeo")
    text = clean_text(row.get("text"), fallback)
    title = f"- {video}: {text}"
    reference = pause_reference(row)
    if (video.casefold(), text.casefold()) in duplicate_keys and reference:
        title = f"{title} ({reference})"
    return title


def _en_count(value: int, singular: str, plural: str | None = None) -> str:
    return f"{value} {singular if value == 1 else (plural or singular + 's')}"


def _format_research_summary_en(summary: dict[str, Any]) -> str:
    if not summary:
        return "No research data is available yet."
    participant = "Anonymous session" if summary.get("is_anonymous") else clean_text(summary.get("user_name"), "No participant")
    pauses = int_value(summary, "pauses_presented")
    repeated = int_value(summary, "repeated_presentations")
    turns = int_value(summary, "professional_turn_marked")
    appropriate = int_value(summary, "response_marked_adequate")
    review = int_value(summary, "review_marked")
    continue_presses = int_value(summary, "continue_presses")
    hotspot_activity = [row for row in summary.get("hotspot_activity", []) or [] if isinstance(row, dict)]
    support_activity = [row for row in summary.get("support_activity", []) or [] if isinstance(row, dict)]
    lines = [
        "SESSION SUMMARY", "",
        f"Participant: {participant}",
        f"Date: {format_date(summary.get('started_at'))}",
        f"Duration: {format_duration(summary.get('duration_ms'))}",
        f"Videos used: {_en_count(video_count(summary), 'video')}",
        f"Pauses presented: {_en_count(pauses, 'pause') if pauses else 'None'}",
        f"Repeated pauses: {_en_count(repeated, 'pause') if repeated else 'None'}",
        "", "PROFESSIONAL INTERACTION", "",
        f"Turns: {_en_count(turns, 'turn')}",
        f"Appropriate responses: {_en_count(appropriate, 'response')}",
        f"Items to review: {_en_count(review, 'item')}",
        f"Continue: {_en_count(continue_presses, 'press', 'presses')}",
        "", "HOTSPOTS", "",
        f"Hotspots presented: {_en_count(int_value(summary, 'hotspots_available'), 'hotspot')}",
        f"Hotspots activated: {_en_count(int_value(summary, 'distinct_hotspots_activated', activity_count(hotspot_activity, 'hotspot_id')), 'hotspot') if hotspot_activity else 'None'}",
    ]
    for row in hotspot_activity:
        label = clean_text(row.get("text") or row.get("hotspot_text") or row.get("hotspot_id"), "Hotspot")
        lines.extend(["", str(label), f"  Activations: {_en_count(int(row.get('count', 0) or 0), 'activation')}"])
    lines.extend([
        "", "SUPPORTS", "",
        f"Supports presented: {_en_count(int_value(summary, 'supports_available'), 'support')}",
        f"Supports activated: {_en_count(int_value(summary, 'distinct_supports_activated', activity_count(support_activity, 'support_id')), 'support') if support_activity else 'None'}",
    ])
    for row in support_activity:
        label = clean_text(row.get("text") or row.get("support_text") or row.get("support_id"), "Support")
        lines.extend(["", str(label), f"  Activations: {_en_count(int(row.get('count', 0) or 0), 'activation')}"])
    per_video = [row for row in summary.get("per_video", []) or [] if isinstance(row, dict)]
    if per_video:
        lines.extend(["", "BREAKDOWN BY VIDEO"])
        for index, row in enumerate(per_video, start=1):
            name = clean_text(row.get("video_name") or row.get("video_id"), f"Video {index}")
            lines.extend([
                "", str(name),
                f"  Time used: {format_duration(row.get('time_ms', 0))}",
                f"  Pauses presented: {int(row.get('pauses_presented', 0) or 0)}",
                f"  Repeated pauses: {int(row.get('repeated_presentations', 0) or 0)}",
                f"  Hotspots activated: {int(row.get('hotspots_activated', 0) or 0)}",
                f"  Supports activated: {int(row.get('supports_activated', 0) or 0)}",
                f"  Turns: {int(row.get('professional_turn_marked', 0) or 0)}",
                f"  Appropriate responses: {int(row.get('response_marked_adequate', 0) or 0)}",
                f"  To review: {int(row.get('review_marked', 0) or 0)}",
            ])
    return "\n".join(lines)


def format_research_summary(summary: dict[str, Any], language: str = "es") -> str:
    if language == "en-US":
        return _format_research_summary_en(summary)
    if not summary:
        return "Todavía no hay datos de investigación disponibles."

    participant = "Sesión anónima" if summary.get("is_anonymous") else clean_text(summary.get("user_name"), "Sin participante")
    pauses = int_value(summary, "pauses_presented")
    repeated = int_value(summary, "repeated_presentations")
    turns = int_value(summary, "professional_turn_marked")
    adequate = int_value(summary, "response_marked_adequate")
    review = int_value(summary, "review_marked")
    continue_presses = int_value(summary, "continue_presses")
    hotspots_presented = int_value(summary, "hotspots_available")
    hotspots_activated = int_value(summary, "hotspots_activated")
    supports_presented = int_value(summary, "supports_available")
    supports_activated = int_value(summary, "supports_activated")
    hotspot_activity = [row for row in summary.get("hotspot_activity", []) or [] if isinstance(row, dict)]
    support_activity = [row for row in summary.get("support_activity", []) or [] if isinstance(row, dict)]
    distinct_hotspots_activated = int_value(summary, "distinct_hotspots_activated", activity_count(hotspot_activity, "hotspot_id"))
    distinct_supports_activated = int_value(summary, "distinct_supports_activated", activity_count(support_activity, "support_id"))

    lines = [
        "RESUMEN DE LA SESIÓN",
        "",
        f"Participante: {participant}",
        f"Fecha: {format_date(summary.get('started_at'))}",
        f"Duración: {format_duration(summary.get('duration_ms'))}",
        f"Vídeos trabajados: {count_label(video_count(summary), 'vídeo', 'vídeos')}",
        f"Pausas presentadas: {none_or_count_label(pauses, 'pausa', 'pausas')}",
        f"Pausas repetidas: {none_or_count_label(repeated, 'pausa', 'pausas')}",
        "",
        "INTERACCIÓN PROFESIONAL",
        "",
        f"Turnos: {count_label(turns, 'turno', 'turnos')}",
        f"Respuestas adecuadas: {count_label(adequate, 'respuesta', 'respuestas')}",
        f"Elementos para revisar: {count_label(review, 'elemento', 'elementos')}",
        f"Continuar: {count_label(continue_presses, 'pulsación', 'pulsaciones')}",
    ]
    if review == 0:
        lines.append("No se marcaron elementos para revisar.")

    lines.extend([
        "",
        "HOTSPOTS",
        "",
        f"Hotspots presentados: {count_label(hotspots_presented, 'hotspot', 'hotspots')}",
    ])
    if hotspot_activity:
        lines.append(f"Hotspots activados: {count_label(distinct_hotspots_activated, 'hotspot', 'hotspots')}")
        lines.append(f"Activaciones de hotspots: {count_label(hotspots_activated, 'activación', 'activaciones')}")
    else:
        lines.append(f"Hotspots activados: {none_or_count_label(hotspots_activated, 'hotspot', 'hotspots', 'Ninguno')}")
    if hotspot_activity:
        lines.append("")
        duplicate_keys = duplicate_text_keys(hotspot_activity)
        for row in hotspot_activity:
            count = int(row.get("count", 0) or 0)
            lines.extend([
                activity_title(row, "Hotspot", duplicate_keys),
                f"  Tipología: {typology_label(row.get('typology') or row.get('category'))}",
                f"  Activaciones: {count_label(count, 'activación', 'activaciones')}",
            ])
    elif hotspots_activated == 0:
        lines.append("No se activaron hotspots.")

    lines.extend([
        "",
        "APOYOS",
        "",
        f"Apoyos presentados: {count_label(supports_presented, 'apoyo', 'apoyos')}",
    ])
    if support_activity:
        lines.append(f"Apoyos activados: {count_label(distinct_supports_activated, 'apoyo', 'apoyos')}")
        lines.append(f"Activaciones de apoyos: {count_label(supports_activated, 'activación', 'activaciones')}")
    else:
        lines.append(f"Apoyos activados: {none_or_count_label(supports_activated, 'apoyo', 'apoyos', 'Ninguno')}")
    if support_activity:
        lines.append("")
        duplicate_keys = duplicate_text_keys(support_activity)
        for row in support_activity:
            count = int(row.get("count", 0) or 0)
            lines.extend([
                activity_title(row, "Apoyo", duplicate_keys),
                f"  Activaciones: {count_label(count, 'activación', 'activaciones')}",
            ])
            usage = support_audio_tts_text(row)
            if usage:
                lines.append(usage)
    elif supports_presented == 0:
        lines.append("No se presentaron apoyos durante esta sesión.")
    elif supports_activated == 0:
        lines.append("No se activaron apoyos.")

    per_video = [row for row in summary.get("per_video", []) or [] if isinstance(row, dict)]
    if per_video:
        lines.extend(["", "DESGLOSE POR VÍDEO"])
        for index, row in enumerate(per_video, start=1):
            name = clean_text(row.get("video_name") or row.get("video_id"), f"Vídeo {index}")
            lines.extend([
                "",
                str(name),
                f"  Tiempo trabajado: {format_duration(row.get('time_ms', 0))}",
                f"  Pausas presentadas: {none_or_count_label(int(row.get('pauses_presented', 0) or 0), 'pausa', 'pausas')}",
                f"  Pausas repetidas: {none_or_count_label(int(row.get('repeated_presentations', 0) or 0), 'pausa', 'pausas')}",
                f"  Hotspots: {presented_activated_phrase(int(row.get('hotspots_available', 0) or 0), int(row.get('hotspots_activated', 0) or 0), 'hotspot', 'hotspots')}",
                f"  Apoyos: {presented_activated_phrase(int(row.get('supports_available', 0) or 0), int(row.get('supports_activated', 0) or 0), 'apoyo', 'apoyos')}",
                f"  Turnos: {int(row.get('professional_turn_marked', 0) or 0)}",
                f"  Respuestas adecuadas: {int(row.get('response_marked_adequate', 0) or 0)}",
                f"  Para revisar: {int(row.get('review_marked', 0) or 0)}",
            ])

    technical_lines = []
    video_changes = int_value(summary, "video_changes")
    backward = int_value(summary, "backward_seeks")
    forward = int_value(summary, "forward_seeks")
    go_to_start = int_value(summary, "go_to_start_seeks")
    manual = int_value(summary, "manual_seeks")
    if video_changes:
        technical_lines.append(f"Cambios de vídeo: {video_changes}")
    if backward:
        technical_lines.append(f"Retrocesos temporales: {backward}")
    if forward:
        technical_lines.append(f"Avances temporales: {forward}")
    if go_to_start:
        technical_lines.append(f"Uso de Inicio: {go_to_start}")
    if manual:
        technical_lines.append(f"Seeks manuales: {manual}")
    if technical_lines:
        lines.extend(["", "DETALLES TÉCNICOS", "", *technical_lines])

    return "\n".join(lines)
