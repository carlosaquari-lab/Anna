from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

SCHEMA_VERSION = "0.4.0-pause-event"
LEGACY_SCHEMA_VERSIONS = {None, "", "0.3.0-temporal-hotspot-editor"}
DEFAULT_PROJECT_ID = "anna-interactive-video"
FRAME_SIZE = (1536, 864)
FRAME_WIDTH = FRAME_SIZE[0]
FRAME_HEIGHT = FRAME_SIZE[1]
MIN_NORM_SIZE = 0.02
PAUSE_TOLERANCE_MS = 250
PAUSE_TRIGGER_TOLERANCE_MS = 120
GEOMETRY_EPSILON = 1e-6
DEFAULT_HOTSPOT_COLOR = "#00A6C8"
DEFAULT_FILL_OPACITY = 15
HOTSPOT_MESSAGE_MAX_CHARS = 40
HOTSPOT_TEXT_FONT_FAMILY_DEFAULT = "Arial"
HOTSPOT_TEXT_FONT_SIZE_DEFAULT = 26
HOTSPOT_TEXT_BOLD_DEFAULT = True
HOTSPOT_TEXT_UPPERCASE_DEFAULT = True
HOTSPOT_TEXT_COLOR_DEFAULT = "#FFFF00"
HOTSPOT_TEXT_BACKGROUND_DEFAULT = "#111111"
HOTSPOT_TEXT_BACKGROUND_OPACITY_DEFAULT = 100
SUPPORT_SLOTS = 3
HOTSPOT_PALETTE = {
    "turquoise": "#00A6C8",
    "blue": "#2A7FD1",
    "green": "#45A84A",
    "orange": "#FF8C24",
    "pink": "#D94A9C",
    "red": "#D94848",
}
COMMUNICATION_CATEGORIES: dict[str, str] = {
    "unspecified": "No especificado",
    "proper_person": "Persona / nombre propio",
    "noun_object": "Sustantivo / objeto",
    "verb_action": "Verbo / acción",
    "adjective": "Adjetivo",
    "adverb": "Adverbio",
    "social_expression": "Expresión social",
    "function_word": "Palabra funcional",
    "place": "Lugar",
    "other": "Otro",
}
COMMUNICATION_CATEGORY_ALIASES: dict[str, str] = {
    "noun": "noun_object",
    "descriptor": "adjective",
    "Descriptor": "adjective",
    "priority_emergency": "other",
    "Prioridad / emergencia": "other",
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def opacity_percent_to_alpha(opacity: int) -> int:
    return round(clamp(int(opacity), 0, 100) * 255 / 100)


def clamp_hotspot_message(text: str, max_chars: int = HOTSPOT_MESSAGE_MAX_CHARS) -> str:
    return str(text or "")[:max_chars]


def message_counter_text(text: str, max_chars: int = HOTSPOT_MESSAGE_MAX_CHARS) -> str:
    return f"{min(len(str(text or '')), max_chars)}/{max_chars}"


def validate_font_size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return HOTSPOT_TEXT_FONT_SIZE_DEFAULT
    return int(clamp(size, 10, 48))


def validate_opacity_percent(value: Any) -> int:
    try:
        opacity = int(value)
    except (TypeError, ValueError):
        return HOTSPOT_TEXT_BACKGROUND_OPACITY_DEFAULT
    return int(clamp(opacity, 0, 100))


def validate_hex_color(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            int(text[1:], 16)
            return text.upper()
        except ValueError:
            pass
    return default


def wrap_long_preview_words(text: str, chunk_size: int = 28) -> str:
    parts: list[str] = []
    for token in str(text or "").split(" "):
        if len(token) <= chunk_size:
            parts.append(token)
            continue
        chunks = [token[index : index + chunk_size] for index in range(0, len(token), chunk_size)]
        parts.append("\u200b".join(chunks))
    return " ".join(parts)


def normalize_geometry(geom: dict[str, Any], min_size: float = MIN_NORM_SIZE) -> dict[str, float]:
    x = clamp(float(geom.get("x", 0.0)), 0.0, 1.0)
    y = clamp(float(geom.get("y", 0.0)), 0.0, 1.0)
    width = clamp(float(geom.get("width", min_size)), min_size, 1.0)
    height = clamp(float(geom.get("height", min_size)), min_size, 1.0)
    if x + width > 1.0:
        x = max(0.0, 1.0 - width)
    if y + height > 1.0:
        y = max(0.0, 1.0 - height)
    return {"x": x, "y": y, "width": width, "height": height}


def pixel_to_normalized(rect: tuple[float, float, float, float], frame_size: tuple[int, int] = FRAME_SIZE) -> dict[str, float]:
    frame_w, frame_h = frame_size
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError("frame_size must be positive")
    x, y, width, height = rect
    return normalize_geometry({"x": x / frame_w, "y": y / frame_h, "width": width / frame_w, "height": height / frame_h})


def normalized_to_pixel(geom: dict[str, Any], frame_size: tuple[int, int] = FRAME_SIZE) -> tuple[float, float, float, float]:
    frame_w, frame_h = frame_size
    norm = normalize_geometry(geom)
    return (norm["x"] * frame_w, norm["y"] * frame_h, norm["width"] * frame_w, norm["height"] * frame_h)


def effective_video_rect(container_width: float, container_height: float, video_width: float = FRAME_WIDTH, video_height: float = FRAME_HEIGHT) -> tuple[float, float, float, float]:
    if container_width <= 0 or container_height <= 0 or video_width <= 0 or video_height <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    scale = min(container_width / video_width, container_height / video_height)
    width = video_width * scale
    height = video_height * scale
    return ((container_width - width) / 2.0, (container_height - height) / 2.0, width, height)


def message_strip_geometry(container_width: float, container_height: float, video_width: float = FRAME_WIDTH, video_height: float = FRAME_HEIGHT) -> tuple[float, float]:
    video_left, _, video_display_width, _ = effective_video_rect(container_width, container_height, video_width, video_height)
    return (video_left, video_display_width)


def hotspot_shape_path(hotspot: "Hotspot", frame_size: tuple[int, int] = FRAME_SIZE) -> QPainterPath:
    x, y, width, height = normalized_to_pixel(hotspot.geometry, frame_size)
    rect = QRectF(x, y, width, height)
    path = QPainterPath()
    if hotspot.shape == "ellipse":
        path.addEllipse(rect)
    else:
        path.addRect(rect)
    return path


def hotspots_overlap(first: "Hotspot", second: "Hotspot", frame_size: tuple[int, int] = FRAME_SIZE, epsilon: float = GEOMETRY_EPSILON) -> bool:
    intersected = hotspot_shape_path(first, frame_size).intersected(hotspot_shape_path(second, frame_size))
    bounds = intersected.boundingRect()
    return not intersected.isEmpty() and bounds.width() > epsilon and bounds.height() > epsilon


def first_overlap(hotspot: "Hotspot", others: list["Hotspot"], frame_size: tuple[int, int] = FRAME_SIZE) -> "Hotspot | None":
    for other in others:
        if other.hotspot_id != hotspot.hotspot_id and hotspots_overlap(hotspot, other, frame_size):
            return other
    return None


def move_pixel_rect(rect: tuple[float, float, float, float], delta: tuple[float, float], bounds: tuple[int, int] = FRAME_SIZE) -> tuple[float, float, float, float]:
    x, y, width, height = rect
    dx, dy = delta
    return (clamp(x + dx, 0.0, max(0.0, bounds[0] - width)), clamp(y + dy, 0.0, max(0.0, bounds[1] - height)), width, height)


def resize_pixel_rect(rect: tuple[float, float, float, float], handle: str, delta: tuple[float, float], bounds: tuple[int, int] = FRAME_SIZE, min_size_px: float = 24.0) -> tuple[float, float, float, float]:
    x, y, width, height = rect
    left, top, right, bottom = x, y, x + width, y + height
    dx, dy = delta
    if "w" in handle:
        left = clamp(left + dx, 0.0, right - min_size_px)
    if "e" in handle:
        right = clamp(right + dx, left + min_size_px, bounds[0])
    if "n" in handle:
        top = clamp(top + dy, 0.0, bottom - min_size_px)
    if "s" in handle:
        bottom = clamp(bottom + dy, top + min_size_px, bounds[1])
    return (left, top, right - left, bottom - top)


def color_default(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            int(text[1:], 16)
        except ValueError:
            return fallback
        return text.upper()
    return fallback


def require_range(name: str, value: Any, minimum: int, maximum: int) -> int:
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def validate_category(value: str) -> str:
    category = str(value or "unspecified")
    category = COMMUNICATION_CATEGORY_ALIASES.get(category, category)
    if category not in COMMUNICATION_CATEGORIES:
        raise ValueError(f"unsupported communication_category: {category}")
    return category

def validate_audio_asset(value: str | None) -> str | None:
    if value in {None, ""}:
        return None
    text = str(value).replace("\\", "/")
    if text.startswith("/") or ":" in text:
        raise ValueError("audio_asset must be a relative path")
    parts = [part for part in text.split("/") if part]
    if any(part == ".." for part in parts):
        raise ValueError("audio_asset cannot contain traversal")
    if len(parts) < 3 or parts[0] != "assets" or parts[1] != "audio":
        raise ValueError("audio_asset must be inside assets/audio")
    return "/".join(parts)

def validate_support_asset(value: str | None) -> str | None:
    if value in {None, ""}:
        return None
    text = str(value).replace("\\", "/")
    if text.startswith("/") or ":" in text:
        raise ValueError("support asset must be a relative path")
    parts = [part for part in text.split("/") if part]
    if any(part == ".." for part in parts):
        raise ValueError("support asset cannot contain traversal")
    if len(parts) < 3 or parts[0] != "assets" or parts[1] != "supports":
        raise ValueError("support asset must be inside assets/supports")
    return "/".join(parts)

@dataclass
class Hotspot:
    hotspot_id: str
    name: str = "Hotspot"
    shape: str = "rectangle"
    geometry: dict[str, float] = field(default_factory=lambda: {"x": 0.2, "y": 0.2, "width": 0.2, "height": 0.16})
    color: str = DEFAULT_HOTSPOT_COLOR
    fill_opacity: int = DEFAULT_FILL_OPACITY
    message_text: str = ""
    hotspot_label: str = ""
    show_message_text: bool = True
    communication_category: str = "unspecified"
    audio_asset: str | None = None
    font_family: str = HOTSPOT_TEXT_FONT_FAMILY_DEFAULT
    font_size_px: int = HOTSPOT_TEXT_FONT_SIZE_DEFAULT
    font_bold: bool = HOTSPOT_TEXT_BOLD_DEFAULT
    uppercase: bool = HOTSPOT_TEXT_UPPERCASE_DEFAULT
    text_color: str = HOTSPOT_TEXT_COLOR_DEFAULT
    background_color: str = HOTSPOT_TEXT_BACKGROUND_DEFAULT
    background_opacity: int = HOTSPOT_TEXT_BACKGROUND_OPACITY_DEFAULT
    tts_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "hotspot_id": self.hotspot_id,
            "name": self.name,
            "shape": self.shape,
            "geometry": normalize_geometry(self.geometry),
            "style": {"color": self.color, "border_width": 3, "fill_opacity": int(self.fill_opacity)},
            "message_text": self.message_text,
            "hotspot_label": self.hotspot_label,
            "show_message_text": bool(self.show_message_text),
            "communication_category": self.communication_category,
            "audio_asset": validate_audio_asset(self.audio_asset),
            "tts_enabled": bool(self.tts_enabled),
            "text_style": {
                "font_family": str(self.font_family or HOTSPOT_TEXT_FONT_FAMILY_DEFAULT),
                "font_size_px": validate_font_size(self.font_size_px),
                "font_bold": bool(self.font_bold),
                "uppercase": bool(self.uppercase),
                "text_color": validate_hex_color(self.text_color, HOTSPOT_TEXT_COLOR_DEFAULT),
                "background_color": validate_hex_color(self.background_color, HOTSPOT_TEXT_BACKGROUND_DEFAULT),
                "background_opacity": validate_opacity_percent(self.background_opacity),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Hotspot":
        if not isinstance(data, dict):
            raise ValueError("hotspot must be an object")
        shape = str(data.get("shape", "rectangle"))
        if shape not in {"rectangle", "ellipse"}:
            raise ValueError(f"unsupported hotspot shape: {shape}")
        style = data.get("style", {}) or {}
        text_style = data.get("text_style", {}) or {}
        legacy_size = data.get("message_text_size_px", HOTSPOT_TEXT_FONT_SIZE_DEFAULT)
        return cls(
            hotspot_id=str(data.get("hotspot_id") or ""),
            name=str(data.get("name") or data.get("hotspot_id") or "Hotspot"),
            shape=shape,
            geometry=normalize_geometry(data.get("geometry", {}) or {}),
            color=color_default(style.get("color", data.get("color", "")), DEFAULT_HOTSPOT_COLOR),
            fill_opacity=require_range("style.fill_opacity", style.get("fill_opacity", data.get("opacity", DEFAULT_FILL_OPACITY)), 0, 100),
            message_text=str(data.get("message_text", data.get("text", ""))),
            hotspot_label=str(data.get("hotspot_label", "")),
            show_message_text=bool(data.get("show_message_text", True)),
            communication_category=validate_category(str(data.get("communication_category", "unspecified"))),
            audio_asset=validate_audio_asset(data.get("audio_asset")),
            font_family=str(text_style.get("font_family", HOTSPOT_TEXT_FONT_FAMILY_DEFAULT) or ""),
            font_size_px=validate_font_size(text_style.get("font_size_px", legacy_size)),
            font_bold=bool(text_style.get("font_bold", HOTSPOT_TEXT_BOLD_DEFAULT)),
            uppercase=bool(text_style.get("uppercase", HOTSPOT_TEXT_UPPERCASE_DEFAULT)),
            text_color=validate_hex_color(text_style.get("text_color", HOTSPOT_TEXT_COLOR_DEFAULT), HOTSPOT_TEXT_COLOR_DEFAULT),
            background_color=validate_hex_color(text_style.get("background_color", HOTSPOT_TEXT_BACKGROUND_DEFAULT), HOTSPOT_TEXT_BACKGROUND_DEFAULT),
            background_opacity=validate_opacity_percent(text_style.get("background_opacity", HOTSPOT_TEXT_BACKGROUND_OPACITY_DEFAULT)),
            tts_enabled=bool(data.get("tts_enabled", True)),
        )


@dataclass
class SupportItem:
    support_id: str
    label: str = "Apoyo"
    text: str = ""
    image_asset: str | None = None
    audio_asset: str | None = None
    tts_enabled: bool = True
    visible: bool = True
    position: int = 0
    communication_category: str = "unspecified"

    def is_configured(self) -> bool:
        return bool(str(self.text or "").strip() or self.image_asset or self.audio_asset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "support_id": self.support_id,
            "label": self.label,
            "text": self.text,
            "image_asset": validate_support_asset(self.image_asset),
            "audio_asset": validate_support_asset(self.audio_asset),
            "tts_enabled": bool(self.tts_enabled),
            "visible": bool(self.visible),
            "position": int(clamp(self.position, 0, SUPPORT_SLOTS - 1)),
            "communication_category": validate_category(self.communication_category),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SupportItem":
        if not isinstance(data, dict):
            raise ValueError("support must be an object")
        # Compatibilidad con el formato antiguo kind/asset.
        kind = str(data.get("kind", ""))
        legacy_asset = data.get("asset")
        image_asset = data.get("image_asset")
        audio_asset = data.get("audio_asset")
        text = str(data.get("text") or "")
        if kind == "image" and not image_asset:
            image_asset = legacy_asset
        elif kind == "audio" and not audio_asset:
            audio_asset = legacy_asset
        return cls(
            support_id=str(data.get("support_id") or data.get("id") or "support"),
            label=str(data.get("label") or "Apoyo"),
            text=text,
            image_asset=validate_support_asset(image_asset),
            audio_asset=validate_support_asset(audio_asset),
            tts_enabled=bool(data.get("tts_enabled", True)),
            visible=bool(data.get("visible", True)),
            position=int(clamp(int(data.get("position", 0)), 0, SUPPORT_SLOTS - 1)),
            communication_category=validate_category(str(data.get("communication_category", "unspecified"))),
        )


def default_supports() -> list[SupportItem]:
    return [SupportItem(f"support_{index + 1}", f"Apoyo {index + 1}", position=index) for index in range(SUPPORT_SLOTS)]


def normalize_supports(supports: list[SupportItem] | None) -> list[SupportItem]:
    normalized = default_supports()
    for fallback_index, support in enumerate(list(supports or [])[:SUPPORT_SLOTS]):
        index = fallback_index
        text_id = str(support.support_id or "")
        if text_id.startswith("support_"):
            try:
                index = int(text_id.split("_", 1)[1]) - 1
            except (IndexError, ValueError):
                index = fallback_index
        elif 0 <= int(getattr(support, "position", fallback_index)) < SUPPORT_SLOTS:
            index = int(getattr(support, "position", fallback_index))
        index = int(clamp(index, 0, SUPPORT_SLOTS - 1))
        support.position = index
        support.label = support.label or f"Apoyo {index + 1}"
        normalized[index] = support
    return normalized


@dataclass
class PauseEvent:
    pause_id: str
    time_ms: int
    hotspots: list[Hotspot] = field(default_factory=list)
    supports: list[SupportItem] = field(default_factory=default_supports)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.pause_id,
            "pause_id": self.pause_id,  # compatibilidad transitoria
            "time_ms": int(self.time_ms),
            "hotspots": [hotspot.to_dict() for hotspot in self.hotspots],
            "supports": [support.to_dict() for support in normalize_supports(deepcopy(self.supports))],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PauseEvent":
        if not isinstance(data, dict):
            raise ValueError("pause must be an object")
        time_ms = int(data.get("time_ms", -1))
        if time_ms < 0:
            raise ValueError("pause.time_ms must be positive")
        hotspots = [Hotspot.from_dict(item) for item in data.get("hotspots", [])]
        seen = set()
        for hotspot in hotspots:
            if not hotspot.hotspot_id:
                raise ValueError("hotspot_id cannot be empty")
            if hotspot.hotspot_id in seen:
                pause_id = str(data.get("event_id") or data.get("pause_id") or f"pause-{time_ms}")
                raise ValueError(f"duplicate hotspot_id in pause {pause_id}: {hotspot.hotspot_id}")
            seen.add(hotspot.hotspot_id)
        raw_supports = [SupportItem.from_dict(item) for item in data.get("supports", [])]
        seen_supports = set()
        pause_id = str(data.get("event_id") or data.get("pause_id") or f"pause-{time_ms}")
        for support in raw_supports:
            if not support.support_id:
                raise ValueError("support_id cannot be empty")
            if support.support_id in seen_supports:
                raise ValueError(f"duplicate support_id in pause {pause_id}: {support.support_id}")
            seen_supports.add(support.support_id)
        supports = normalize_supports(raw_supports)
        return cls(pause_id, time_ms, hotspots, supports)


# Alias de compatibilidad: el código y los proyectos anteriores todavía pueden usar PausePoint.
PausePoint = PauseEvent


@dataclass
class VideoEntry:
    video_id: str
    name: str
    source: str
    pauses: list[PausePoint] = field(default_factory=list)
    start_time: int | None = None
    end_time: int | None = None

    def validate_bounds(self, duration_ms: int | None = None) -> None:
        if self.start_time is not None and int(self.start_time) < 0:
            raise ValueError("start_time must be non-negative")
        if self.end_time is not None and int(self.end_time) < 0:
            raise ValueError("end_time must be non-negative")
        if self.start_time is not None and self.end_time is not None and int(self.start_time) >= int(self.end_time):
            raise ValueError("start_time must be before end_time")
        if duration_ms is not None and int(duration_ms) > 0:
            if self.start_time is not None and int(self.start_time) >= int(duration_ms):
                raise ValueError("start_time must be before the physical video end")
            if self.end_time is not None and int(self.end_time) > int(duration_ms):
                raise ValueError("end_time cannot exceed the physical video duration")

    def effective_start(self) -> int:
        return int(self.start_time) if self.start_time is not None else 0

    def effective_end(self, duration_ms: int) -> int:
        physical_end = max(0, int(duration_ms))
        if self.end_time is None:
            return physical_end
        return min(int(self.end_time), physical_end) if physical_end > 0 else int(self.end_time)

    def pause_is_active(self, pause: PausePoint, duration_ms: int) -> bool:
        end = self.effective_end(duration_ms)
        return int(pause.time_ms) >= self.effective_start() and (end <= 0 or int(pause.time_ms) < end)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "video_id": self.video_id,
            "name": self.name,
            "source": self.source,
            "frame_width": FRAME_WIDTH,
            "frame_height": FRAME_HEIGHT,
            "pause_events": [pause.to_dict() for pause in sorted(self.pauses, key=lambda item: item.time_ms)],
            "pauses": [pause.to_dict() for pause in sorted(self.pauses, key=lambda item: item.time_ms)],  # compatibilidad transitoria
        }
        if self.start_time is not None:
            payload["start_time"] = int(self.start_time)
        if self.end_time is not None:
            payload["end_time"] = int(self.end_time)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int = 0) -> "VideoEntry":
        if not isinstance(data, dict):
            raise ValueError("video entry must be an object")
        raw_events = data.get("pause_events", data.get("pauses", []))
        pauses = [PauseEvent.from_dict(item) for item in raw_events]
        validate_no_pause_overlaps(pauses)
        # Migración: los apoyos globales antiguos se trasladan solo a la primera pausa.
        legacy_supports = normalize_supports([SupportItem.from_dict(item) for item in data.get("supports", [])])
        if pauses and any(item.is_configured() for item in legacy_supports) and not any(item.is_configured() for item in pauses[0].supports):
            pauses[0].supports = legacy_supports
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        video = cls(
            video_id=str(data.get("video_id") or data.get("id") or f"video-{index + 1}"),
            name=str(data.get("name") or f"Vídeo {index + 1}"),
            source=str(data.get("source") or ""),
            pauses=sorted(pauses, key=lambda item: item.time_ms),
            start_time=None if start_time is None else int(start_time),
            end_time=None if end_time is None else int(end_time),
        )
        video.validate_bounds()
        return video

def default_project(duration_ms: int = 0) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": DEFAULT_PROJECT_ID,
        "video": {"source": "", "duration_ms": int(duration_ms), "frame_width": FRAME_WIDTH, "frame_height": FRAME_HEIGHT},
        "videos": [{"video_id": "video-1", "name": "Vídeo 1", "source": "", "frame_width": FRAME_WIDTH, "frame_height": FRAME_HEIGHT, "pause_events": [], "pauses": []}],
        "current_video_index": 0,
        "text_output": {"background_color": "#000000", "background_opacity": 100, "text_color": "#FFFFFF", "text_size": 28, "duration_ms": 0, "visible": True},
        "pause_tolerance_ms": PAUSE_TOLERANCE_MS,
        "pause_events": [],
        "pauses": [],  # compatibilidad transitoria
    }


def find_pause(pauses: list[PausePoint], time_ms: int, tolerance_ms: int = PAUSE_TOLERANCE_MS) -> PausePoint | None:
    candidates = [pause for pause in pauses if abs(pause.time_ms - time_ms) <= tolerance_ms]
    return min(candidates, key=lambda pause: abs(pause.time_ms - time_ms)) if candidates else None


def find_or_create_pause(pauses: list[PausePoint], time_ms: int, tolerance_ms: int = PAUSE_TOLERANCE_MS) -> tuple[PausePoint, bool]:
    existing = find_pause(pauses, time_ms, tolerance_ms)
    if existing:
        return existing, False
    pause = PausePoint(f"pause-{int(time_ms)}", int(time_ms))
    pauses.append(pause)
    pauses.sort(key=lambda item: item.time_ms)
    return pause, True


def add_hotspot_to_time(pauses: list[PausePoint], time_ms: int, hotspot: Hotspot, tolerance_ms: int = PAUSE_TOLERANCE_MS) -> tuple[PausePoint, bool]:
    pause, created = find_or_create_pause(pauses, time_ms, tolerance_ms)
    pause.hotspots.append(hotspot)
    return pause, created


def validate_no_pause_overlaps(pauses: list[PausePoint]) -> None:
    for pause in pauses:
        for index, hotspot in enumerate(pause.hotspots):
            conflict = first_overlap(hotspot, pause.hotspots[index + 1 :])
            if conflict:
                raise ValueError(f"hotspot overlap in pause {pause.pause_id}: {hotspot.hotspot_id} overlaps {conflict.hotspot_id}")


def next_pause_after(pauses: list[PausePoint], time_ms: int) -> PausePoint | None:
    later = [pause for pause in pauses if pause.time_ms > time_ms]
    return min(later, key=lambda pause: pause.time_ms) if later else None


def crossed_pause_times(pauses: list[PausePoint], previous_ms: int, current_ms: int, tolerance_ms: int = PAUSE_TRIGGER_TOLERANCE_MS) -> list[int]:
    if current_ms <= previous_ms:
        return []
    return [pause.time_ms for pause in sorted(pauses, key=lambda item: item.time_ms) if previous_ms < pause.time_ms <= current_ms]


def next_temporal_pause(
    pauses: list[PausePoint],
    pause_states: dict[int, str],
    previous_ms: int,
    current_ms: int,
    *,
    scrubbing: bool = False,
) -> tuple[PausePoint | None, dict[str, Any]]:
    direction = "forward" if current_ms > previous_ms else "backward" if current_ms < previous_ms else "still"
    diagnostics: dict[str, Any] = {
        "previous_position": int(previous_ms),
        "current_position": int(current_ms),
        "direction": direction,
        "scrubbing": bool(scrubbing),
        "pause_states": {str(pause.time_ms): pause_states.get(pause.time_ms, "armed") for pause in pauses},
        "crossed": [],
        "ignored": [],
        "activated_pause": None,
    }
    if scrubbing:
        diagnostics["ignored"].append({"reason": "scrubbing"})
        return None, diagnostics
    if direction != "forward":
        diagnostics["ignored"].append({"reason": "not_forward"})
        return None, diagnostics
    for pause in sorted(pauses, key=lambda item: item.time_ms):
        crossed = previous_ms < pause.time_ms <= current_ms
        state = pause_states.get(pause.time_ms, "armed")
        if crossed:
            diagnostics["crossed"].append(pause.time_ms)
            if state == "armed":
                diagnostics["activated_pause"] = pause.time_ms
                return pause, diagnostics
            diagnostics["ignored"].append({"pause_time": pause.time_ms, "reason": f"state_{state}"})
    if not diagnostics["crossed"]:
        diagnostics["ignored"].append({"reason": "no_crossing"})
    return None, diagnostics


def safe_continue_exit_position(current_pause_ms: int, pauses: list[PausePoint], duration_ms: int = 0, trigger_tolerance_ms: int = PAUSE_TRIGGER_TOLERANCE_MS) -> tuple[int, int | None]:
    next_pause = next_pause_after(pauses, current_pause_ms)
    desired = current_pause_ms + trigger_tolerance_ms + 1
    if next_pause:
        desired = min(desired, max(current_pause_ms, next_pause.time_ms - 1))
    if duration_ms:
        desired = min(desired, max(0, duration_ms - 1))
    return max(0, int(desired)), (next_pause.time_ms if next_pause else None)


def remove_hotspot_from_pause(pause: PausePoint, hotspot_id: str) -> bool:
    before = len(pause.hotspots)
    pause.hotspots = [hotspot for hotspot in pause.hotspots if hotspot.hotspot_id != hotspot_id]
    return len(pause.hotspots) != before


def migrate_project_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a new payload in the current PauseEvent schema.

    The migration is deterministic and does not mutate the input. Legacy ``pauses``
    arrays are copied to the canonical ``pause_events`` key, and ``pause_id`` is
    promoted to ``event_id`` while remaining readable for compatibility.
    """
    if not isinstance(payload, dict):
        raise ValueError("project JSON must be an object")
    migrated = deepcopy(payload)
    version = migrated.get("schema_version")
    if version not in LEGACY_SCHEMA_VERSIONS and version != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {version!r}")

    def migrate_events(container: dict[str, Any]) -> list[dict[str, Any]]:
        raw = container.get("pause_events", None)
        if not raw and container.get("pauses"):
            raw = container.get("pauses", [])
        if raw is None:
            raw = []
        if not isinstance(raw, list):
            raise ValueError("pause_events must be a list")
        events: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("PauseEvent must be an object")
            event = deepcopy(item)
            event_id = str(event.get("event_id") or event.get("pause_id") or f"pause-{int(event.get('time_ms', 0))}")
            event["event_id"] = event_id
            event.setdefault("pause_id", event_id)
            events.append(event)
        container["pause_events"] = events
        container["pauses"] = deepcopy(events)  # compatibilidad transitoria
        return events

    top_events = migrate_events(migrated)
    videos = migrated.get("videos")
    if isinstance(videos, list):
        for video in videos:
            if isinstance(video, dict):
                migrate_events(video)
        if videos and isinstance(videos[0], dict) and not videos[0].get("pause_events") and top_events:
            videos[0]["pause_events"] = deepcopy(top_events)
            videos[0]["pauses"] = deepcopy(top_events)

    migrated["schema_version"] = SCHEMA_VERSION
    return migrated


def validate_project_payload(payload: dict[str, Any]) -> list[PausePoint]:
    if not isinstance(payload, dict):
        raise ValueError("project JSON must be an object")
    payload = migrate_project_payload(payload)
    video = payload.get("video")
    if not isinstance(video, dict):
        raise ValueError("video must be an object")
    if int(video.get("frame_width", 0)) <= 0 or int(video.get("frame_height", 0)) <= 0:
        raise ValueError("video frame size must be positive")
    raw_pauses = payload.get("pause_events", [])
    if not isinstance(raw_pauses, list):
        raise ValueError("pauses must be a list")
    pauses = [PauseEvent.from_dict(item) for item in raw_pauses]
    times = set()
    for pause in pauses:
        if pause.time_ms in times:
            raise ValueError(f"duplicate pause time: {pause.time_ms}")
        times.add(pause.time_ms)
    validate_no_pause_overlaps(pauses)
    return sorted(pauses, key=lambda item: item.time_ms)


def videos_from_project_payload(payload: dict[str, Any]) -> list[VideoEntry]:
    payload = migrate_project_payload(payload)
    raw_videos = payload.get("videos")
    if isinstance(raw_videos, list) and raw_videos:
        videos = [VideoEntry.from_dict(item, index) for index, item in enumerate(raw_videos)]
        legacy_pauses = payload.get("pause_events", [])
        if legacy_pauses and videos and not videos[0].pauses:
            videos[0].pauses = validate_project_payload(payload)
        return videos
    pauses = validate_project_payload(payload)
    video = payload.get("video", {}) or {}
    return [VideoEntry("video-1", "Vídeo 1", str(video.get("source") or ""), pauses)]


def serialize_project(project: dict[str, Any], pauses: list[PausePoint], duration_ms: int = 0, videos: list[VideoEntry] | None = None, current_video_index: int = 0) -> dict[str, Any]:
    payload = deepcopy(project)
    payload["schema_version"] = SCHEMA_VERSION
    payload.setdefault("video", {})
    payload["video"].setdefault("source", "")
    payload["video"]["duration_ms"] = int(duration_ms or payload["video"].get("duration_ms", 0))
    payload["video"]["frame_width"] = FRAME_WIDTH
    payload["video"]["frame_height"] = FRAME_HEIGHT
    payload.setdefault("text_output", default_project()["text_output"])
    payload["pause_tolerance_ms"] = PAUSE_TOLERANCE_MS
    if videos is None:
        payload["pause_events"] = [pause.to_dict() for pause in sorted(pauses, key=lambda item: item.time_ms)]
        payload["pauses"] = deepcopy(payload["pause_events"])  # compatibilidad transitoria
        payload["videos"] = [VideoEntry("video-1", "Vídeo 1", payload["video"]["source"], deepcopy(pauses)).to_dict()]
        payload["current_video_index"] = 0
    else:
        safe_index = int(clamp(current_video_index, 0, max(0, len(videos) - 1))) if videos else 0
        payload["videos"] = [video.to_dict() for video in videos]
        payload["current_video_index"] = safe_index
        payload["video"]["source"] = videos[safe_index].source if videos else ""
        payload["pause_events"] = [pause.to_dict() for pause in sorted(videos[safe_index].pauses if videos else pauses, key=lambda item: item.time_ms)]
        payload["pauses"] = deepcopy(payload["pause_events"])  # compatibilidad transitoria
    return payload


class History:
    def __init__(self, limit: int = 80) -> None:
        self.limit = limit
        self.undo_stack: list[dict[str, Any]] = []
        self.redo_stack: list[dict[str, Any]] = []

    def push(self, state: dict[str, Any]) -> None:
        self.undo_stack.append(deepcopy(state))
        if len(self.undo_stack) > self.limit:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 1

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo(self, current_state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.can_undo():
            return None
        self.redo_stack.append(deepcopy(current_state if current_state is not None else self.undo_stack[-1]))
        self.undo_stack.pop()
        return deepcopy(self.undo_stack[-1])

    def redo(self, current_state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.redo_stack:
            return None
        next_state = self.redo_stack.pop()
        self.undo_stack.append(deepcopy(next_state))
        return deepcopy(next_state)
