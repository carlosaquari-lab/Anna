
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import uuid
import re
from copy import deepcopy
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QLocale, QPointF, QRectF, QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QFont, QFontMetrics, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut, QValidator
from PySide6.QtMultimedia import QAudioInput, QAudioOutput, QMediaCaptureSession, QMediaDevices, QMediaFormat, QMediaPlayer, QMediaRecorder, QVideoSink
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except ImportError:  # Qt TextToSpeech puede no estar instalado en todos los entornos.
    QTextToSpeech = None
from PySide6.QtWidgets import QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QFrame, QGraphicsObject, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget, QStyle, QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QVBoxLayout, QWidget

from temporal_event_engine import PlaybackMode
from playback_controller import PlaybackController
from hotspot_model import COMMUNICATION_CATEGORIES, DEFAULT_FILL_OPACITY, DEFAULT_HOTSPOT_COLOR, DEFAULT_PROJECT_ID, FRAME_HEIGHT, FRAME_SIZE, FRAME_WIDTH, HOTSPOT_MESSAGE_MAX_CHARS, HOTSPOT_PALETTE, HOTSPOT_TEXT_BACKGROUND_DEFAULT, HOTSPOT_TEXT_BACKGROUND_OPACITY_DEFAULT, HOTSPOT_TEXT_BOLD_DEFAULT, HOTSPOT_TEXT_UPPERCASE_DEFAULT, HOTSPOT_TEXT_COLOR_DEFAULT, HOTSPOT_TEXT_FONT_FAMILY_DEFAULT, HOTSPOT_TEXT_FONT_SIZE_DEFAULT, History, Hotspot, PAUSE_TOLERANCE_MS, PAUSE_TRIGGER_TOLERANCE_MS, PausePoint, SupportItem, VideoEntry, clamp, clamp_hotspot_message, default_project, default_supports, effective_video_rect, find_or_create_pause, find_pause, first_overlap, message_counter_text, message_strip_geometry, move_pixel_rect, next_temporal_pause, normalize_supports, normalized_to_pixel, opacity_percent_to_alpha, pixel_to_normalized, remove_hotspot_from_pause, resize_pixel_rect, safe_continue_exit_position, serialize_project, validate_audio_asset, validate_category, validate_font_size, validate_hex_color, validate_opacity_percent, validate_project_payload, validate_support_asset, videos_from_project_payload, wrap_long_preview_words
from research_session import ResearchSessionManager
from research_export import export_sessions_csv
from research_summary import format_research_summary
from users_manager import UsersManager
from localization import DEFAULT_LANGUAGE, LANGUAGE_LABELS, PRODUCT_NAME, PRODUCT_SUBTITLE, PRODUCT_TITLE, current_language, load_language, localize_widget_tree, save_language, set_language, tr
from data_storage import users_path
from version import APP_VERSION

ROOT = Path(__file__).resolve().parent
def application_data_root() -> Path:
    if not getattr(sys, "frozen", False):
        return ROOT
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    current = local_app_data / "ANNA"
    legacy = local_app_data / "Emma"
    if not current.exists() and legacy.is_dir():
        shutil.copytree(legacy, current)
    current.mkdir(parents=True, exist_ok=True)
    return current


USER_ROOT = application_data_root()
RESULTS_DIR = USER_ROOT / "results"
USERS_CSV = users_path(USER_ROOT)
LOG_PATH = RESULTS_DIR / "editor_hotspots_log.jsonl"
DEFAULT_PROJECT_FILENAME = "anna_project.json"
AUDIO_DIR = USER_ROOT / "assets" / "audio"
SUPPORTS_DIR = USER_ROOT / "assets" / "supports"
APP_ICON = ROOT / "assets" / "app" / "ANNA.ico"
HOTSPOT_TTS_FIELD = "tts_enabled"
HANDLE = 10.0
MIN_SIZE_PX = 24.0
MARKER_TOLERANCE_MS = PAUSE_TRIGGER_TOLERANCE_MS
MANUAL_SEEK_CONFIRM_TOLERANCE_MS = 35
CONTINUE_RESUME_FALLBACK_MS = 120


def asset_path(relative_path: str) -> Path:
    local_path = USER_ROOT / relative_path
    return local_path if local_path.exists() else ROOT / relative_path


def asset_reference(path: Path) -> str:
    resolved = path.resolve()
    for base in (USER_ROOT, ROOT):
        if resolved.is_relative_to(base):
            return resolved.relative_to(base).as_posix()
    raise ValueError("asset path is outside ANNA resource roots")


class JsonlLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **payload: object) -> None:
        row = {"ts": round(time.time(), 3), "event": event, **payload}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def format_time(ms: int) -> str:
    total = max(0, int(ms))
    hours = total // 3600000
    minutes = (total % 3600000) // 60000
    seconds = (total % 60000) // 1000
    millis = total % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


SEGMENT_TIME_PATTERN = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)\.(\d{3})$")


def parse_segment_time(text: str) -> int | None:
    match = SEGMENT_TIME_PATTERN.fullmatch(str(text).strip())
    if match is None:
        return None
    hours, minutes, seconds, millis = (int(value) for value in match.groups())
    return hours * 3_600_000 + minutes * 60_000 + seconds * 1_000 + millis


class SegmentTimeValidator(QValidator):
    def validate(self, text: str, position: int):
        if parse_segment_time(text) is not None:
            return QValidator.State.Acceptable, text, position
        if re.fullmatch(r"[0-9:.]*", text):
            return QValidator.State.Intermediate, text, position
        return QValidator.State.Invalid, text, position


def qcolor(value: str, fallback: str = DEFAULT_HOTSPOT_COLOR) -> QColor:
    color = QColor(value)
    return color if color.isValid() else QColor(fallback)


def color_icon(color: str, selected: bool = False) -> QIcon:
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QPen(QColor("#172033" if selected else "#7d8999"), 3 if selected else 1))
    painter.drawRoundedRect(QRectF(3, 3, 16, 16), 3, 3)
    painter.end()
    return QIcon(pixmap)


def tool_palette_icon(name: str) -> QIcon:
    pixmap = QPixmap(34, 34)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if name in {"select", "edit", "delete"}:
        circle_color = {"select": "#1677C8", "edit": "#EF8B22", "delete": "#D94848"}[name]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(circle_color))
        painter.drawEllipse(QRectF(3, 3, 28, 28))
        painter.setPen(QPen(QColor("#111111"), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if name == "select":
            painter.setBrush(QColor("#111111"))
            painter.drawPolygon([QPointF(10, 7), QPointF(10, 25), QPointF(15, 21), QPointF(18, 28), QPointF(21, 27), QPointF(18, 20), QPointF(24, 20)])
        elif name == "edit":
            painter.drawLine(QPointF(11, 23), QPointF(22, 12))
            painter.drawLine(QPointF(19, 9), QPointF(25, 15))
            painter.drawLine(QPointF(10, 24), QPointF(15, 23))
        else:
            painter.drawRect(QRectF(11, 13, 12, 13))
            painter.drawLine(QPointF(9, 11), QPointF(25, 11))
            painter.drawLine(QPointF(14, 8), QPointF(20, 8))
            painter.drawLine(QPointF(15, 16), QPointF(15, 23))
            painter.drawLine(QPointF(19, 16), QPointF(19, 23))
    elif name == "ellipse":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#111111"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawEllipse(QRectF(7, 9, 20, 16))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#111111"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRect(QRectF(8, 9, 18, 16))
    painter.end()
    return QIcon(pixmap)


def hotspot_shape_icon(shape: str) -> QIcon:
    return tool_palette_icon("ellipse" if shape == "ellipse" else "rectangle")


def simple_tool_icon(name: str) -> QIcon:
    pixmap = QPixmap(34, 34)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#1677C8"), 3))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if name == "edit":
        painter.drawLine(QPointF(9, 24), QPointF(23, 10))
        painter.drawLine(QPointF(19, 8), QPointF(25, 14))
        painter.drawRect(QRectF(8, 24, 8, 3))
    elif name == "delete":
        painter.drawRect(QRectF(10, 13, 14, 14))
        painter.drawLine(QPointF(8, 11), QPointF(26, 11))
        painter.drawLine(QPointF(14, 8), QPointF(20, 8))
    elif name == "arrow":
        painter.drawLine(QPointF(8, 17), QPointF(25, 17))
        painter.drawLine(QPointF(19, 10), QPointF(26, 17))
        painter.drawLine(QPointF(19, 24), QPointF(26, 17))
    elif name == "text":
        font = painter.font()
        font.setBold(True)
        font.setPointSize(18)
        painter.setFont(font)
        painter.drawText(QRectF(5, 5, 24, 24), Qt.AlignmentFlag.AlignCenter, "T")
    elif name == "speaker":
        painter.drawPolygon([QPointF(7, 14), QPointF(13, 14), QPointF(21, 8), QPointF(21, 26), QPointF(13, 20), QPointF(7, 20)])
        painter.drawArc(QRectF(18, 11, 9, 12), -45 * 16, 90 * 16)
    elif name == "start":
        painter.drawLine(QPointF(8, 8), QPointF(8, 26))
        painter.drawLine(QPointF(26, 17), QPointF(11, 17))
        painter.drawLine(QPointF(16, 11), QPointF(10, 17))
        painter.drawLine(QPointF(16, 23), QPointF(10, 17))
    painter.end()
    return QIcon(pixmap)


def mode_icon(name: str) -> QIcon:
    pixmap = QPixmap(34, 34)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#111111"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if name == "professional":
        painter.drawEllipse(QRectF(11, 11, 12, 12))
        painter.drawEllipse(QRectF(15, 15, 4, 4))
        for start, end in (
            (QPointF(17, 5), QPointF(17, 10)),
            (QPointF(17, 24), QPointF(17, 29)),
            (QPointF(5, 17), QPointF(10, 17)),
            (QPointF(24, 17), QPointF(29, 17)),
            (QPointF(8.5, 8.5), QPointF(12, 12)),
            (QPointF(22, 22), QPointF(25.5, 25.5)),
            (QPointF(25.5, 8.5), QPointF(22, 12)),
            (QPointF(12, 22), QPointF(8.5, 25.5)),
        ):
            painter.drawLine(start, end)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111111"))
        painter.drawPolygon([QPointF(11, 7), QPointF(27, 17), QPointF(11, 27)])
    painter.end()
    return QIcon(pixmap)


class AspectRatioPixmapLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.original_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_original_pixmap(self, pixmap: QPixmap) -> None:
        self.original_pixmap = QPixmap(pixmap)
        self.update_scaled_pixmap()

    def clear_original_pixmap(self) -> None:
        self.original_pixmap = QPixmap()
        self.clear()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_scaled_pixmap()

    def update_scaled_pixmap(self) -> None:
        if self.original_pixmap.isNull():
            return
        target = self.contentsRect().size()
        if target.width() <= 0 or target.height() <= 0:
            return
        self.setPixmap(
            self.original_pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class SupportImageButton(QToolButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.original_pixmap = QPixmap()

    def set_original_pixmap(self, pixmap: QPixmap) -> None:
        self.original_pixmap = QPixmap(pixmap)
        self.setIcon(QIcon(self.original_pixmap))
        self.update_icon_size()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_icon_size()

    def update_icon_size(self) -> None:
        if self.original_pixmap.isNull():
            return
        area = self.contentsRect()
        label_height = 24 if self.text() else 8
        width = max(1, area.width() - 12)
        height = max(1, area.height() - label_height - 8)
        self.setIconSize(QSize(width, height))


def thumbnail_icon(frame: QPixmap | None = None, selected: bool = False) -> QIcon:
    pixmap = QPixmap(88, 50)
    pixmap.fill(QColor("#dfe7f1" if not selected else "#cde8ff"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if frame and not frame.isNull():
        scaled = frame.scaled(pixmap.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        source = QRectF((scaled.width() - pixmap.width()) / 2, (scaled.height() - pixmap.height()) / 2, pixmap.width(), pixmap.height())
        painter.drawPixmap(QRectF(0, 0, pixmap.width(), pixmap.height()), scaled, source)
    painter.setPen(QPen(QColor("#1677C8" if selected else "#8aa0b8"), 3 if selected else 1))
    painter.drawRect(QRectF(1, 1, 86, 48))
    painter.end()
    return QIcon(pixmap)


class DialogAudioController:
    def __init__(
        self,
        owner: QDialog,
        *,
        get_asset: Callable[[], str | None],
        set_asset: Callable[[str | None], None],
        validate_asset: Callable[[str | None], str | None],
        target_dir: Path,
        filename_prefix: str,
        audio_player: QMediaPlayer,
        status_label: QLabel,
        record_button: QPushButton,
        listen_button: QPushButton,
        delete_button: QPushButton,
        stop_button: QPushButton,
    ) -> None:
        self.owner = owner
        self.get_asset = get_asset
        self.set_asset = set_asset
        self.validate_asset = validate_asset
        self.target_dir = target_dir
        self.filename_prefix = filename_prefix
        self.audio_player = audio_player
        self.status_label = status_label
        self.record_button = record_button
        self.listen_button = listen_button
        self.delete_button = delete_button
        self.stop_button = stop_button
        self.record_button.setCheckable(True)
        self.temp_assets: list[str] = []

    def asset_path(self, asset: str | None) -> Path | None:
        if not asset:
            return None
        try:
            validated = self.validate_asset(asset)
        except ValueError:
            return None
        return asset_path(validated) if validated else None

    def make_portable_asset(self, source: Path) -> str:
        source = source.resolve()
        if source.is_relative_to(USER_ROOT) or source.is_relative_to(ROOT):
            try:
                asset = self.validate_asset(asset_reference(source))
                if asset:
                    return asset
            except ValueError:
                pass
        self.target_dir.mkdir(parents=True, exist_ok=True)
        target = self.target_dir / f"{self.filename_prefix}_{uuid.uuid4().hex}{source.suffix.lower()}"
        shutil.copy2(source, target)
        asset = self.validate_asset(asset_reference(target)) or ""
        self.temp_assets.append(asset)
        return asset

    def choose_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.owner,
            tr("button.select_audio").rstrip("…"),
            str(ROOT),
            tr("file.audio_filter"),
        )
        if not path:
            return
        try:
            self.set_asset(self.make_portable_asset(Path(path)))
        except (OSError, ValueError):
            QMessageBox.warning(self.owner, tr("dialog.audio"), tr("message.audio_prepare_failed"))
            return
        self.update_audio_status()

    def start_recording(self) -> None:
        recorder = getattr(self.owner, "recorder", None)
        if recorder and recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            return
        devices = QMediaDevices.audioInputs()
        if not devices:
            QMessageBox.warning(self.owner, tr("dialog.audio"), tr("message.no_microphone"))
            return
        self.target_dir.mkdir(parents=True, exist_ok=True)
        target = self.target_dir / f"{self.filename_prefix}_{uuid.uuid4().hex}.wav"
        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.Wave)
        capture_session = QMediaCaptureSession(self.owner)
        audio_input = QAudioInput(devices[0], self.owner)
        recorder = QMediaRecorder(self.owner)
        recorder.setMediaFormat(media_format)
        recorder.setOutputLocation(QUrl.fromLocalFile(str(target)))
        capture_session.setAudioInput(audio_input)
        capture_session.setRecorder(recorder)
        asset = self.validate_asset(asset_reference(target))
        self.set_asset(asset)
        if asset:
            self.temp_assets.append(asset)
        self.owner.capture_session = capture_session
        self.owner.audio_input = audio_input
        self.owner.recorder = recorder
        recorder.record()
        self.update_audio_status()

    def stop_recording(self) -> None:
        recorder = getattr(self.owner, "recorder", None)
        if recorder:
            recorder.stop()
            finished = getattr(self.owner, "_finished_recorders", None)
            if finished is None:
                finished = []
                self.owner._finished_recorders = finished
            finished.append(recorder)
            self.owner.recorder = None
        self.update_audio_status()

    def play_audio(self) -> bool:
        path = self.asset_path(self.get_asset())
        if not path or not path.exists():
            QMessageBox.warning(self.owner, tr("dialog.audio"), tr("message.no_audio_to_play"))
            return False
        self.audio_player.setSource(QUrl.fromLocalFile(str(path)))
        self.audio_player.play()
        return True

    def delete_audio(self) -> None:
        self.set_asset(None)
        self.update_audio_status()

    def update_audio_status(self) -> None:
        recorder = getattr(self.owner, "recorder", None)
        recording = bool(recorder and recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState)
        asset = self.get_asset()
        key = "status.recording" if recording else ("status.audio_ready" if asset else "status.no_audio")
        self.status_label.setText(tr(key))
        self.record_button.setChecked(recording)
        self.record_button.setDown(recording)
        self.listen_button.setEnabled(bool(asset))
        self.delete_button.setEnabled(bool(asset))
        self.stop_button.setEnabled(recording)
        self.stop_button.setChecked(False)
        self.stop_button.setDown(False)

    def cleanup_temp_assets(self, original_assets: set[str | None]) -> None:
        for asset in self.temp_assets:
            if asset in original_assets:
                continue
            path = self.asset_path(asset)
            if path and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass


class TimelineSlider(QSlider):
    markerClicked = Signal(int)
    seekClicked = Signal(int)

    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self.pause_times: list[int] = []
        self.selected_pause_ms: int | None = None
        self.segment_start_ms = 0
        self.segment_end_ms: int | None = None
        self._press_x: float | None = None
        self._press_marker: int | None = None
        self._dragged = False
        self.setMinimumHeight(42)
        self.setTracking(True)

    def set_pauses(self, pauses: list[PausePoint], selected: int | None) -> None:
        self.pause_times = [pause.time_ms for pause in pauses]
        self.selected_pause_ms = selected
        self.update()

    def set_segment(self, start_ms: int, end_ms: int | None) -> None:
        self.segment_start_ms = max(0, int(start_ms))
        self.segment_end_ms = None if end_ms is None else max(0, int(end_ms))
        self.update()

    def value_from_x(self, x: float) -> int:
        left, right = 12, max(13, self.width() - 12)
        ratio = max(0.0, min(1.0, (x - left) / (right - left)))
        return round(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.maximum() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right = 12, self.width() - 12
        marker_y = self.height() - 18
        span = max(1, self.maximum() - self.minimum())
        start_x = left + ((self.segment_start_ms - self.minimum()) / span) * (right - left)
        effective_end = self.maximum() if self.segment_end_ms is None else self.segment_end_ms
        end_x = left + ((effective_end - self.minimum()) / span) * (right - left)
        start_x = max(left, min(right, start_x))
        end_x = max(left, min(right, end_x))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(45, 55, 70, 55))
        painter.drawRect(QRectF(left, 4, max(0, start_x - left), marker_y - 7))
        painter.drawRect(QRectF(end_x, 4, max(0, right - end_x), marker_y - 7))
        painter.setPen(QPen(QColor("#2f8f5b"), 4))
        painter.drawLine(QPointF(start_x, marker_y - 7), QPointF(end_x, marker_y - 7))
        painter.setPen(QPen(QColor("#8aa0b8"), 1))
        painter.drawLine(QPointF(left, marker_y - 7), QPointF(right, marker_y - 7))
        value_ratio = (self.value() - self.minimum()) / max(1, self.maximum() - self.minimum())
        head_x = left + value_ratio * (right - left)
        painter.setPen(QPen(QColor("#1677C8"), 2))
        painter.drawLine(QPointF(head_x, 6), QPointF(head_x, marker_y - 12))
        painter.setBrush(QColor("#1677C8"))
        painter.setPen(QPen(QColor("#ffffff"), 3))
        painter.drawEllipse(QPointF(head_x, 14), 7, 7)
        font = painter.font(); font.setPointSize(9); painter.setFont(font)
        marker_positions = []
        for pause_ms in self.pause_times:
            x = left + (pause_ms / max(1, self.maximum())) * (right - left)
            marker_positions.append((pause_ms, x))
        for index, (pause_ms, x) in enumerate(marker_positions):
            selected = pause_ms == self.selected_pause_ms
            active = pause_ms >= self.segment_start_ms and (self.segment_end_ms is None or pause_ms < self.segment_end_ms)
            painter.setPen(QPen(QColor("#172033") if selected else QColor("#ffffff"), 4 if selected else 2))
            painter.setBrush(QColor("#EF8B22") if active else QColor("#9aa4b1"))
            size = 18 if selected else 14
            points = [QPointF(x, marker_y - size), QPointF(x + size / 2, marker_y - size / 2), QPointF(x, marker_y), QPointF(x - size / 2, marker_y - size / 2)]
            painter.drawPolygon(points)
            if selected:
                painter.setPen(QColor("#172033"))
                painter.drawText(QRectF(x - 30, marker_y + 1, 60, 18), Qt.AlignmentFlag.AlignCenter, format_time(pause_ms)[3:8])
    def mousePressEvent(self, event) -> None:
        self._press_x = event.position().x()
        self._press_marker = self.marker_at(self._press_x)
        self._dragged = False
        value = self.value_from_x(self._press_x)
        self.setValue(value)
        self.seekClicked.emit(value)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        marker = self.marker_at(event.position().x())
        self.setToolTip(tr("message.pause_at", time=format_time(marker)) if marker is not None else tr("message.drag_video"))
        if self._press_x is not None and abs(event.position().x() - self._press_x) > 4:
            self._dragged = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        marker = self._press_marker
        dragged = self._dragged
        super().mouseReleaseEvent(event)
        if marker is not None and not dragged:
            self.markerClicked.emit(marker)
        self._press_x = None
        self._press_marker = None
        self._dragged = False

    def marker_at(self, x: float) -> int | None:
        if self.maximum() <= 0:
            return None
        left, right = 12, self.width() - 12
        nearest = None
        nearest_distance = 9999.0
        for pause_ms in self.pause_times:
            marker_x = left + (pause_ms / max(1, self.maximum())) * (right - left)
            distance = abs(marker_x - x)
            if distance < nearest_distance:
                nearest = pause_ms
                nearest_distance = distance
        return nearest if nearest is not None and nearest_distance <= 16 else None

class HotspotContentDialog(QDialog):
    CATEGORY_OPTIONS = tuple(COMMUNICATION_CATEGORIES.items())

    def __init__(self, hotspot: Hotspot, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.hotspot_content"))
        self.hotspot = deepcopy(hotspot)
        self.original_audio_asset = hotspot.audio_asset
        self.pending_audio_asset = hotspot.audio_asset
        self.temp_audio_files: list[Path] = []
        self.recorder: QMediaRecorder | None = None
        self.capture_session: QMediaCaptureSession | None = None
        self.audio_input: QAudioInput | None = None
        self.audio_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_player.setAudioOutput(self.audio_output)
        self.audio_controller: DialogAudioController | None = None
        self.setMinimumWidth(520)
        self.setMaximumWidth(580)
        self._updating_message = False
        self.message = QTextEdit()
        self.message.setPlainText(self.hotspot.message_text)
        self.message.setFixedHeight(62)
        self.message.setAcceptRichText(False)
        self.message.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.message.setTabChangesFocus(True)
        self.message.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.message.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.message.textChanged.connect(self.enforce_message_limit)
        self.message_counter = QLabel(message_counter_text(self.hotspot.message_text))
        self.message_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.message_counter.setObjectName("messageCounter")
        self.message_counter.setToolTip(tr("message.max_characters", count=HOTSPOT_MESSAGE_MAX_CHARS))
        self.category = QComboBox()
        for value, _label in self.CATEGORY_OPTIONS:
            self.category.addItem(tr(f"category.{value}"), value)
        index = self.category.findData(self.hotspot.communication_category)
        self.category.setCurrentIndex(max(0, index))
        self.show_message = QCheckBox(tr("option.show_text"))
        self.show_message.setChecked(self.hotspot.show_message_text)
        self.font_family = QFontComboBox()
        if self.hotspot.font_family:
            self.font_family.setCurrentFont(QFont(self.hotspot.font_family))
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 48)
        self.font_size.setSuffix(" px")
        self.font_size.setValue(validate_font_size(self.hotspot.font_size_px))
        self.font_bold = QCheckBox(tr("option.bold"))
        self.font_bold.setChecked(bool(self.hotspot.font_bold))
        self.uppercase = QCheckBox(tr("option.uppercase"))
        self.uppercase.setChecked(bool(self.hotspot.uppercase))
        self.text_color_btn = QPushButton()
        self.background_color_btn = QPushButton()
        self.background_opacity = QSpinBox()
        self.background_opacity.setRange(0, 100)
        self.background_opacity.setSuffix(" %")
        self.background_opacity.setValue(validate_opacity_percent(self.hotspot.background_opacity))
        self.text_color_btn.clicked.connect(lambda: self.choose_text_style_color("text"))
        self.background_color_btn.clicked.connect(lambda: self.choose_text_style_color("background"))
        self.update_text_style_color_buttons()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        message_box = QVBoxLayout()
        message_box.setSpacing(3)
        message_box.addWidget(self.message)
        message_box.addWidget(self.message_counter)
        form.addRow(tr("field.message"), message_box)
        form.addRow(tr("field.font"), self.font_family)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_size)
        font_row.addWidget(self.font_bold)
        font_row.addStretch()
        form.addRow(tr("field.size_style"), font_row)
        form.addRow("", self.uppercase)
        form.addRow(tr("field.text_color"), self.text_color_btn)
        form.addRow(tr("field.text_background"), self.background_color_btn)
        form.addRow(tr("field.background_opacity"), self.background_opacity)
        form.addRow(tr("field.category"), self.category)
        form.addRow("", self.show_message)
        color_box = QHBoxLayout()
        color_box.setSpacing(6)
        color_box.addWidget(QLabel(tr("field.color")))
        self.color_swatch = QPushButton("")
        self.color_swatch.setFixedSize(26, 26)
        self.color_swatch.setEnabled(False)
        self.color_swatch.setAccessibleName(tr("tooltip.current_hotspot_color"))
        color_box.addWidget(self.color_swatch)
        self.change_color_btn = QPushButton(tr("button.change_color"))
        self.change_color_btn.setToolTip(tr("tooltip.choose_hotspot_color"))
        self.change_color_btn.setAccessibleName(tr("tooltip.change_hotspot_color"))
        color_box.addWidget(self.change_color_btn)
        self.color_menu = QMenu(self)
        self.color_actions: dict[str, QAction] = {}
        for name, color in HOTSPOT_PALETTE.items():
            localized_color = tr(f"color.{name}")
            action = QAction(localized_color, self)
            action.setCheckable(True)
            action.setIcon(color_icon(color))
            action.setToolTip(localized_color)
            action.triggered.connect(lambda _=False, c=color: self.select_color(c))
            self.color_actions[color] = action
            self.color_menu.addAction(action)
        self.change_color_btn.clicked.connect(self.open_color_menu)
        color_box.addStretch()
        audio_box = QVBoxLayout()
        audio_box.setSpacing(6)
        audio_box.addWidget(QLabel(tr("field.audio")))
        audio_buttons = QHBoxLayout()
        audio_buttons.setSpacing(6)
        self.choose_audio_btn = QPushButton(tr("button.select_audio"))
        self.record_btn = QPushButton(tr("button.record"))
        self.stop_record_btn = QPushButton(tr("button.stop"))
        self.listen_btn = QPushButton(tr("button.listen"))
        self.delete_audio_btn = QPushButton(tr("button.delete_audio"))
        for btn, tip in [
            (self.choose_audio_btn, tr("tooltip.select_audio")),
            (self.record_btn, tr("tooltip.record_audio")),
            (self.stop_record_btn, tr("tooltip.stop_recording")),
            (self.listen_btn, tr("tooltip.listen_audio")),
            (self.delete_audio_btn, tr("tooltip.delete_audio")),
        ]:
            btn.setToolTip(tip)
            btn.setAccessibleName(tip)
            btn.setMinimumWidth(74)
            audio_buttons.addWidget(btn)
        audio_buttons.addStretch()
        self.choose_audio_btn.clicked.connect(self.choose_audio)
        self.record_btn.clicked.connect(self.start_recording)
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.listen_btn.clicked.connect(self.play_audio)
        self.delete_audio_btn.clicked.connect(self.delete_audio)
        self.audio_status = QLabel(tr("status.no_audio"))
        self.tts_enabled = QCheckBox(tr("option.tts"))
        self.tts_enabled.setChecked(bool(getattr(self.hotspot, HOTSPOT_TTS_FIELD, True)))
        self.audio_controller = DialogAudioController(
            self,
            get_asset=lambda: self.pending_audio_asset,
            set_asset=self.set_pending_audio_asset,
            validate_asset=validate_audio_asset,
            target_dir=AUDIO_DIR,
            filename_prefix="hotspot_audio",
            audio_player=self.audio_player,
            status_label=self.audio_status,
            record_button=self.record_btn,
            listen_button=self.listen_btn,
            delete_button=self.delete_audio_btn,
            stop_button=self.stop_record_btn,
        )
        audio_box.addLayout(audio_buttons)
        audio_box.addWidget(self.audio_status)
        audio_box.addWidget(self.tts_enabled)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("button.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("button.cancel"))
        buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addLayout(form)
        layout.addLayout(color_box)
        layout.addLayout(audio_box)
        layout.addWidget(buttons)
        self.update_color_buttons()
        self.update_audio_status()
        self.message.setFocus()
        localize_widget_tree(self)
        self.setWindowTitle(tr("dialog.hotspot_content"))

    def choose_text_style_color(self, target: str) -> None:
        current = self.hotspot.text_color if target == "text" else self.hotspot.background_color
        selected = QColorDialog.getColor(QColor(current), self, tr("field.text_color" if target == "text" else "field.text_background"))
        if not selected.isValid():
            return
        if target == "text":
            self.hotspot.text_color = selected.name().upper()
        else:
            self.hotspot.background_color = selected.name().upper()
        self.update_text_style_color_buttons()

    def update_text_style_color_buttons(self) -> None:
        text_color = validate_hex_color(self.hotspot.text_color, HOTSPOT_TEXT_COLOR_DEFAULT)
        background_color = validate_hex_color(self.hotspot.background_color, HOTSPOT_TEXT_BACKGROUND_DEFAULT)
        self.text_color_btn.setText(text_color)
        self.text_color_btn.setStyleSheet(f"background:{text_color}; color:{'#000000' if QColor(text_color).lightness() > 150 else '#FFFFFF'}; padding:4px;")
        self.background_color_btn.setText(background_color)
        self.background_color_btn.setStyleSheet(f"background:{background_color}; color:{'#000000' if QColor(background_color).lightness() > 150 else '#FFFFFF'}; padding:4px;")

    def enforce_message_limit(self) -> None:
        if self._updating_message:
            return
        text = self.message.toPlainText()
        if len(text) > HOTSPOT_MESSAGE_MAX_CHARS:
            cursor = self.message.textCursor()
            position = min(cursor.position(), HOTSPOT_MESSAGE_MAX_CHARS)
            self._updating_message = True
            self.message.setPlainText(clamp_hotspot_message(text))
            cursor = self.message.textCursor()
            cursor.setPosition(position)
            self.message.setTextCursor(cursor)
            self._updating_message = False
            text = self.message.toPlainText()
        self.message_counter.setText(message_counter_text(text))

    def select_color(self, color: str) -> None:
        self.hotspot.color = color.upper()
        self.update_color_buttons()
        if self.parent() and hasattr(self.parent(), "logger"):
            self.parent().logger.write("hotspot_color_selected", color=self.hotspot.color)

    def open_color_menu(self) -> None:
        self.color_menu.exec(self.change_color_btn.mapToGlobal(self.change_color_btn.rect().bottomLeft()))

    def update_color_buttons(self) -> None:
        self.color_swatch.setStyleSheet(f"background:{self.hotspot.color}; border:1px solid #7d8999; border-radius:4px;")
        self.color_swatch.setToolTip(f"Color actual {self.hotspot.color}")
        for color, action in self.color_actions.items():
            selected = color.upper() == self.hotspot.color.upper()
            action.setChecked(selected)
            action.setIcon(color_icon(color, selected))

    def set_pending_audio_asset(self, asset: str | None) -> None:
        self.pending_audio_asset = validate_audio_asset(asset)

    def _absolute_audio_path(self, asset: str | None) -> Path | None:
        return self.audio_controller.asset_path(asset) if self.audio_controller else None

    def update_audio_status(self) -> None:
        if self.audio_controller:
            self.audio_controller.update_audio_status()

    def choose_audio(self) -> None:
        if self.audio_controller:
            self.audio_controller.choose_audio()

    def start_recording(self) -> None:
        if not self.audio_controller:
            return
        had_recorder = self.recorder is not None
        self.audio_controller.start_recording()
        if self.recorder is None and not had_recorder:
            if self.parent() and hasattr(self.parent(), "logger"):
                self.parent().logger.write("audio_record_error", reason="no_input_device")
            return
        if self.parent() and hasattr(self.parent(), "logger"):
            self.parent().logger.write("audio_record_started", audio_asset=self.pending_audio_asset)

    def stop_recording(self) -> None:
        if self.audio_controller:
            self.audio_controller.stop_recording()
        if self.parent() and hasattr(self.parent(), "logger"):
            self.parent().logger.write("audio_record_stopped", audio_asset=self.pending_audio_asset)

    def play_audio(self) -> None:
        played = self.audio_controller.play_audio() if self.audio_controller else False
        if played and self.parent() and hasattr(self.parent(), "logger"):
            self.parent().logger.write("audio_preview_played", audio_asset=self.pending_audio_asset)

    def delete_audio(self) -> None:
        old = self.pending_audio_asset
        if self.audio_controller:
            self.audio_controller.delete_audio()
        if self.parent() and hasattr(self.parent(), "logger"):
            self.parent().logger.write("audio_deleted", audio_asset=old)

    def reject(self) -> None:
        if self.audio_controller:
            self.audio_controller.cleanup_temp_assets({self.original_audio_asset})
        super().reject()

    def result_hotspot(self) -> Hotspot:
        self.hotspot.message_text = clamp_hotspot_message(self.message.toPlainText())
        self.hotspot.communication_category = str(self.category.currentData())
        self.hotspot.show_message_text = self.show_message.isChecked()
        self.hotspot.audio_asset = validate_audio_asset(self.pending_audio_asset)
        setattr(self.hotspot, HOTSPOT_TTS_FIELD, self.tts_enabled.isChecked())
        selected_family = self.font_family.currentFont().family()
        self.hotspot.font_family = "" if not selected_family else selected_family
        self.hotspot.font_size_px = validate_font_size(self.font_size.value())
        self.hotspot.font_bold = self.font_bold.isChecked()
        self.hotspot.uppercase = self.uppercase.isChecked()
        self.hotspot.text_color = validate_hex_color(self.hotspot.text_color, HOTSPOT_TEXT_COLOR_DEFAULT)
        self.hotspot.background_color = validate_hex_color(self.hotspot.background_color, HOTSPOT_TEXT_BACKGROUND_DEFAULT)
        self.hotspot.background_opacity = validate_opacity_percent(self.background_opacity.value())
        if self.audio_controller:
            self.audio_controller.temp_assets.clear()
        return self.hotspot


class SupportConfigDialog(QDialog):
    TEXT_MAX_CHARS = 40

    def __init__(self, support: SupportItem, slot_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.configure_support", name=slot_name))
        self.support = deepcopy(support)
        self.slot_name = slot_name
        self.original_assets = {support.image_asset, support.audio_asset}
        self.temp_assets: list[str] = []
        self.recorder = None
        self.capture_session = None
        self.audio_input = None
        self.audio_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_player.setAudioOutput(self.audio_output)
        self.setMinimumWidth(600)

        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setFixedHeight(72)
        self.text_edit.setPlainText(self.support.text)
        self.text_edit.textChanged.connect(self.enforce_text_limit)
        self.text_counter = QLabel()
        self.text_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.text_counter.setToolTip(tr("message.max_characters", count=self.TEXT_MAX_CHARS))

        self.category = QComboBox()
        for value in COMMUNICATION_CATEGORIES:
            self.category.addItem(tr(f"category.{value}"), value)
        category_index = self.category.findData(validate_category(self.support.communication_category))
        self.category.setCurrentIndex(max(0, category_index))

        self.image_preview = AspectRatioPixmapLabel(tr("status.no_image"))
        self.image_preview.setFixedSize(240, 135)
        self.choose_image_btn = QPushButton(tr("button.select_image"))
        self.remove_image_btn = QPushButton(tr("button.delete_image"))
        self.choose_image_btn.clicked.connect(self.choose_image)
        self.remove_image_btn.clicked.connect(self.remove_image)

        self.choose_audio_btn = QPushButton(tr("button.select_audio"))
        self.record_btn = QPushButton(tr("button.record"))
        self.stop_record_btn = QPushButton(tr("button.stop"))
        self.listen_btn = QPushButton(tr("button.listen"))
        self.delete_audio_btn = QPushButton(tr("button.delete_audio"))
        self.audio_status = QLabel(tr("status.no_audio"))
        self.audio_controller = DialogAudioController(
            self,
            get_asset=lambda: self.support.audio_asset,
            set_asset=self.set_support_audio_asset,
            validate_asset=validate_support_asset,
            target_dir=SUPPORTS_DIR / "audio",
            filename_prefix="support",
            audio_player=self.audio_player,
            status_label=self.audio_status,
            record_button=self.record_btn,
            listen_button=self.listen_btn,
            delete_button=self.delete_audio_btn,
            stop_button=self.stop_record_btn,
        )
        self.choose_audio_btn.clicked.connect(self.choose_audio)
        self.record_btn.clicked.connect(self.start_recording)
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.listen_btn.clicked.connect(self.play_audio)
        self.delete_audio_btn.clicked.connect(self.delete_audio)
        self.tts_enabled = QCheckBox(tr("option.tts"))
        self.tts_enabled.setChecked(bool(self.support.tts_enabled))
        self.visible = QCheckBox(tr("option.visible_user"))
        self.visible.setChecked(bool(self.support.visible))

        form = QFormLayout()
        text_box = QWidget(); text_l = QVBoxLayout(text_box); text_l.setContentsMargins(0,0,0,0)
        text_l.addWidget(self.text_edit); text_l.addWidget(self.text_counter)
        form.addRow(tr("field.text"), text_box)
        form.addRow(tr("field.category"), self.category)
        image_box = QWidget(); image_l = QVBoxLayout(image_box); image_l.setContentsMargins(0,0,0,0)
        image_buttons = QHBoxLayout(); image_buttons.addWidget(self.choose_image_btn); image_buttons.addWidget(self.remove_image_btn); image_buttons.addStretch()
        image_l.addLayout(image_buttons); image_l.addWidget(self.image_preview)
        form.addRow(tr("field.image"), image_box)
        audio_box = QWidget(); audio_l = QVBoxLayout(audio_box); audio_l.setContentsMargins(0,0,0,0)
        audio_buttons = QHBoxLayout()
        for b in (self.choose_audio_btn,self.record_btn,self.stop_record_btn,self.listen_btn,self.delete_audio_btn): audio_buttons.addWidget(b)
        audio_l.addLayout(audio_buttons); audio_l.addWidget(self.audio_status); audio_l.addWidget(self.tts_enabled)
        form.addRow(tr("field.audio"), audio_box)
        form.addRow("", self.visible)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("button.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("button.cancel"))
        delete_btn = buttons.addButton(tr("button.delete_support"), QDialogButtonBox.ButtonRole.DestructiveRole)
        delete_btn.clicked.connect(self.clear_support)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout=QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)
        self.enforce_text_limit(); self.update_image_preview(); self.update_audio_status()
        localize_widget_tree(self)
        self.setWindowTitle(tr("dialog.configure_support", name=slot_name))

    def asset_path(self, asset):
        if not asset: return None
        try: return asset_path(validate_support_asset(asset))
        except ValueError: return None

    def make_portable_asset(self, source: Path, kind: str) -> str:
        source=source.resolve()
        if source.is_relative_to(USER_ROOT) or source.is_relative_to(ROOT):
            try: return validate_support_asset(asset_reference(source)) or ""
            except ValueError: pass
        target_dir=SUPPORTS_DIR/("images" if kind=="image" else "audio"); target_dir.mkdir(parents=True,exist_ok=True)
        target=target_dir/f"support_{uuid.uuid4().hex}{source.suffix.lower()}"; shutil.copy2(source,target)
        asset=validate_support_asset(asset_reference(target)) or ""; self.temp_assets.append(asset); return asset

    def enforce_text_limit(self):
        text=self.text_edit.toPlainText()[:self.TEXT_MAX_CHARS]
        if text != self.text_edit.toPlainText(): self.text_edit.setPlainText(text)
        self.text_counter.setText(f"{len(text)}/{self.TEXT_MAX_CHARS}")

    def choose_image(self):
        path,_=QFileDialog.getOpenFileName(self,tr("button.select_image").rstrip("…"),str(ROOT),tr("file.image_filter"))
        if path: self.support.image_asset=self.make_portable_asset(Path(path),"image"); self.update_image_preview()
    def remove_image(self): self.support.image_asset=None; self.update_image_preview()
    def update_image_preview(self):
        path=self.asset_path(self.support.image_asset)
        if path and path.exists():
            pix=QPixmap(str(path))
            if not pix.isNull():
                self.image_preview.setText("")
                self.image_preview.set_original_pixmap(pix)
                return
        self.image_preview.clear_original_pixmap(); self.image_preview.setText(tr("status.no_image"))
    def set_support_audio_asset(self, asset: str | None) -> None:
        self.support.audio_asset = validate_support_asset(asset)

    def choose_audio(self):
        self.audio_controller.choose_audio()

    def start_recording(self):
        self.audio_controller.start_recording()

    def stop_recording(self):
        self.audio_controller.stop_recording()

    def play_audio(self):
        self.audio_controller.play_audio()

    def delete_audio(self):
        self.audio_controller.delete_audio()

    def update_audio_status(self):
        self.audio_controller.update_audio_status()

    def clear_support(self):
        self.support=SupportItem(self.support.support_id,self.slot_name,position=self.support.position); self.accept()
    def reject(self):
        self.audio_controller.cleanup_temp_assets(self.original_assets)
        for asset in self.temp_assets:
            if asset in self.original_assets: continue
            path=self.asset_path(asset)
            if path and path.exists():
                try: path.unlink()
                except OSError: pass
        super().reject()
    def result_support(self):
        result=deepcopy(self.support)
        # El identificador/nombre del slot es interno; el usuario solo define el contenido.
        result.label=self.slot_name
        result.text=self.text_edit.toPlainText().strip()[:self.TEXT_MAX_CHARS]
        result.image_asset=validate_support_asset(result.image_asset); result.audio_asset=validate_support_asset(result.audio_asset); result.tts_enabled=self.tts_enabled.isChecked(); result.visible=bool(self.visible.isChecked() and result.is_configured()); result.communication_category=str(self.category.currentData())
        self.audio_controller.temp_assets.clear(); self.temp_assets.clear(); return result


class HotspotItem(QGraphicsObject):
    changed = Signal(str, dict, dict)
    editRequested = Signal(str)
    activated = Signal(str)

    def __init__(self, hotspot: Hotspot, logger: JsonlLogger) -> None:
        super().__init__()
        self.hotspot = hotspot
        self.logger = logger
        self.preview_mode = False
        self._rect = QRectF(0, 0, 120, 90)
        self._drag_mode: str | None = None
        self._drag_start = QPointF()
        self._start_pixel_rect = (0.0, 0.0, 120.0, 90.0)
        self.invalid_geometry = False
        self.setFlags(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable | QGraphicsObject.GraphicsItemFlag.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self.apply_from_model()

    def apply_from_model(self) -> None:
        self.set_pixel_rect(normalized_to_pixel(self.hotspot.geometry, FRAME_SIZE), push_model=False)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-HANDLE, -HANDLE, HANDLE, HANDLE)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = qcolor(self.hotspot.color)
        fill = QColor(color)
        fill.setAlpha(opacity_percent_to_alpha(self.hotspot.fill_opacity))
        painter.setBrush(fill)
        painter.setPen(QPen(QColor("#D50000") if self.invalid_geometry else color, 5 if self.invalid_geometry else 3))
        if self.hotspot.shape == "ellipse":
            painter.drawEllipse(self._rect)
        else:
            painter.drawRoundedRect(self._rect, 8, 8)
        if self.isSelected() and not self.preview_mode:
            painter.setPen(QPen(QColor("#00E5FF"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._rect)
            painter.setPen(QPen(QColor(DEFAULT_HOTSPOT_COLOR), 2))
            painter.setBrush(QColor("#FFFFFF"))
            for handle in self.handle_rects().values():
                painter.drawRect(handle)

    def handle_rects(self) -> dict[str, QRectF]:
        r = self._rect
        points = {"nw": r.topLeft(), "n": QPointF(r.center().x(), r.top()), "ne": r.topRight(), "e": QPointF(r.right(), r.center().y()), "se": r.bottomRight(), "s": QPointF(r.center().x(), r.bottom()), "sw": r.bottomLeft(), "w": QPointF(r.left(), r.center().y())}
        return {name: QRectF(point.x() - HANDLE / 2, point.y() - HANDLE / 2, HANDLE, HANDLE) for name, point in points.items()}

    def handle_at(self, pos: QPointF) -> str | None:
        if self.preview_mode:
            return None
        for name, rect in self.handle_rects().items():
            if rect.contains(pos):
                return name
        return None

    def pixel_rect(self) -> tuple[float, float, float, float]:
        return (self.pos().x(), self.pos().y(), self._rect.width(), self._rect.height())

    def set_pixel_rect(self, rect: tuple[float, float, float, float], push_model: bool = True) -> None:
        x, y, width, height = rect
        self.prepareGeometryChange()
        self.setPos(QPointF(x, y))
        self._rect = QRectF(0, 0, max(MIN_SIZE_PX, width), max(MIN_SIZE_PX, height))
        if push_model:
            self.hotspot.geometry = pixel_to_normalized(self.pixel_rect(), FRAME_SIZE)
        self.update()

    def set_preview_mode(self, enabled: bool) -> None:
        self.preview_mode = enabled
        self.setSelected(False if enabled else self.isSelected())
        self.update()

    def set_invalid_geometry(self, invalid: bool) -> None:
        self.invalid_geometry = invalid
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:
        if self.preview_mode:
            self.activated.emit(self.hotspot.hotspot_id)
        else:
            self.editRequested.emit(self.hotspot.hotspot_id)
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.preview_mode:
            self.activated.emit(self.hotspot.hotspot_id)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_mode = self.handle_at(event.pos()) or "move"
            self._drag_start = event.scenePos()
            self._start_pixel_rect = self.pixel_rect()
            self.set_invalid_geometry(False)
            self.setSelected(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.preview_mode:
            return
        if not self._drag_mode:
            return super().mouseMoveEvent(event)
        delta = (event.scenePos().x() - self._drag_start.x(), event.scenePos().y() - self._drag_start.y())
        rect = move_pixel_rect(self._start_pixel_rect, delta, FRAME_SIZE) if self._drag_mode == "move" else resize_pixel_rect(self._start_pixel_rect, self._drag_mode, delta, FRAME_SIZE, MIN_SIZE_PX)
        self.set_pixel_rect(rect)
        scene_parent = self.scene().parent() if self.scene() else None
        if scene_parent and hasattr(scene_parent, "candidate_overlaps_pause"):
            self.set_invalid_geometry(scene_parent.candidate_overlaps_pause(self.hotspot))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self.preview_mode:
            event.accept()
            return
        before = pixel_to_normalized(self._start_pixel_rect, FRAME_SIZE)
        after = pixel_to_normalized(self.pixel_rect(), FRAME_SIZE)
        self.hotspot.geometry = after
        if before != after:
            self.changed.emit(self.hotspot.hotspot_id, before, after)
            self.logger.write("hotspot_geometry_changed", hotspot_id=self.hotspot.hotspot_id, before=before, after=after)
        self._drag_mode = None
        self.set_invalid_geometry(False)
        event.accept()


class VideoView(QGraphicsView):
    resized = Signal()

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor("#edf1f6"))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMouseTracking(True)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        painter.setPen(QPen(QColor("#9aa9bb"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, FRAME_WIDTH, FRAME_HEIGHT))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(QRectF(0, 0, FRAME_WIDTH, FRAME_HEIGHT), Qt.AspectRatioMode.KeepAspectRatio)
        self.resized.emit()

class EditorWindow(QMainWindow):
    def __init__(self, json_path: Path | None = None, auto_show: bool = False) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(str(APP_ICON)))
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        self.logger = JsonlLogger(LOG_PATH)
        self.project = default_project()
        self.project_path: Path | None = None
        self.pauses: list[PausePoint] = []
        self.videos: list[VideoEntry] = [VideoEntry("video-1", tr("video.automatic_name", number=1), "", self.pauses)]
        self.current_video_index = 0
        self.draft_start: int | None = None
        self.draft_end: int | None = None
        self._segment_draft_video_id = self.videos[0].video_id
        # Estado de edición y estado de reproducción son independientes.
        # selected_event_id solo pertenece al modo edición.
        # active_event_id solo existe mientras un PauseEvent está activo en modo usuario.
        self.selected_event_id: str | None = None
        self.active_event_id: str | None = None
        # Compatibilidad visual temporal con TimelineWidget; deja de ser la fuente de verdad.
        self.selected_pause_ms: int | None = None
        self.items: dict[str, HotspotItem] = {}
        self.current_hotspot_id: str | None = None
        self.active_hotspot_id: str | None = None
        self.active_support_id: str | None = None
        self.mode = "select"
        self.preview_mode = False
        self.pause_states: dict[int, str] = {}
        self.duration_ms = 0
        self.playback_controller = PlaybackController()
        self._closing = False
        self._last_drag_seek_ms = -100000
        self._manual_seek_target_ms: int | None = None
        self._creating = False
        self._create_shape = "rectangle"
        self._create_start: QPointF | None = None
        self._create_rect = None
        self.video_thumbnails: dict[str, QPixmap] = {}
        self.thumbnail_requests: set[str] = set()
        self.thumbnail_extractors: list[tuple[QMediaPlayer, QVideoSink]] = []
        self.last_primed_video_id: str | None = None
        self.history = History()
        self.research = ResearchSessionManager(RESULTS_DIR / "sessions")
        self.users_manager = UsersManager(USERS_CSV)
        self._research_completed_videos: set[str] = set()
        self.language = load_language(ROOT)
        self.setWindowTitle(PRODUCT_TITLE)
        self.make_menu()
        self.scene = QGraphicsScene(0, 0, FRAME_WIDTH, FRAME_HEIGHT, self)
        self.poster_item = QGraphicsPixmapItem()
        self.poster_item.setZValue(-1100)
        self.scene.addItem(self.poster_item)
        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(QSize(FRAME_WIDTH, FRAME_HEIGHT))
        self.video_item.setZValue(-1000)
        self.scene.addItem(self.video_item)
        self.view = VideoView(self.scene)
        self.view.resized.connect(self.update_output_geometry)
        self.view.viewport().installEventFilter(self)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_item)
        # Un proyecto nuevo de ANNA comienza sin vídeo.
        self.player.setSource(QUrl())
        self.hotspot_audio_player = QMediaPlayer(self)
        self.hotspot_audio_output = QAudioOutput(self)
        self.hotspot_audio_player.setAudioOutput(self.hotspot_audio_output)
        self.support_tts = (
            QTextToSpeech("sapi", self) if sys.platform == "win32" else QTextToSpeech(self)
        ) if QTextToSpeech is not None else None
        self.configure_tts_locale()
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.playbackStateChanged.connect(self.update_play_button)
        self.top_label = QLabel(PRODUCT_TITLE)
        self.top_label.setObjectName("topLabel")
        self.selected_label = QLabel(tr("label.selected_pause_none"))
        self.mode_label = QLabel(tr("mode.professional"))
        self.mode_label.setObjectName("modeLabel")
        self.participant_selector = QComboBox()
        self.participant_selector.setObjectName("userLabel")
        self.participant_selector.setMinimumWidth(150)
        self.participant_selector.currentIndexChanged.connect(self.on_participant_selector_changed)
        self._updating_participant_selector = False
        self.user_label = self.participant_selector
        self.mode_quick_btn = QPushButton("")
        self.mode_quick_btn.setObjectName("modeQuickButton")
        self.mode_quick_btn.setFixedSize(34, 26)
        self.mode_quick_btn.clicked.connect(self.handle_mode_quick_button)
        # Control interno heredado: conserva la lógica de transición ya probada,
        # pero no forma parte de la interfaz visible.
        self.preview_btn = QPushButton()
        self.preview_btn.setCheckable(True)
        self.preview_btn.setToolTip(tr("tooltip.switch_mode"))
        self.preview_btn.hide()

        # Estado textual + botón compacto ON/OFF. La activación solo se
        # puede cambiar desde el modo profesional.
        self.research_label = QLabel(tr("label.research"))
        self.research_label.setObjectName("researchLabel")
        self.research_quick_btn = QPushButton("OFF")
        self.research_quick_btn.setObjectName("researchQuickButton")
        self.research_quick_btn.setFixedSize(54, 26)
        self.research_quick_btn.clicked.connect(self.toggle_research)

        # Anotaciones profesionales agrupadas en la zona superior derecha.
        # Los atajos de teclado se conservan como complemento.
        self.professional_annotation_bar = QWidget()
        self.professional_annotation_bar.setObjectName("professionalAnnotationBar")
        annotation_layout = QHBoxLayout(self.professional_annotation_bar)
        annotation_layout.setContentsMargins(0, 0, 0, 0)
        annotation_layout.setSpacing(4)
        self.professional_annotation_buttons: dict[str, QPushButton] = {}
        for mark, label in (
            ("turn", tr("annotation.turn")),
            ("adequate", tr("annotation.appropriate")),
            ("review", tr("annotation.review")),
        ):
            button = QPushButton(label)
            button.setObjectName("professionalAnnotationButton")
            button.setFixedHeight(30)
            button.setMinimumWidth(82)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, value=mark: self.handle_professional_annotation(value))
            annotation_layout.addWidget(button)
            self.professional_annotation_buttons[mark] = button
        self._research_shortcuts: list[QShortcut] = []
        self.install_research_shortcuts()
        self.support_visibility = QCheckBox(tr("label.supports"))
        self.support_visibility.setChecked(True)
        self.support_visibility.toggled.connect(lambda _: self.refresh_support_panel())
        self.navigation_visibility = QCheckBox(tr("label.navigation"))
        self.navigation_visibility.setChecked(True)
        self.navigation_visibility.toggled.connect(lambda checked: self.video_nav.setVisible(checked))
        self.show_hotspots_toggle = QCheckBox(tr("label.show_hotspots"))
        self.show_hotspots_toggle.setChecked(True)
        self.show_hotspots_toggle.toggled.connect(lambda _: self.refresh_hotspot_visibility())
        top = QWidget()
        top.setObjectName("topBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 3, 10, 3)
        top_layout.setSpacing(8)
        top_layout.addWidget(self.top_label)
        top_layout.addStretch(1)
        top_layout.addWidget(self.navigation_visibility)
        top_layout.addWidget(self.support_visibility)
        top_layout.addWidget(self.show_hotspots_toggle)
        top_layout.addWidget(self.participant_selector)
        top_layout.addWidget(self.mode_label)
        top_layout.addWidget(self.professional_annotation_bar)
        top_layout.addWidget(self.research_quick_btn)
        top_layout.addWidget(self.mode_quick_btn)

        top_container = QWidget()
        top_container_layout = QVBoxLayout(top_container)
        top_container_layout.setContentsMargins(0, 0, 0, 0)
        top_container_layout.setSpacing(1)
        top_container_layout.addWidget(top)
        self.output_label = QLabel("")
        self.output_label.setObjectName("hotspotBubble")
        self.output_label.setWordWrap(False)
        self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_label.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        self.output_label.setStyleSheet("background:#111111;color:#FFFF00;font-size:20px;font-weight:800;padding:6px 10px;border:0;border-radius:5px;")
        self.output_proxy = self.scene.addWidget(self.output_label)
        self.output_proxy.setZValue(9998)
        self.output_proxy.hide()
        self.video_nav = QWidget()
        self.video_nav.setObjectName("videoNav")
        self.video_nav_layout = QHBoxLayout(self.video_nav)
        self.video_nav_layout.setContentsMargins(10, 5, 10, 5)
        self.video_nav_layout.setSpacing(8)
        video_column = QWidget()
        video_column.setObjectName("videoStage")
        video_layout = QVBoxLayout(video_column)
        video_layout.setContentsMargins(24, 8, 24, 8)
        video_layout.setSpacing(4)
        self.view.setObjectName("videoView")
        video_layout.addWidget(self.view, 1)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        self.tool_panel = self.make_tools()
        self.tool_panel.setMinimumWidth(168)
        self.tool_panel.setMaximumWidth(168)
        content.addWidget(self.tool_panel, 0)

        # El área central es la única columna expansible.
        content.addWidget(video_column, 1)

        self.support_panel = self.make_support_panel()
        self.support_panel.setMinimumWidth(224)
        self.support_panel.setMaximumWidth(224)
        content.addWidget(self.support_panel, 0)
        center = QWidget()
        center.setObjectName("workspace")
        center.setLayout(content)
        outer = QWidget()
        outer.setObjectName("root")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(8, 6, 8, 6)
        outer_layout.setSpacing(6)
        outer_layout.addWidget(top_container)
        outer_layout.addWidget(self.video_nav)
        outer_layout.addWidget(center, 1)
        outer_layout.addWidget(self.make_controls())
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("rootScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(outer)
        self.setCentralWidget(self.scroll_area)
        self.apply_styles()
        self.retranslate_ui()
        if json_path:
            self.load_json(json_path)
        self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.refresh_video_nav()
        self.refresh_support_panel()
        self.update_mode_controls()
        self.update_research_controls()
        self.history.push(self.snapshot())
        self.logger.write("temporal_editor_started")
        self.prime_current_video_frame()
        QTimer.singleShot(0, self.update_output_geometry)

    @property
    def _playback_running(self) -> bool:
        return self.playback_controller.running

    @_playback_running.setter
    def _playback_running(self, value: bool) -> None:
        self.playback_controller.running = bool(value)

    @property
    def _seeking(self) -> bool:
        return self.playback_controller.seeking

    @_seeking.setter
    def _seeking(self, value: bool) -> None:
        self.playback_controller.seeking = bool(value)

    @property
    def _seek_start_ms(self) -> int:
        return self.playback_controller.seek_start_ms

    @_seek_start_ms.setter
    def _seek_start_ms(self, value: int) -> None:
        self.playback_controller.seek_start_ms = int(value)

    @property
    def _last_position_ms(self) -> int:
        return self.playback_controller.previous_ms

    @_last_position_ms.setter
    def _last_position_ms(self, value: int) -> None:
        self.playback_controller.previous_ms = int(value)

    @property
    def _temporal_mode(self) -> PlaybackMode:
        return self.playback_controller.mode

    @_temporal_mode.setter
    def _temporal_mode(self, value: PlaybackMode) -> None:
        self.playback_controller.mode = value

    @property
    def _pending_continue_position_ms(self) -> int | None:
        return self.playback_controller.pending_continue_position_ms

    @_pending_continue_position_ms.setter
    def _pending_continue_position_ms(self, value: int | None) -> None:
        self.playback_controller.pending_continue_position_ms = (
            None if value is None else int(value)
        )

    def make_menu(self) -> None:
        self.file_menu = self.menuBar().addMenu(tr("menu.file"))
        self.mode_menu = self.menuBar().addMenu(tr("menu.mode"))
        file_menu = self.file_menu
        mode_menu = self.mode_menu

        new_action = QAction(tr("action.new_project"), self)
        new_action.triggered.connect(self.new_project)
        self.new_project_action = new_action
        open_action = QAction(tr("action.open_project"), self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_json)
        self.open_project_action = open_action
        save_action = QAction(tr("action.save"), self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_json)
        self.save_project_action = save_action
        save_as_action = QAction(tr("action.save_as"), self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(lambda: self.save_json(force_dialog=True))
        self.save_project_as_action = save_as_action
        add_video_action = QAction(tr("action.add_video"), self)
        add_video_action.triggered.connect(self.add_video)
        self.add_video_action = add_video_action
        delete_video_action = QAction(tr("action.delete_video"), self)
        delete_video_action.triggered.connect(lambda: self.delete_video(self.current_video_index))
        self.delete_video_action = delete_video_action
        exit_action = QAction(tr("action.exit"), self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        self.exit_action = exit_action
        for action in (new_action, open_action, save_action, save_as_action):
            file_menu.addAction(action)
        file_menu.addSeparator()
        for action in (add_video_action, delete_video_action):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        self.mode_edit_action = mode_menu.addAction(tr("mode.professional"), self.enter_edit_mode)
        self.mode_user_action = mode_menu.addAction(tr("mode.user"), lambda: (self.preview_btn.setChecked(True), self.toggle_preview_mode()))
        self.project_edit_actions = [
            self.new_project_action,
            self.open_project_action,
            self.save_project_action,
            self.save_project_as_action,
            self.add_video_action,
            self.delete_video_action,
        ]

        self.research_menu = self.menuBar().addMenu(tr("menu.research"))
        research_menu = self.research_menu
        self.toggle_research_action = QAction(tr("action.research_toggle"), self)
        self.toggle_research_action.triggered.connect(self.toggle_research)
        self.select_user_action = QAction(tr("action.manage_participants"), self)
        self.select_user_action.triggered.connect(self.manage_participants)
        self.view_logs_action = QAction(tr("action.session_summary"), self)
        self.view_logs_action.triggered.connect(self.view_research_logs)
        self.export_csv_action = QAction(tr("action.export_csv"), self)
        self.export_csv_action.triggered.connect(self.export_research_csv)
        for action in (self.toggle_research_action, self.select_user_action, self.view_logs_action, self.export_csv_action):
            research_menu.addAction(action)
        self.research_actions = [
            self.toggle_research_action,
            self.select_user_action,
            self.view_logs_action,
            self.export_csv_action,
        ]

        self.language_menu = self.menuBar().addMenu(tr("menu.language"))
        language_menu = self.language_menu
        self.language_actions: dict[str, QAction] = {}
        for language in ("en-US", "es"):
            action = QAction(LANGUAGE_LABELS[language], self)
            action.setCheckable(True)
            action.setData(language)
            action.triggered.connect(lambda _=False, code=language: self.change_language(code))
            language_menu.addAction(action)
            self.language_actions[language] = action

        self.help_menu = self.menuBar().addMenu(tr("menu.help"))
        help_menu = self.help_menu
        open_sample_action = QAction(tr("action.open_sample_project"), self)
        self.open_sample_project_action = open_sample_action
        open_sample_action.triggered.connect(self.open_sample_project)
        help_menu.addAction(open_sample_action)
        about_action = QAction(tr("action.about"), self)
        self.about_action = about_action
        about_action.triggered.connect(self.show_about_anna)
        help_menu.addAction(about_action)


    def show_about_anna(self) -> None:
        QMessageBox.information(
            self,
            tr("action.about"),
            (
                f"{PRODUCT_TITLE}\n"
                f"{tr('label.version')} {APP_VERSION}\n\n"
                f"{tr('message.about')}\n\n"
                "Copyright © 2026 Carlos Máñez-Carvajal\n"
                f"{tr('label.license')}: GPL-3.0-or-later"
            ),
        )

    def open_sample_project(self) -> None:
        self.load_json(ROOT / "demo_project" / "washing_hands.json")

    def new_project(self) -> None:
        if not self.resolve_pending_segment_changes():
            return
        self.player.stop()
        self.project_path = None
        self.duration_ms = 0
        self.restore_snapshot(default_project())
        self.player.stop()
        self.player.setSource(QUrl())
        self.player.setPosition(0)
        self.poster_item.setPixmap(QPixmap())
        self.poster_item.hide()
        self.playback_controller.reset(0)
        self._manual_seek_target_ms = None
        self._last_position_ms = 0
        self.timeline.blockSignals(True)
        self.timeline.setRange(0, 1)
        self.timeline.setValue(0)
        self.timeline.blockSignals(False)
        self.timeline.set_pauses([], None)
        self.timeline.set_segment(0, None)
        self.time_label.setText(f"{format_time(0)} / {format_time(0)}")
        self.update_segment_controls()
        self.history = History()
        self.history.push(self.snapshot())
        self.update_project_title()
        self.logger.write("project_created")

    def change_language(self, language: str) -> None:
        self.language = set_language(language)
        save_language(ROOT, self.language)
        self.configure_tts_locale()
        self.retranslate_ui()

    def configure_tts_locale(self) -> None:
        if self.support_tts is None:
            return
        requested = QLocale("es_ES" if self.language == "es" else "en_US")
        available = list(self.support_tts.availableLocales())
        selected = next((locale for locale in available if locale.name() == requested.name()), None)
        if selected is None:
            selected = next((locale for locale in available if locale.language() == requested.language()), None)
        if selected is not None:
            self.support_tts.setLocale(selected)

    def retranslate_ui(self) -> None:
        set_language(getattr(self, "language", DEFAULT_LANGUAGE))
        localize_widget_tree(self)
        self.top_label.setText(PRODUCT_TITLE)
        for code, action in getattr(self, "language_actions", {}).items():
            action.setText(LANGUAGE_LABELS[code])
            action.setChecked(code == self.language)
        self.refresh_participant_selector()
        self.refresh_video_nav()
        self.update_mode_controls()
        self.update_project_title()

    def make_tools(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("toolPanel")
        panel.setFixedWidth(168)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        title = QLabel(tr("label.tools"))
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        self.tool_buttons: dict[str, QPushButton] = {}
        tools = [
            ("select", tr("tool.select_move"), tool_palette_icon("select"), tr("tooltip.select_move")),
            ("rectangle", tr("tool.rectangle"), hotspot_shape_icon("rectangle"), tr("tooltip.draw_rectangle")),
            ("ellipse", tr("tool.ellipse"), hotspot_shape_icon("ellipse"), tr("tooltip.draw_ellipse")),
            ("edit", tr("tool.edit"), tool_palette_icon("edit"), tr("tooltip.edit_hotspot")),
            ("delete", tr("tool.delete"), tool_palette_icon("delete"), tr("tooltip.delete_hotspot")),
        ]
        for name, text, icon, tip in tools:
            btn = QPushButton(icon, text)
            btn.setObjectName("toolButton")
            btn.setIconSize(QSize(20, 20) if name in {"select", "edit", "delete"} else QSize(22, 22))
            btn.setMinimumSize(0, 40)
            btn.setToolTip(tip)
            btn.setAccessibleName(tip)
            btn.setCheckable(name in {"select", "rectangle", "ellipse"})
            btn.clicked.connect(lambda _=False, n=name: self.tool_clicked(n))
            self.tool_buttons[name] = btn
            layout.addWidget(btn)
        layout.addStretch()
        self.set_mode("select")
        return panel

    def make_controls(self) -> QWidget:
        panel = QWidget()
        self.controls_panel = panel
        panel.setObjectName("controls")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)
        playback_panel = QWidget(panel)
        self.playback_controls = playback_panel
        playback_panel.setObjectName("playbackControls")
        playback_layout = QVBoxLayout(playback_panel)
        playback_layout.setContentsMargins(0, 0, 0, 0)
        playback_layout.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.home_btn = QPushButton(tr("button.start"))
        self.home_btn.setObjectName("transportButton")
        self.home_btn.setIcon(simple_tool_icon("start"))
        self.home_btn.setToolTip(tr("tooltip.go_start"))
        self.home_btn.setAccessibleName(tr("button.start"))
        self.home_btn.clicked.connect(self.go_to_start)
        self.play_btn = QPushButton(tr("button.play"))
        self.play_btn.setObjectName("transportButton")
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn = QPushButton(tr("button.stop"))
        self.stop_btn.setObjectName("transportButton")
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_btn.clicked.connect(self.stop_video)
        self.continue_btn = QPushButton(tr("button.continue"))
        self.continue_btn.setObjectName("continueButton")
        self.continue_btn.setIcon(simple_tool_icon("arrow"))
        self.continue_btn.setToolTip(tr("tooltip.continue_video"))
        self.continue_btn.setAccessibleName(tr("tooltip.continue_video"))
        self.continue_btn.clicked.connect(self.continue_from_pause)
        self.continue_btn.setEnabled(False)
        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        row.addWidget(self.home_btn)
        row.addWidget(self.play_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(self.continue_btn)
        row.addWidget(self.time_label)
        row.addStretch()
        self.timeline = TimelineSlider()
        self.timeline.sliderPressed.connect(self.begin_slider_seek)
        self.timeline.sliderMoved.connect(self.seek_during_drag)
        self.timeline.sliderReleased.connect(self.finish_slider_seek)
        self.timeline.valueChanged.connect(self.on_slider_value_changed)
        self.timeline.markerClicked.connect(self.goto_pause)
        self.timeline.seekClicked.connect(self.seek_from_click)
        playback_layout.addLayout(row)

        self.segment_controls = QWidget(panel)
        self.segment_controls.setObjectName("videoSegmentBox")
        self.segment_controls.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.segment_controls.setFixedWidth(242)
        segment_layout = QVBoxLayout(self.segment_controls)
        segment_layout.setContentsMargins(8, 5, 8, 5)
        segment_layout.setSpacing(3)
        self.segment_title_label = QLabel(tr("segment.title"))
        self.segment_start_caption = QLabel(tr("segment.start"))
        self.segment_start_value = QLineEdit()
        self.segment_start_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.segment_start_value.setValidator(SegmentTimeValidator(self.segment_start_value))
        self.segment_end_caption = QLabel(tr("segment.end"))
        self.segment_end_value = QLineEdit()
        self.segment_end_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.segment_end_value.setValidator(SegmentTimeValidator(self.segment_end_value))
        self.save_segment_btn = QPushButton(tr("segment.apply"))
        self.save_segment_btn.setObjectName("segmentApplyButton")
        self.reset_segment_btn = QPushButton(tr("segment.reset"))
        for field in (self.segment_start_value, self.segment_end_value):
            field.setFixedHeight(26)
            field.setMinimumWidth(150)
        for button in (self.save_segment_btn, self.reset_segment_btn):
            button.setFixedHeight(24)
            button.setMinimumWidth(0)
        self.save_segment_btn.clicked.connect(self.save_segment)
        self.reset_segment_btn.clicked.connect(self.reset_segment)
        self.segment_start_value.editingFinished.connect(lambda: self.commit_segment_text(True))
        self.segment_end_value.editingFinished.connect(lambda: self.commit_segment_text(False))
        self.segment_start_value.textEdited.connect(lambda text: self.on_segment_text_edited(True, text))
        self.segment_end_value.textEdited.connect(lambda text: self.on_segment_text_edited(False, text))
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(6)
        form.setVerticalSpacing(3)
        form.addRow(self.segment_start_caption, self.segment_start_value)
        form.addRow(self.segment_end_caption, self.segment_end_value)
        actions = QHBoxLayout()
        actions.setSpacing(5)
        actions.addWidget(self.save_segment_btn)
        actions.addWidget(self.reset_segment_btn)
        segment_layout.addWidget(self.segment_title_label)
        segment_layout.addLayout(form)
        segment_layout.addLayout(actions)
        playback_layout.addWidget(self.timeline)
        layout.addWidget(playback_panel, 1)
        layout.addWidget(self.segment_controls)
        # Segment es el hijo más alto de esta fila. Al ocultarlo en User mode,
        # conservar la altura profesional evita que el workspace y VideoView
        # absorban el espacio liberado y vuelvan a escalar la escena.
        panel.setMinimumHeight(panel.sizeHint().height())
        return panel

    def make_support_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("supportPanel")
        panel.setFixedWidth(224)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.support_buttons_layout = QVBoxLayout()
        self.support_buttons_layout.setSpacing(6)
        layout.addLayout(self.support_buttons_layout)
        layout.addStretch()
        return panel

    def current_video(self) -> VideoEntry:
        if not self.videos:
            self.videos = [VideoEntry("video-1", tr("video.automatic_name", number=1), "", self.pauses)]
            self.current_video_index = 0
        self.current_video_index = max(0, min(self.current_video_index, len(self.videos) - 1))
        return self.videos[self.current_video_index]

    def effective_start_time(self) -> int:
        return self.current_video().effective_start()

    def effective_end_time(self) -> int:
        return self.current_video().effective_end(self.duration_ms)

    def active_pauses(self) -> list[PausePoint]:
        video = self.current_video()
        return [pause for pause in self.pauses if video.pause_is_active(pause, self.duration_ms)]

    def activate_pause_at_start_if_armed(self, reason: str) -> bool:
        """Present an armed event exactly at the effective playback start."""
        if not self.preview_mode:
            return False
        start = self.effective_start_time()
        pause = next(
            (pause for pause in self.active_pauses() if int(pause.time_ms) == start),
            None,
        )
        if pause is None or self.pause_state(pause.time_ms) != "armed":
            return False
        self.pause_at_temporal_event(pause)
        self.logger.write("pause_at_start_activated", pause_time_ms=start, reason=reason)
        return True

    def segment_clamped_position(self, value: int) -> int:
        start = self.effective_start_time()
        end = self.effective_end_time()
        upper = max(start, end - 1) if end > 0 else max(start, int(value))
        return max(start, min(int(value), upper))

    def update_segment_controls(self) -> None:
        if not hasattr(self, "segment_start_value"):
            return
        video = self.current_video()
        if self._segment_draft_video_id != video.video_id:
            self.load_segment_draft()
        self.segment_title_label.setText(tr("segment.title"))
        self.segment_start_caption.setText(tr("segment.start"))
        self.segment_end_caption.setText(tr("segment.end"))
        self.save_segment_btn.setText(tr("segment.apply"))
        self.reset_segment_btn.setText(tr("segment.reset"))
        self.segment_start_value.setText(format_time(self.draft_start if self.draft_start is not None else 0))
        if self.draft_end is not None:
            end_text = format_time(self.draft_end)
        elif self.duration_ms > 0:
            end_text = format_time(self.duration_ms)
        else:
            end_text = "--:--:--.---"
        self.segment_end_value.setText(end_text)
        editable = not self.preview_mode and self.duration_ms > 0
        self.segment_start_value.setEnabled(editable)
        self.segment_end_value.setEnabled(editable)
        self.reset_segment_btn.setEnabled(editable)
        self.save_segment_btn.setEnabled(not self.preview_mode and self.duration_ms > 0 and self.segment_has_pending_changes())
        self.timeline.set_segment(video.effective_start(), video.end_time)

    def load_segment_draft(self) -> None:
        video = self.current_video()
        self.draft_start = video.start_time
        self.draft_end = video.end_time
        self._segment_draft_video_id = video.video_id

    def segment_has_pending_changes(self) -> bool:
        video = self.current_video()
        if self._segment_draft_video_id != video.video_id:
            return False
        return self.normalized_segment_limits(self.draft_start, self.draft_end) != self.normalized_segment_limits(
            video.start_time, video.end_time
        )

    def normalized_segment_limits(self, start: int | None, end: int | None) -> tuple[int | None, int | None]:
        normalized_start = None if start is None or int(start) == 0 else int(start)
        normalized_end = None if end is None else int(end)
        if self.duration_ms > 0 and normalized_end == int(self.duration_ms):
            normalized_end = None
        return normalized_start, normalized_end

    def draft_effective_start(self) -> int:
        return int(self.draft_start) if self.draft_start is not None else 0

    def draft_effective_end(self) -> int | None:
        if self.draft_end is not None:
            return int(self.draft_end)
        return int(self.duration_ms) if self.duration_ms > 0 else None

    def validate_segment_draft(self) -> bool:
        end = self.draft_effective_end()
        if self.duration_ms <= 0 or end is None:
            return False
        start = self.draft_effective_start()
        return 0 <= start < end <= int(self.duration_ms)

    def show_segment_error(self, message: str) -> None:
        QMessageBox.warning(self, tr("segment.invalid_title"), message)

    def commit_segment_text(self, is_start: bool, *, show_error: bool = True) -> bool:
        field = self.segment_start_value if is_start else self.segment_end_value
        candidate = parse_segment_time(field.text())
        if candidate is None:
            if show_error:
                self.show_segment_error(tr("segment.invalid_format"))
            self.update_segment_controls()
            return False
        if is_start:
            end = self.draft_effective_end()
            valid = self.duration_ms > 0 and end is not None and 0 <= candidate < end and candidate < self.duration_ms
            if valid:
                self.draft_start = candidate
        else:
            valid = self.duration_ms > 0 and self.draft_effective_start() < candidate <= self.duration_ms
            if valid:
                self.draft_end = candidate
        if not valid:
            if show_error:
                self.show_segment_error(tr("segment.invalid_start" if is_start else "segment.invalid_end"))
            self.update_segment_controls()
            return False
        self.update_segment_controls()
        return True

    def on_segment_text_edited(self, is_start: bool, text: str) -> None:
        candidate = parse_segment_time(text)
        if candidate is None:
            return
        if is_start:
            self.draft_start = candidate
        else:
            self.draft_end = candidate
        self.save_segment_btn.setEnabled(
            not self.preview_mode and self.duration_ms > 0 and self.segment_has_pending_changes()
        )

    def reset_segment(self) -> None:
        if self.preview_mode or self.duration_ms <= 0:
            return
        video = self.current_video()
        had_applied_segment = video.start_time is not None or video.end_time is not None
        self.draft_start = None
        self.draft_end = None
        video.start_time = None
        video.end_time = None
        self._manual_seek_target_ms = None
        self.playback_controller.reset(0)
        self.player.pause()
        self.player.setPosition(0)
        self._last_position_ms = 0
        self.clear_output_text()
        self.active_event_id = None
        self.current_hotspot_id = None
        self.active_hotspot_id = None
        self.active_support_id = None
        self.clear_selected_event()
        self.pause_states = {pause.time_ms: "armed" for pause in self.pauses}
        self.timeline.blockSignals(True)
        self.timeline.setValue(0)
        self.timeline.blockSignals(False)
        self.timeline.set_pauses(self.pauses, None)
        self.reload_hotspots_for_pause()
        self.update_continue_button()
        self.time_label.setText(f"{format_time(0)} / {format_time(self.duration_ms)}")
        self._research_completed_videos.discard(video.video_id)
        self.update_segment_controls()
        if had_applied_segment:
            self.push_history("video_segment_reset")

    def save_segment(self) -> bool:
        start_candidate = parse_segment_time(self.segment_start_value.text())
        end_candidate = parse_segment_time(self.segment_end_value.text())
        if start_candidate is None or end_candidate is None:
            self.show_segment_error(tr("segment.invalid_format"))
            self.update_segment_controls()
            return False
        if self.duration_ms <= 0 or not (0 <= start_candidate < end_candidate <= self.duration_ms):
            self.show_segment_error(tr("segment.invalid_interval"))
            self.update_segment_controls()
            return False
        self.draft_start, self.draft_end = start_candidate, end_candidate
        if not self.segment_has_pending_changes():
            self.draft_start, self.draft_end = self.normalized_segment_limits(self.draft_start, self.draft_end)
            self.update_segment_controls()
            return True
        if not self.validate_segment_draft():
            self.show_segment_error(tr("segment.invalid_interval"))
            return False
        video = self.current_video()
        normalized_start, normalized_end = self.normalized_segment_limits(self.draft_start, self.draft_end)
        self.draft_start, self.draft_end = normalized_start, normalized_end
        video.start_time = normalized_start
        video.end_time = normalized_end
        position = int(self.player.position())
        start = video.effective_start()
        end = video.effective_end(self.duration_ms)
        self.player.pause()
        if position < start or position >= end:
            self.playback_controller.reset(start)
            self._manual_seek_target_ms = start
            self.player.setPosition(start)
            self.timeline.setValue(start)
            self._last_position_ms = start
        self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.update_segment_controls()
        self.push_history("video_segment_saved")
        return True

    def discard_segment_draft(self) -> None:
        self.load_segment_draft()
        self.update_segment_controls()

    def resolve_pending_segment_changes(self, decision: str | None = None) -> bool:
        if not self.segment_has_pending_changes():
            return True
        if decision == "save":
            return self.save_segment()
        if decision == "discard":
            self.discard_segment_draft()
            return True
        if decision == "cancel":
            return False
        dialog = QMessageBox(self)
        dialog.setWindowTitle(tr("segment.pending_title"))
        dialog.setText(tr("segment.pending_message"))
        save_button = dialog.addButton(tr("segment.save_changes"), QMessageBox.ButtonRole.AcceptRole)
        discard_button = dialog.addButton(tr("segment.discard_changes"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton(tr("button.cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(save_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is save_button:
            return self.save_segment()
        if clicked is discard_button:
            self.discard_segment_draft()
            return True
        if clicked is cancel_button:
            return False
        return False

    def project_display_name(self) -> str:
        if not self.video_has_valid_source(self.current_video()):
            return ""
        return self.localized_video_name(self.current_video())

    def localized_video_name(self, video: VideoEntry) -> str:
        name = str(video.name or "")
        automatic = re.fullmatch(r"(?:Video|Vídeo)\s+(\d+)", name, re.IGNORECASE)
        if automatic:
            return tr("video.automatic_name", number=int(automatic.group(1)))
        return name

    def update_project_title(self) -> None:
        title = self.project_display_name()
        self.top_label.setText(PRODUCT_TITLE)
        self.setWindowTitle(f"{PRODUCT_TITLE} — {title}" if title else PRODUCT_TITLE)

    def sync_current_video(self) -> None:
        self.current_video().pauses = self.pauses

    def resolved_video_path(self, video: VideoEntry) -> Path:
        source_path = Path(video.source)
        if not source_path.is_absolute():
            source_path = (ROOT / source_path).resolve()
        return source_path

    def request_video_thumbnail(self, video: VideoEntry) -> None:
        if video.video_id in self.video_thumbnails or video.video_id in self.thumbnail_requests:
            if video.video_id in self.video_thumbnails and video.video_id == self.current_video().video_id:
                self.set_central_poster(self.video_thumbnails[video.video_id])
            return
        # QMediaPlayer puede no entregar frames de forma fiable cuando se crean
        # varios extractores a la vez. Serializar las capturas: al completar una,
        # refresh_video_nav solicita automáticamente la siguiente que falte.
        if self.thumbnail_requests:
            return
        source_path = self.resolved_video_path(video)
        if not source_path.exists():
            return
        self.thumbnail_requests.add(video.video_id)
        sink = QVideoSink(self)
        player = QMediaPlayer(self)
        player.setVideoOutput(sink)
        player.setSource(QUrl.fromLocalFile(str(source_path)))

        def capture_frame(frame, video_id: str = video.video_id, player_ref: QMediaPlayer = player, sink_ref: QVideoSink = sink) -> None:
            image = frame.toImage()
            if image.isNull():
                return
            pixmap = QPixmap.fromImage(image)
            self.video_thumbnails[video_id] = pixmap
            if video_id == self.current_video().video_id:
                self.set_central_poster(pixmap)
            try:
                sink_ref.videoFrameChanged.disconnect()
            except (RuntimeError, TypeError):
                pass
            player_ref.stop()
            player_ref.deleteLater()
            sink_ref.deleteLater()
            self.thumbnail_extractors = [(p, s) for p, s in self.thumbnail_extractors if p is not player_ref]
            self.thumbnail_requests.discard(video_id)
            self.refresh_video_nav()

        sink.videoFrameChanged.connect(capture_frame)
        self.thumbnail_extractors.append((player, sink))
        player.play()
        QTimer.singleShot(500, player.pause)

    def set_central_poster(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(QSize(FRAME_WIDTH, FRAME_HEIGHT), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.poster_item.setPixmap(scaled)
        self.poster_item.setOffset((FRAME_WIDTH - scaled.width()) / 2, (FRAME_HEIGHT - scaled.height()) / 2)
        self.poster_item.show()

    def prime_current_video_frame(self) -> None:
        self.last_primed_video_id = self.current_video().video_id
        self.request_video_thumbnail(self.current_video())
        QTimer.singleShot(0, lambda: (self.player.pause(), self.player.setPosition(self.effective_start_time())))

    def refresh_video_nav(self) -> None:
        while self.video_nav_layout.count():
            item = self.video_nav_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        has_empty_slot = False
        for index, video in enumerate(self.videos):
            selected = index == self.current_video_index
            valid_source = self.video_has_valid_source(video)
            frame = self.video_thumbnails.get(video.video_id) if valid_source else None
            button = QToolButton()
            button.setObjectName("videoThumbButton" if valid_source else "addVideoButton")
            button.setFixedSize(132, 70)
            button.setCheckable(valid_source)
            button.setChecked(selected and valid_source)
            if valid_source:
                button.setIcon(thumbnail_icon(frame, selected))
                button.setIconSize(QSize(76, 42))
                display_name = self.localized_video_name(video)
                button.setText(display_name)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                button.setToolTip(tr("tooltip.select_video", name=display_name))
                if not self.preview_mode:
                    button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    button.customContextMenuRequested.connect(
                        lambda point, video_id=video.video_id, btn=button: self.show_video_context_menu(video_id, btn.mapToGlobal(point))
                    )
                else:
                    button.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
                self.request_video_thumbnail(video)
            else:
                has_empty_slot = True
                button.setText("+")
                button.setAccessibleName(tr("action.add_video").rstrip("…"))
                button.setStyleSheet("font-size:28px;font-weight:600;")
            button.clicked.connect(lambda _=False, i=index: self.select_or_add_video(i))
            self.video_nav_layout.addWidget(button)
        if not has_empty_slot:
            self.add_video_btn = QToolButton()
            self.add_video_btn.setText("+")
            self.add_video_btn.setObjectName("addVideoButton")
            self.add_video_btn.setAccessibleName(tr("action.add_video").rstrip("…"))
            self.add_video_btn.setFixedSize(132, 70)
            self.add_video_btn.setStyleSheet("font-size:28px;font-weight:600;")
            self.add_video_btn.clicked.connect(self.add_video)
            self.video_nav_layout.addWidget(self.add_video_btn)
        else:
            self.add_video_btn = None
        self.video_nav_layout.addStretch()
        self.update_project_title()
        self.update_mode_controls()

    def video_has_valid_source(self, video: VideoEntry) -> bool:
        source = str(video.source or "").strip()
        if not source:
            return False
        return self.resolved_video_path(video).exists()

    def select_or_add_video(self, index: int) -> None:
        if self.preview_mode and not self.navigation_enabled_for_user():
            return
        if index < 0 or index >= len(self.videos):
            return
        if not self.video_has_valid_source(self.videos[index]):
            if self.preview_mode:
                return
            self.add_video(replace_index=index)
            return
        self.select_video(index, navigation_action="thumbnail")

    def navigation_enabled_for_user(self) -> bool:
        return bool(
            not self.preview_mode
            or not hasattr(self, "navigation_visibility")
            or self.navigation_visibility.isChecked()
        )

    def video_index_by_id(self, video_id: str) -> int | None:
        for index, video in enumerate(self.videos):
            if video.video_id == video_id:
                return index
        return None

    def video_has_associated_content(self, video: VideoEntry) -> bool:
        return bool(video.pauses)

    def confirm_replace_video_content_removal(self) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(tr("dialog.replace_video"))
        dialog.setText(tr("message.replace_video_content"))
        replace_button = dialog.addButton(tr("button.replace"), QMessageBox.ButtonRole.AcceptRole)
        cancel_button = dialog.addButton(tr("button.cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() == replace_button

    def show_video_context_menu(self, video_id: str, global_pos) -> None:
        if self.preview_mode:
            return
        index = self.video_index_by_id(video_id)
        if index is None or not self.video_has_valid_source(self.videos[index]):
            return
        menu, rename_action, replace_action, delete_action = self.make_video_context_menu()
        action = menu.exec(global_pos)
        current_index = self.video_index_by_id(video_id)
        if current_index is None:
            return
        if action == rename_action:
            self.prompt_rename_video(current_index)
        elif action == replace_action:
            self.replace_video(current_index)
        elif action == delete_action:
            self.delete_video(current_index)

    def make_video_context_menu(self) -> tuple[QMenu, QAction, QAction, QAction]:
        menu = QMenu(self)
        rename_action = menu.addAction(tr("action.rename_video"))
        rename_action.setEnabled(not self.research.is_active)
        replace_action = menu.addAction(tr("action.replace_video"))
        delete_action = menu.addAction(tr("action.delete_video"))
        return menu, rename_action, replace_action, delete_action

    def next_video_number(self) -> int:
        used: set[int] = set()
        for video in self.videos:
            digits = "".join(character for character in str(video.video_id or "") if character.isdigit())
            if digits:
                used.add(int(digits))
        number = 1
        while number in used:
            number += 1
        return number

    def prompt_rename_video(self, index: int) -> bool:
        if self.preview_mode or self.research.is_active or index < 0 or index >= len(self.videos):
            return False
        video = self.videos[index]
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setWindowTitle(tr("dialog.rename_video"))
        dialog.setLabelText(tr("label.video_name"))
        dialog.setTextValue(video.name)
        line_edit = dialog.findChild(QLineEdit)
        if line_edit is not None:
            line_edit.setMaxLength(80)
            line_edit.selectAll()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return self.rename_video(index, dialog.textValue())

    def rename_video(self, index: int, entered_text: str) -> bool:
        if self.preview_mode or self.research.is_active or index < 0 or index >= len(self.videos):
            return False
        new_name = str(entered_text).strip()
        if not new_name:
            QMessageBox.warning(self, tr("dialog.rename_video"), tr("message.video_name_empty"))
            return False
        if len(new_name) > 80:
            QMessageBox.warning(self, tr("dialog.rename_video"), tr("message.video_name_too_long"))
            return False
        video = self.videos[index]
        if new_name == video.name:
            return False
        normalized = new_name.casefold()
        if any(other_index != index and str(other.name).strip().casefold() == normalized for other_index, other in enumerate(self.videos)):
            QMessageBox.warning(self, tr("dialog.rename_video"), tr("message.video_name_duplicate"))
            return False
        video.name = new_name
        self.refresh_video_nav()
        self.push_history("video_renamed")
        return True

    def select_video(self, index: int, *, sync_previous: bool = True, navigation_action: str | None = None) -> None:
        if index < 0 or index >= len(self.videos):
            return
        if index != self.current_video_index and not self.resolve_pending_segment_changes():
            return
        previous_index = self.current_video_index
        previous_video = self.current_video()
        previous_video_id = previous_video.video_id
        previous_video_name = previous_video.name
        previous_position_ms = int(self.player.position())
        if sync_previous:
            self.sync_current_video()
        self.player.pause()
        self.playback_controller.reset(0)
        self._manual_seek_target_ms = None
        self.clear_active_interaction()
        self.selected_pause_ms = None
        self.selected_event_id = None
        self.active_event_id = None
        self.current_hotspot_id = None
        self.active_hotspot_id = None
        self.active_support_id = None
        self.current_video_index = index
        self.duration_ms = 0
        segment_start = self.effective_start_time()
        self.load_segment_draft()
        if navigation_action is None:
            if index == previous_index - 1:
                navigation_action = "previous"
            elif index == previous_index + 1:
                navigation_action = "next"
            else:
                navigation_action = "thumbnail"
        self.research.record_event(
            "video_changed",
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            video_position_ms=segment_start,
            target_type="video",
            target_id=self.current_video().video_id,
            navigation_action=navigation_action,
            from_video_id=previous_video_id,
            from_video_name=previous_video_name,
            to_video_id=self.current_video().video_id,
            to_video_name=self.current_video().name,
            from_position_ms=previous_position_ms,
            to_position_ms=segment_start,
            start_time=self.current_video().start_time,
            end_time=self.current_video().end_time,
            previous_video_id=previous_video_id,
        )
        video = self.current_video()
        self.pauses = video.pauses
        source_path = self.resolved_video_path(video)
        self.player.setSource(QUrl.fromLocalFile(str(source_path)))
        self.player.setPosition(segment_start)
        self.playback_controller.reset(segment_start)
        self._last_position_ms = segment_start
        self.timeline.blockSignals(True)
        self.timeline.setValue(segment_start)
        self.timeline.blockSignals(False)
        self.timeline.set_pauses(self.pauses, None)
        self.reload_hotspots_for_pause()
        self.refresh_video_nav()
        self.refresh_support_panel()
        self.update_segment_controls()
        self.activate_pause_at_start_if_armed("video_changed")
        self.logger.write("video_selected", video_index=index, video_id=video.video_id, source=video.source)
        self.update_project_title()
        self.time_label.setText(f"{format_time(segment_start)} / {format_time(self.duration_ms)}")

    def add_video(self, *, replace_index: int | None = None) -> None:
        if self.preview_mode:
            return
        if not self.resolve_pending_segment_changes():
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog.add_video"), str(ROOT.parents[1]), tr("file.video_filter"))
        if not path:
            return
        self.sync_current_video()
        selected_path = str(Path(path))

        # «Vídeo 1» es un espacio vacío que se completa; no se crea
        # «Vídeo 2» dejando el primero vacío.
        if replace_index is None and len(self.videos) == 1 and not self.video_has_valid_source(self.videos[0]):
            replace_index = 0

        if replace_index is not None and 0 <= replace_index < len(self.videos):
            previous = self.videos[replace_index]
            self.video_thumbnails.pop(previous.video_id, None)
            self.thumbnail_requests.discard(previous.video_id)
            self.videos[replace_index] = VideoEntry(
                previous.video_id or f"video-{replace_index + 1}",
                previous.name or tr("video.automatic_name", number=replace_index + 1),
                selected_path,
                previous.pauses,
            )
            self.select_video(replace_index)
            self.push_history("video_source_added")
            return

        number = self.next_video_number()
        video = VideoEntry(f"video-{number}", tr("video.automatic_name", number=number), selected_path, [])
        self.videos.append(video)
        self.select_video(len(self.videos) - 1)
        self.push_history("video_added")

    def replace_video(self, index: int) -> None:
        if self.preview_mode:
            return
        if index < 0 or index >= len(self.videos):
            return
        if index == self.current_video_index and not self.resolve_pending_segment_changes():
            return
        self.sync_current_video()
        video = self.videos[index]
        if self.video_has_associated_content(video) and not self.confirm_replace_video_content_removal():
            return
        if False and self.video_has_associated_content(video):
            accepted = QMessageBox.question(
                self,
                tr("dialog.replace_video"),
                tr("message.replace_video_confirm"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if accepted != QMessageBox.StandardButton.Yes:
                return
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog.replace_video"), str(ROOT.parents[1]), tr("file.video_filter"))
        if not path:
            return
        self.video_thumbnails.pop(video.video_id, None)
        self.thumbnail_requests.discard(video.video_id)
        self.videos[index] = VideoEntry(
            video.video_id or f"video-{index + 1}",
            video.name or tr("video.automatic_name", number=index + 1),
            str(Path(path)),
            [],
        )
        self.duration_ms = 0
        self.select_video(index, sync_previous=False)
        self.push_history("video_replaced")

    def delete_video(self, index: int) -> None:
        if self.preview_mode:
            return
        if index < 0 or index >= len(self.videos):
            return
        if index == self.current_video_index and not self.resolve_pending_segment_changes():
            return
        if len(self.videos) <= 1:
            QMessageBox.information(self, tr("dialog.delete_video"), tr("message.delete_video_minimum"))
            return
        accepted = QMessageBox.question(
            self,
            tr("dialog.delete_video"),
            tr("message.delete_video_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if accepted != QMessageBox.StandardButton.Yes:
            return
        self.sync_current_video()
        removed = self.videos.pop(index)
        self.video_thumbnails.pop(removed.video_id, None)
        self.thumbnail_requests.discard(removed.video_id)
        self.current_video_index = min(index, len(self.videos) - 1)
        self.pauses = []
        self.timeline.set_pauses([], None)
        self.select_video(self.current_video_index, sync_previous=False)
        self.push_history("video_deleted")

    def support_is_configured(self, support: SupportItem) -> bool:
        return support.is_configured()

    def support_asset_path(self, asset: str | None) -> Path | None:
        if not asset: return None
        try: return asset_path(validate_support_asset(asset))
        except ValueError: return None

    def hotspot_audio_asset_path(self, asset: str | None) -> Path | None:
        if not asset:
            return None
        try:
            return asset_path(validate_audio_asset(asset))
        except ValueError:
            return None

    def play_interaction_audio(self, path: Path | None) -> bool:
        """Reproduce el audio de hotspot/support mediante el mismo flujo Qt."""
        if path is None or not path.exists():
            return False
        if self.support_tts is not None:
            self.support_tts.stop()
        self.hotspot_audio_player.stop()
        self.hotspot_audio_output.setMuted(False)
        self.hotspot_audio_output.setVolume(1.0)
        self.hotspot_audio_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.hotspot_audio_player.setPosition(0)
        # Igual que en los supports: iniciar una vez aplicada la fuente al reproductor.
        QTimer.singleShot(0, self.hotspot_audio_player.play)
        return True

    def support_display_label(self, support: SupportItem, index: int) -> str:
        # El nombre del slot es interno. Solo se presenta el contenido escrito.
        return " ".join(str(support.text or "").split())[:SupportConfigDialog.TEXT_MAX_CHARS]

    def support_button_icon(self, support: SupportItem) -> QIcon:
        path = self.support_asset_path(support.image_asset)
        if path and path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                # QIcon conserva la proporción; el tamaño se fija en la tarjeta.
                return QIcon(pixmap)
        return QIcon()

    def support_button_pixmap(self, support: SupportItem) -> QPixmap:
        path = self.support_asset_path(support.image_asset)
        if path and path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return pixmap
        return QPixmap()

    def make_support_card(self, support: SupportItem, index: int) -> QWidget:
        card = QWidget(self.support_panel)
        card.setObjectName("supportCard")
        card.setFixedSize(200, 154 if not self.preview_mode else 132)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        configured = support.is_configured()
        user_visible = bool(support.visible and configured)

        if not self.preview_mode:
            visible = QCheckBox(tr("option.visible"), card)
            visible.setChecked(user_visible)
            visible.toggled.connect(lambda checked, s=support: self.set_support_visible(s, checked))
            layout.addWidget(visible)

        button = SupportImageButton(card)
        button.setObjectName("supportConfigureButton" if not self.preview_mode else "supportUserButton")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setFixedSize(188, 116 if not self.preview_mode else 122)

        display_text = self.support_display_label(support, index)
        support_pixmap = self.support_button_pixmap(support)
        has_image = bool(support.image_asset and not support_pixmap.isNull())
        if configured:
            if has_image:
                button.set_original_pixmap(support_pixmap)
            # Con imagen, el texto funciona como etiqueta breve debajo. Sin imagen, ocupa la tarjeta.
            button.setText(display_text if display_text else "")
            button.update_icon_size()
        else:
            button.setText("+")
            button.setIcon(QIcon())

        if has_image:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        else:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        button.setToolTip("Configurar apoyo" if not self.preview_mode else display_text)
        button.clicked.connect(
            lambda _=False, s=support: self.configure_support(s)
            if not self.preview_mode
            else self.activate_support(s)
        )

        if self.preview_mode:
            # Se conserva el hueco del slot, pero solo el apoyo visible es interactivo y perceptible.
            button.setVisible(user_visible)
            button.setEnabled(user_visible)

        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        return card

    def set_support_visible(self, support: SupportItem, visible: bool) -> None:
        if visible and not support.is_configured():
            QMessageBox.information(self, tr("dialog.empty_support"), tr("message.empty_support"))
            self.refresh_support_panel()
            return
        support.visible = bool(visible)
        self.sync_current_video()
        self.refresh_support_panel()

    def pause_by_id(self, event_id: str | None) -> PausePoint | None:
        if not event_id:
            return None
        return next(
            (pause for pause in self.pauses if pause.pause_id == event_id),
            None,
        )

    def selected_event(self) -> PausePoint | None:
        """PauseEvent selected by the professional in edit mode."""
        return self.pause_by_id(self.selected_event_id)

    def active_event(self) -> PausePoint | None:
        """PauseEvent currently active during user-mode playback."""
        return self.pause_by_id(self.active_event_id)

    def select_event(self, pause: PausePoint | None) -> None:
        """Select an event for editing without changing playback state."""
        self.selected_event_id = pause.pause_id if pause is not None else None
        self.selected_pause_ms = pause.time_ms if pause is not None else None
        self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        if hasattr(self, "selected_label"):
            self.selected_label.setText(
                tr("label.selected_pause", time=format_time(pause.time_ms))
                if pause is not None
                else tr("label.selected_pause_none")
            )

    def clear_selected_event(self) -> None:
        self.select_event(None)

    def support_context_pause(self, position_ms: int | None = None) -> PausePoint | None:
        # En modo usuario solo existe el PauseEvent activo.
        if self.preview_mode:
            return self.active_event()

        # En edición, la pausa seleccionada deja de ser contexto en cuanto el
        # cabezal abandona su tolerancia temporal. Así no se arrastran supports
        # ni hotspots de una pausa anterior.
        position = int(self.player.position()) if position_ms is None else int(position_ms)
        pause = self.selected_event()
        if pause is not None and abs(position - int(pause.time_ms)) <= PAUSE_TOLERANCE_MS:
            return pause
        if pause is not None:
            self.clear_selected_event()

        pause = find_pause(self.pauses, position, PAUSE_TOLERANCE_MS)
        if pause is not None:
            self.select_event(pause)
        return pause

    def configure_support(self, support: SupportItem) -> None:
        if self.preview_mode:
            return
        pause = self.support_context_pause()
        created = False
        if pause is None:
            pause, created = find_or_create_pause(
                self.pauses,
                int(self.player.position()),
                PAUSE_TOLERANCE_MS,
            )
        index = support.position
        dialog = SupportConfigDialog(support, tr("support.automatic_name", number=index + 1), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            if created:
                self.pauses = [item for item in self.pauses if item is not pause]
                self.sync_current_video()
                self.clear_selected_event()
                self.timeline.set_pauses(self.pauses, None)
                self.refresh_support_panel()
            return
        pause.supports[index] = dialog.result_support()
        self.select_event(pause)
        self.sync_current_video()
        self.refresh_support_panel()
        self.push_history("support_configured")

    def refresh_support_panel(self, position_ms: int | None = None) -> None:
        if not hasattr(self, "support_buttons_layout"):
            return

        # La columna derecha forma parte de la geometría fija del espacio de trabajo.
        # Nunca se colapsa: en ausencia de contenido queda vacía, de modo que el vídeo
        # conserva exactamente el mismo tamaño y posición en edición, reproducción,
        # antes de una pausa, durante una pausa y después de pulsar Continuar.
        self.support_panel.setVisible(True)

        while self.support_buttons_layout.count():
            item = self.support_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        enabled = self.support_visibility.isChecked() if hasattr(self, "support_visibility") else True
        if not enabled:
            return

        pause = self.support_context_pause(position_ms)
        if pause is None:
            if not self.preview_mode:
                # En edición se mantienen los tres slots de autoría aunque todavía no
                # exista una pausa seleccionada.
                for index, support in enumerate(default_supports()):
                    self.support_buttons_layout.addWidget(
                        self.make_support_card(support, index)
                    )
            # En modo usuario, sin PauseEvent activo, la columna permanece vacía.
            return

        pause.supports = normalize_supports(pause.supports)
        for index, support in enumerate(pause.supports):
            if self.preview_mode and not (support.visible and support.is_configured()):
                continue
            self.support_buttons_layout.addWidget(
                self.make_support_card(support, index)
            )

    def activate_support(self, support: SupportItem) -> None:
        pause = self.support_context_pause()
        if not pause or not support.visible or not support.is_configured():
            return

        # Un apoyo comunica mediante audio. El audio grabado/seleccionado tiene prioridad.
        played_audio = False
        if support.audio_asset:
            played_audio = self.play_interaction_audio(
                self.support_asset_path(support.audio_asset)
            )

        used_tts = False
        text = " ".join(str(support.text or "").split())
        if not played_audio and text and support.tts_enabled and self.support_tts is not None:
            self.hotspot_audio_player.stop()
            self.support_tts.stop()
            self.support_tts.say(text)
            used_tts = True

        self.research.record_support_activation(
            support.support_id,
            audio_played=played_audio,
            tts_played=used_tts,
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            pause_id=pause.pause_id,
            support_text=text,
            communication_category=support.communication_category,
            typology=support.communication_category,
            visible=bool(support.visible),
            image_available=bool(support.image_asset),
            audio_available=bool(support.audio_asset),
            tts_enabled=bool(support.tts_enabled and text),
            support_type=("combinado" if sum([bool(text), bool(support.image_asset), bool(support.audio_asset)]) > 1 else "audio" if support.audio_asset else "imagen" if support.image_asset else "texto"),
            video_position_ms=int(self.player.position()),
        )
        self.active_support_id = support.support_id
        self.active_hotspot_id = None

        self.logger.write(
            "support_activated",
            support_id=support.support_id,
            pause_id=pause.pause_id,
            position=support.position,
            has_text=bool(text),
            has_image=bool(support.image_asset),
            has_audio=bool(support.audio_asset),
            audio_played=played_audio,
            tts_enabled=bool(support.tts_enabled),
            tts_used=used_tts,
            video_index=self.current_video_index,
            position_ms=int(self.player.position()),
        )

    def enter_edit_mode(self) -> None:
        if self.preview_mode:
            self.preview_btn.setChecked(False)
            self.toggle_preview_mode()

    def update_mode_controls(self) -> None:
        user_mode = self.preview_mode
        self.mode_label.setText(tr("mode.user" if user_mode else "mode.professional"))
        self.mode_label.setVisible(not user_mode)
        if hasattr(self, "segment_controls"):
            self.segment_controls.setVisible(not user_mode)
            self.segment_controls.setEnabled(not user_mode)
            self.update_segment_controls()
        self.refresh_mode_quick_button()
        self.update_research_controls()

        # Mantener exactamente el mismo ancho y posición del área de vídeo en ambos modos.
        # En modo usuario se oculta el contenido de la columna de herramientas, pero no
        # la propia columna fija de 168 px; así el vídeo y sus hotspots no cambian de
        # tamaño ni de posición al alternar entre edición y uso.
        self.tool_panel.setVisible(True)
        tool_panel_children = [
            *self.tool_panel.findChildren(QLabel),
            *self.tool_panel.findChildren(QPushButton),
        ]
        for child in tool_panel_children:
            child.setVisible(not user_mode)

        self.selected_label.setVisible(False)
        if getattr(self, "add_video_btn", None) is not None:
            self.add_video_btn.setVisible(not user_mode)
            self.add_video_btn.setEnabled(not user_mode)
        if hasattr(self, "navigation_visibility"):
            self.navigation_visibility.setVisible(not user_mode)
            self.video_nav.setVisible(self.navigation_visibility.isChecked())
            self.timeline.setEnabled((not user_mode) or self.navigation_visibility.isChecked())
        if hasattr(self, "support_visibility"):
            self.support_visibility.setVisible(not user_mode)
        if hasattr(self, "show_hotspots_toggle"):
            self.show_hotspots_toggle.setVisible(not user_mode)
        self.refresh_support_panel()
        self.refresh_hotspot_visibility()

        # En modo usuario no se puede operar con ningún menú.
        # El engranaje es el único control para volver al modo terapeuta.
        for action in getattr(self, "project_edit_actions", []):
            action.setEnabled(not user_mode)
        for action in getattr(self, "research_actions", []):
            action.setEnabled(not user_mode)
        if hasattr(self, "exit_action"):
            self.exit_action.setEnabled(True)
        if hasattr(self, "mode_edit_action"):
            self.mode_edit_action.setEnabled(user_mode)
        if hasattr(self, "mode_user_action"):
            self.mode_user_action.setEnabled(not user_mode)
        for menu in (
            getattr(self, "file_menu", None),
            getattr(self, "research_menu", None),
        ):
            if menu is not None:
                menu.menuAction().setVisible(True)
                menu.menuAction().setEnabled(True)
        for menu in (
            getattr(self, "mode_menu", None),
            getattr(self, "language_menu", None),
            getattr(self, "help_menu", None),
        ):
            if menu is not None:
                menu.menuAction().setVisible(True)
                menu.menuAction().setEnabled(True)

    def record_user_event(self, event_type: str) -> None:
        pause = self.current_pause()
        research_event = {
            "turn": "professional_turn_marked",
            "adequate": "response_marked_adequate",
            "review": "review_marked",
        }.get(event_type, event_type)
        target_id = self.active_hotspot_id or self.current_hotspot_id or self.active_support_id
        if self.active_hotspot_id or self.current_hotspot_id:
            target_type = "hotspot"
        elif self.active_support_id:
            target_type = "support"
        elif pause:
            target_type = "pause"
            target_id = pause.pause_id
        else:
            target_type = "general"
        self.research.record_event(
            research_event,
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            pause_id=pause.pause_id if pause else None,
            video_position_ms=int(self.player.position()),
            hotspot_id=target_id if target_type == "hotspot" else None,
            support_id=target_id if target_type == "support" else None,
            target_type=target_type,
            target_id=target_id,
        )
        self.logger.write(
            "user_event",
            event_type=event_type,
            project_id=self.project.get("project_id", DEFAULT_PROJECT_ID),
            video_index=self.current_video_index,
            video_id=self.current_video().video_id,
            position_ms=int(self.player.position()),
            pause_id=pause.pause_id if pause else None,
            hotspot_id=self.active_hotspot_id,
        )

    def research_hotspots_for_pause(self, pause: PausePoint) -> list[dict[str, object]]:
        return [
            {
                "hotspot_id": hotspot.hotspot_id,
                "category": hotspot.communication_category,
                "typology": hotspot.communication_category,
                "message_text": hotspot.message_text,
                "text": hotspot.message_text,
                "shape": hotspot.shape,
                "geometry": dict(hotspot.geometry),
                "visible_text": bool(hotspot.show_message_text and hotspot.message_text),
                "audio_available": bool(hotspot.audio_asset),
                "tts_enabled": bool(getattr(hotspot, HOTSPOT_TTS_FIELD, True) and hotspot.message_text),
                "tts_available": bool(getattr(hotspot, HOTSPOT_TTS_FIELD, True) and hotspot.message_text),
            }
            for hotspot in pause.hotspots
        ]

    def research_supports_for_pause(self, pause: PausePoint) -> list[dict[str, object]]:
        supports = []
        for support in normalize_supports(pause.supports):
            if not (support.visible and support.is_configured()):
                continue
            enabled_parts = [
                bool(str(support.text or "").strip()),
                bool(support.image_asset),
                bool(support.audio_asset),
            ]
            if sum(enabled_parts) > 1:
                support_type = "combinado"
            elif support.audio_asset:
                support_type = "audio"
            elif support.image_asset:
                support_type = "imagen"
            else:
                support_type = "texto"
            supports.append(
                {
                    "support_id": support.support_id,
                    "category": support.communication_category,
                    "typology": support.communication_category,
                    "text": support.text,
                    "type": support_type,
                    "visible": bool(support.visible),
                    "image_available": bool(support.image_asset),
                    "audio_available": bool(support.audio_asset),
                    "tts_enabled": bool(support.tts_enabled and support.text),
                    "position": int(support.position),
                }
            )
        return supports

    def refresh_mode_quick_button(self) -> None:
        if self.preview_mode:
            # En modo usuario, engranaje generado para volver a configuración.
            self.mode_quick_btn.setIcon(mode_icon("professional"))
            self.mode_quick_btn.setToolTip(tr("mode.professional"))
        else:
            # En modo profesional, Play generado para pasar a modo usuario.
            self.mode_quick_btn.setIcon(mode_icon("user"))
            self.mode_quick_btn.setToolTip(tr("mode.user"))
        self.mode_quick_btn.setIconSize(QSize(22, 22))

    def handle_mode_quick_button(self) -> None:
        if self.preview_mode:
            self.enter_edit_mode()
        else:
            self.preview_btn.setChecked(True)
            self.toggle_preview_mode()

    def install_research_shortcuts(self) -> None:
        bindings = (("Space", "turn"), ("+", "adequate"), ("-", "review"))
        for sequence, mark in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(lambda value=mark: self.handle_research_shortcut(value))
            self._research_shortcuts.append(shortcut)

    def research_shortcuts_allowed(self) -> bool:
        return bool(self.research.is_active and self.preview_mode and QApplication.activeModalWidget() is None)

    def handle_research_shortcut(self, mark: str) -> None:
        if not self.research_shortcuts_allowed():
            return
        self.handle_professional_annotation(mark)

    def handle_professional_annotation(self, mark: str) -> None:
        if not (self.preview_mode and self.research.is_active):
            return
        self.record_user_event(mark)
        labels = {
            "turn": tr("status.turn_recorded"),
            "adequate": tr("status.appropriate_recorded"),
            "review": tr("status.review_recorded"),
        }
        # El propio estado pressed/released del botón proporciona la respuesta
        # visual. No se abre ni se muestra una barra de estado,
        # evitando cualquier salto de distribución al registrar la marca.

    def undo_last_professional_mark(self) -> None:
        manual_types = {"professional_turn_marked", "response_marked_adequate", "review_marked"}
        for index in range(len(self.research.events) - 1, -1, -1):
            if self.research.events[index].get("event_type") in manual_types:
                del self.research.events[index]
                if self.research.events_path is not None:
                    with self.research.events_path.open("w", encoding="utf-8") as handle:
                        for event in self.research.events:
                            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                break


    def refresh_participant_selector(self) -> None:
        if not hasattr(self, "participant_selector"):
            return
        self._updating_participant_selector = True
        try:
            self.participant_selector.clear()
            if self.research.is_active:
                session = self.research.active_session
                if session is not None and session.is_anonymous:
                    self.participant_selector.addItem(tr("label.research_anonymous"), None)
                else:
                    self.participant_selector.addItem(tr("label.research_participant", name=self.users_manager.get_current_user_name()), self.users_manager.current_user_id)
                self.participant_selector.setEnabled(False)
                self.participant_selector.setVisible(True)
                return
            self.participant_selector.setVisible(not self.preview_mode)
            self.participant_selector.setEnabled(not self.preview_mode)
            self.participant_selector.addItem(tr("label.no_participant"), None)
            for user_id in self.users_manager.sorted_participant_ids(show_archived=False):
                self.participant_selector.addItem(str(self.users_manager.users[user_id].get("name", "")), user_id)
            self.participant_selector.insertSeparator(self.participant_selector.count())
            self.participant_selector.addItem(tr("action.manage_participants"), "__manage__")
            if self.users_manager.current_user_id:
                index = self.participant_selector.findData(self.users_manager.current_user_id)
                if index >= 0:
                    self.participant_selector.setCurrentIndex(index)
        finally:
            self._updating_participant_selector = False

    def on_participant_selector_changed(self, _index: int) -> None:
        if getattr(self, "_updating_participant_selector", False):
            return
        if self.preview_mode or self.research.is_active:
            self.refresh_participant_selector()
            return
        value = self.participant_selector.currentData()
        if value == "__manage__":
            self.manage_participants()
            self.refresh_participant_selector()
            return
        if value:
            self.users_manager.select_user(str(value))
        else:
            self.users_manager.clear_current_user()
        self.refresh_participant_selector()

    def manage_participants(self) -> bool:
        if self.research.is_active:
            QMessageBox.information(self, tr("dialog.active_research"), tr("message.finish_research"))
            return False
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog.participants"))
        dialog.setMinimumSize(560, 360)
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel(tr("dialog.participants"))
        title.setStyleSheet("font-size:16px;font-weight:600;")
        layout.addWidget(title)
        hint = QLabel(tr("message.participants_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#566273;")
        layout.addWidget(hint)

        participant_combo = QComboBox(dialog)
        participant_combo.setMinimumHeight(34)
        participant_combo.hide()
        participant_table = QTableWidget(0, 3, dialog)
        participant_table.setHorizontalHeaderLabels([tr("field.participant"), tr("field.code"), tr("field.status")])
        participant_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        participant_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        participant_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        participant_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        participant_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        participant_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(participant_table, 1)

        show_archived = QCheckBox(tr("option.show_archived"), dialog)
        layout.addWidget(show_archived)

        feedback = QLabel("")
        feedback.setStyleSheet("color:#9b2c2c;")
        layout.addWidget(feedback)
        layout.addStretch(1)

        action_row = QHBoxLayout()
        new_button = QPushButton(tr("button.new"))
        edit_button = QPushButton(tr("button.edit"))
        delete_button = QPushButton(tr("button.deactivate"))
        reactivate_button = QPushButton(tr("button.reactivate"))
        for button in (new_button, edit_button, delete_button, reactivate_button):
            button.setMinimumHeight(32)
            action_row.addWidget(button)
        layout.addLayout(action_row)

        button_row = QHBoxLayout()
        close_button = QPushButton(tr("button.close"))
        close_button.setDefault(True)
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        def selected_user_id() -> str | None:
            row = participant_table.currentRow()
            if row < 0:
                return None
            item = participant_table.item(row, 0)
            if item is None:
                return None
            value = item.data(Qt.ItemDataRole.UserRole)
            return str(value) if value else None

        def update_buttons() -> None:
            user_id = selected_user_id()
            archived = bool(user_id and not self.users_manager.is_active_user(user_id))
            edit_button.setEnabled(user_id is not None and not archived)
            delete_button.setEnabled(user_id is not None and not archived)
            reactivate_button.setEnabled(user_id is not None and archived)

        def refresh_participants(selected_id: str | None = None) -> None:
            participant_table.setRowCount(0)
            for user_id in self.users_manager.sorted_participant_ids(show_archived=show_archived.isChecked()):
                row = participant_table.rowCount()
                participant_table.insertRow(row)
                name_item = QTableWidgetItem(str(self.users_manager.users[user_id].get("name", "")))
                name_item.setData(Qt.ItemDataRole.UserRole, user_id)
                code_item = QTableWidgetItem(self.users_manager.participant_code(user_id))
                state_item = QTableWidgetItem(tr("status.archived") if not self.users_manager.is_active_user(user_id) else "")
                participant_table.setItem(row, 0, name_item)
                participant_table.setItem(row, 1, code_item)
                participant_table.setItem(row, 2, state_item)
            target_id = selected_id or self.users_manager.current_user_id
            if target_id:
                for row in range(participant_table.rowCount()):
                    item = participant_table.item(row, 0)
                    if item and item.data(Qt.ItemDataRole.UserRole) == target_id:
                        participant_table.selectRow(row)
                        break
            elif participant_table.rowCount():
                participant_table.selectRow(0)
            participant_table.setColumnHidden(2, not show_archived.isChecked())
            update_buttons()

        def show_identifier_error(error: Exception) -> None:
            text = str(error)
            if "required" in text:
                feedback.setText(tr("message.participant_required"))
            elif "already exists" in text:
                feedback.setText(tr("message.participant_duplicate"))
            else:
                feedback.setText(text)

        def ask_participant_name(title_text: str, initial_text: str = "") -> str | None:
            prompt = QDialog(dialog)
            prompt.setWindowTitle(title_text)
            prompt_layout = QVBoxLayout(prompt)
            prompt_layout.setContentsMargins(18, 16, 18, 14)
            prompt_layout.setSpacing(10)
            prompt_layout.addWidget(QLabel(tr("field.participant_name")))
            name_edit = QLineEdit(prompt)
            name_edit.setText(initial_text)
            name_edit.setClearButtonEnabled(True)
            prompt_layout.addWidget(name_edit)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, prompt)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("button.ok"))
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("button.cancel"))
            prompt_layout.addWidget(buttons)
            buttons.accepted.connect(prompt.accept)
            buttons.rejected.connect(prompt.reject)
            if prompt.exec() != QDialog.DialogCode.Accepted:
                return None
            return name_edit.text()

        def create_participant() -> None:
            name = ask_participant_name(tr("button.new_participant"))
            if name is None:
                return
            try:
                user_id = self.users_manager.create_user(name)
            except ValueError as exc:
                show_identifier_error(exc)
                return
            feedback.setText("")
            refresh_participants(user_id)

        def rename_participant() -> None:
            user_id = selected_user_id()
            if user_id is None:
                feedback.setText(tr("message.participant_edit_none"))
                return
            current_name = str(self.users_manager.users[user_id].get("name", ""))
            name = ask_participant_name(tr("button.edit"), current_name)
            if name is None:
                return
            try:
                self.users_manager.rename_user(user_id, name)
            except ValueError as exc:
                show_identifier_error(exc)
                return
            feedback.setText("")
            refresh_participants(user_id)

        def delete_or_archive_participant() -> None:
            user_id = selected_user_id()
            if user_id is None:
                feedback.setText(tr("message.participant_delete_none"))
                return
            if self.users_manager.has_recorded_sessions(user_id, RESULTS_DIR / "sessions"):
                message = tr("message.participant_has_sessions")
            else:
                message = tr("message.participant_delete")
            accepted = QMessageBox.question(
                dialog,
                tr("dialog.deactivate_participant"),
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if accepted != QMessageBox.StandardButton.Yes:
                return
            result = self.users_manager.remove_or_archive_user(user_id, RESULTS_DIR / "sessions")
            if result == "archived":
                feedback.setText(tr("status.participant_archived"))
            else:
                feedback.setText("")
            self.update_research_controls()
            refresh_participants()

        def reactivate_participant() -> None:
            user_id = selected_user_id()
            if user_id is None:
                return
            self.users_manager.reactivate_user(user_id)
            feedback.setText("")
            refresh_participants(user_id)

        refresh_participants()
        new_button.clicked.connect(create_participant)
        edit_button.clicked.connect(rename_participant)
        delete_button.clicked.connect(delete_or_archive_participant)
        reactivate_button.clicked.connect(reactivate_participant)
        show_archived.toggled.connect(lambda _=False: refresh_participants())
        participant_table.itemSelectionChanged.connect(update_buttons)
        participant_table.itemDoubleClicked.connect(lambda _item: rename_participant() if edit_button.isEnabled() else None)
        close_button.clicked.connect(dialog.accept)

        dialog.exec()
        self.update_research_controls()
        return False

    def select_user(self, *, allow_anonymous: bool = False) -> bool:
        return self.manage_participants()

    def prompt_participant_name(self, parent: QWidget, title_text: str, initial_text: str = "") -> str | None:
        prompt = QDialog(parent)
        prompt.setWindowTitle(title_text)
        prompt_layout = QVBoxLayout(prompt)
        prompt_layout.setContentsMargins(18, 16, 18, 14)
        prompt_layout.setSpacing(10)
        prompt_layout.addWidget(QLabel(tr("field.participant_name")))
        name_edit = QLineEdit(prompt)
        name_edit.setText(initial_text)
        name_edit.setClearButtonEnabled(True)
        prompt_layout.addWidget(name_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, prompt)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("button.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("button.cancel"))
        prompt_layout.addWidget(buttons)
        buttons.accepted.connect(prompt.accept)
        buttons.rejected.connect(prompt.reject)
        if prompt.exec() != QDialog.DialogCode.Accepted:
            return None
        return name_edit.text()

    def choose_participant_for_research(self) -> str | None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog.select_participant"))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(QLabel(tr("message.research_participant")))
        combo = QComboBox(dialog)
        for user_id in self.users_manager.sorted_participant_ids(show_archived=False):
            combo.addItem(self.users_manager.participant_display_name(user_id, include_archived=False), user_id)
        layout.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("button.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("button.cancel"))
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if combo.count() == 0 or dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        value = combo.currentData()
        return str(value) if value else None

    def create_participant_for_research(self) -> str | None:
        name = self.prompt_participant_name(self, tr("button.new_participant"))
        if name is None:
            return None
        try:
            return self.users_manager.create_user(name)
        except ValueError as exc:
            text = tr("message.participant_required") if "required" in str(exc) else tr("message.participant_duplicate")
            QMessageBox.information(self, tr("dialog.participants"), text)
            return None

    def ensure_research_participant(self) -> tuple[bool, str, str, str, bool]:
        if self.users_manager.current_user_id:
            return (
                True,
                self.users_manager.current_user_id,
                self.users_manager.get_current_user_name(),
                "participant",
                False,
            )
        decision = QMessageBox(self)
        decision.setWindowTitle(tr("dialog.research"))
        decision.setText(tr("message.research_participant"))
        select_button = decision.addButton(tr("button.select_participant"), QMessageBox.ButtonRole.ActionRole)
        create_button = decision.addButton(tr("button.new_participant"), QMessageBox.ButtonRole.ActionRole)
        anonymous_button = decision.addButton(tr("button.start_anonymous"), QMessageBox.ButtonRole.AcceptRole)
        decision.addButton(tr("button.cancel"), QMessageBox.ButtonRole.RejectRole)
        decision.exec()
        clicked = decision.clickedButton()
        if clicked is select_button:
            user_id = self.choose_participant_for_research()
            if user_id:
                self.users_manager.select_user(user_id)
                return True, user_id, self.users_manager.get_current_user_name(), "participant", False
            return False, "", "", "", False
        if clicked is create_button:
            user_id = self.create_participant_for_research()
            if user_id:
                self.users_manager.select_user(user_id)
                return True, user_id, self.users_manager.get_current_user_name(), "participant", False
            return False, "", "", "", False
        if clicked is anonymous_button:
            return True, "", "", "test", True
        return False, "", "", "", False

    def update_research_controls(self) -> None:
        active = self.research.is_active
        user_mode = self.preview_mode
        self.refresh_participant_selector()
        current_user_name = self.users_manager.get_current_user_name()
        self.research_quick_btn.setText("ON" if active else "OFF")
        self.research_quick_btn.setToolTip(tr("action.research_toggle"))
        # El control ON/OFF se muestra en modo profesional; en modo usuario
        # aparece la barra de anotaciones profesionales en su lugar.
        self.research_quick_btn.setVisible(not user_mode)
        self.research_quick_btn.setEnabled(not user_mode)
        self.professional_annotation_bar.setVisible(user_mode)
        for button in self.professional_annotation_buttons.values():
            button.setEnabled(user_mode and active)
        if hasattr(self, "toggle_research_action"):
            self.toggle_research_action.setEnabled(not user_mode)
        if hasattr(self, "select_user_action"):
            self.select_user_action.setEnabled(not user_mode and not active)

    def toggle_research(self) -> None:
        if self.preview_mode:
            return
        if self.research.is_active:
            was_anonymous = bool(self.research.active_session and self.research.active_session.is_anonymous)
            self.research.finish_session(
                status="completed",
                video_id=self.current_video().video_id,
                video_name=self.current_video().name,
                video_position_ms=int(self.player.position()),
                finish_reason="research_disabled",
            )
            self.users_manager.update_user_session_on_close()
            if was_anonymous:
                self.users_manager.clear_current_user()
        else:
            allowed, user_id, user_name, session_type, is_anonymous = self.ensure_research_participant()
            if not allowed:
                self.update_research_controls()
                return
            self.research.start_session(
                project_id=str(self.project.get("project_id", DEFAULT_PROJECT_ID)),
                project_name=self.project_display_name(),
                video_id=self.current_video().video_id,
                video_name=self.current_video().name,
                video_position_ms=int(self.player.position()),
                user_id=user_id,
                user_name=user_name,
                session_type=session_type,
                is_anonymous=is_anonymous,
                start_time=self.current_video().start_time,
                end_time=self.current_video().end_time,
            )
        self.update_research_controls()

    # Compatibilidad con llamadas existentes.
    def start_research_session(self) -> None:
        if not self.research.is_active:
            self.toggle_research()

    def finish_research_session(self) -> None:
        if self.research.is_active:
            self.toggle_research()

    def _latest_research_summary(self) -> dict[str, object]:
        if self.research.is_active:
            return self.research.build_summary()
        sessions_root = RESULTS_DIR / "sessions"
        if not sessions_root.exists():
            return {}
        for session_dir in sorted((p for p in sessions_root.iterdir() if p.is_dir()), reverse=True):
            summary_path = session_dir / "summary.json"
            if summary_path.exists():
                try:
                    return json.loads(summary_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError):
                    continue
        return {}

    @staticmethod
    def _format_research_summary(summary: dict[str, object]) -> str:
        return format_research_summary(summary, current_language())

    def export_research_csv(self) -> None:
        destination = QFileDialog.getExistingDirectory(
            self,
            tr("dialog.export_csv"),
            str(RESULTS_DIR),
        )
        if not destination:
            return
        try:
            export_sessions_csv(RESULTS_DIR / "sessions", Path(destination))
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("dialog.export_csv"),
                tr("message.export_csv_error", error=str(exc)),
            )
            return
        QMessageBox.information(
            self,
            tr("dialog.export_csv"),
            tr("message.export_csv_success", path=str(Path(destination))),
        )

    def view_research_logs(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog.session_summary"))
        dialog.resize(760, 650)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 14)
        header = QLabel(tr("dialog.session_summary"))
        header.setStyleSheet("font-size:20px;font-weight:700;color:#1d2733;")
        layout.addWidget(header)
        intro = QLabel(tr("message.summary_intro"))
        intro.setStyleSheet("color:#566273;")
        layout.addWidget(intro)
        text = QTextEdit(dialog)
        text.setReadOnly(True)
        text.setPlainText(self._format_research_summary(self._latest_research_summary()))
        text.setStyleSheet("font-family:'Segoe UI',Arial,sans-serif;font-size:14px;background:white;line-height:1.35;")
        layout.addWidget(text, 1)
        row = QHBoxLayout()
        copy_button = QPushButton(tr("button.copy_summary"))
        close_button = QPushButton(tr("button.close"))
        for button in (copy_button, close_button):
            button.setObjectName("summaryActionButton")
            button.setMinimumSize(118, 34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoDefault(False)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row.addWidget(copy_button)
        row.addStretch(1)
        row.addWidget(close_button)
        layout.addLayout(row)

        def copy_summary() -> None:
            vertical_scroll = text.verticalScrollBar().value()
            horizontal_scroll = text.horizontalScrollBar().value()
            previous_focus = QApplication.focusWidget()
            QApplication.clipboard().setText(text.toPlainText())
            text.verticalScrollBar().setValue(vertical_scroll)
            text.horizontalScrollBar().setValue(horizontal_scroll)
            if previous_focus is not None:
                previous_focus.setFocus(Qt.FocusReason.OtherFocusReason)

        copy_button.clicked.connect(copy_summary)
        close_button.clicked.connect(dialog.accept)
        dialog.exec()

    def apply_styles(self) -> None:
        self.setStyleSheet("""
            QMainWindow{background:#edf1f6;}
            QMenuBar{background:#ffffff;color:#1d2733;font-size:15px;padding:4px;}
            #root{background:#edf1f6;}
            #topBar,#videoNav,#videoStage,#controls{background:#fbfdff;border:1px solid #b9c7d8;border-radius:6px;}
            #workspace{background:#edf1f6;}
            #topLabel{font-size:17px;font-weight:600;color:#172033;}
            #toolPanel{background:#fbfdff;border:1px solid #b9c7d8;border-radius:6px;}
            #panelTitle{font-size:12px;color:#2b3645;}
            #videoView{background:#c6ccd4;border:1px solid #718196;}
            #supportPanel{background:#fbfdff;border:1px solid #b9c7d8;border-radius:6px;}
            #supportTitle{font-size:18px;color:#1d2733;}
            #messageCounter{color:#607085;font-size:11px;}
            #hotspotBubble{background:#111111;color:#FFFF00;font-size:20px;font-weight:800;padding:5px 8px;border:0;border-radius:4px;}
            #modeLabel,#userLabel{font-size:13px;color:#4c5a6a;padding:0 5px;}
            #researchLabel{font-size:13px;color:#1d2733;}
            #researchQuickButton,#modeQuickButton{min-height:24px;max-height:26px;border:1px solid #8d99a8;border-radius:2px;background:#d9d9d9;color:#111111;font-size:12px;font-weight:700;padding:0;}
            #researchQuickButton:disabled{color:#555555;background:#d9d9d9;}
            #professionalAnnotationBar{background:transparent;}
            #professionalAnnotationButton{min-height:24px;max-height:26px;border:1px solid #8d99a8;border-radius:2px;background:#f5f5f5;color:#222222;font-size:12px;font-weight:500;padding:0 8px;}
            #professionalAnnotationButton:hover{background:#eef2f6;}
            #professionalAnnotationButton:pressed{background:#dfe6ee;border:1px solid #667789;padding:0 8px;}
            #professionalAnnotationButton:disabled{background:#eceff3;color:#8a94a3;}
            #summaryActionButton{min-height:32px;border:1px solid #8d99a8;border-radius:4px;background:#f5f5f5;color:#222222;padding:0 12px;font-weight:500;}
            #summaryActionButton:hover{background:#eef2f6;}
            #summaryActionButton:pressed{background:#dfe6ee;border:1px solid #667789;padding:0 12px;}
            #addVideoButton{font-size:11px;font-weight:700;line-height:1.1;text-align:center;padding:3px;background:#ffffff;border:1px solid #b9c7d8;border-radius:5px;}
            #addVideoButton:hover{background:#f2f7fc;border-color:#7f9fbd;}
            #videoThumbButton{font-size:12px;font-weight:500;padding:2px;background:#ffffff;border:1px solid #b9c7d8;border-radius:5px;}
            QPushButton{min-height:30px;border:1px solid #9fb0c4;border-radius:6px;background:#ffffff;color:#1d2733;font-weight:600;}
            QWidget#videoSegmentBox{background:#f5f8fc;border:1px solid #b9c7d8;border-radius:5px;}
            QWidget#videoSegmentBox QLabel{font-size:12px;border:0;background:transparent;}
            QWidget#videoSegmentBox QLineEdit{min-height:24px;max-height:26px;padding:0 4px;font-size:12px;}
            QWidget#videoSegmentBox QPushButton{min-height:22px;max-height:24px;padding:0 6px;border-radius:4px;font-size:12px;}
            QPushButton:checked{background:#e6f2ff;border:3px solid #1677c8;color:#0b4f88;}
            QPushButton:disabled{background:#edf1f6;color:#687789;}
            #toolButton{text-align:left;padding-left:8px;font-size:13px;}
            #transportButton,#continueButton{font-size:16px;padding:3px 12px;}
            #supportCard{background:#ffffff;border:0;border-radius:0;}
            #supportConfigureButton,#supportUserButton{background:#f8fafc;border:1px solid #c9d5e3;border-radius:6px;font-size:16px;font-weight:600;}
            QToolButton#videoThumbButton,QToolButton#addVideoButton{background:#ffffff;border:1px solid #b9c7d8;border-radius:5px;color:#1d2733;font-size:14px;}
            QToolButton#videoThumbButton:checked{background:#e6f2ff;border:3px solid #1677c8;}
            QToolButton#addVideoButton{font-size:32px;font-weight:700;color:#1d2733;}
            QCheckBox{font-size:14px;color:#1d2733;}
        """)

    def update_output_geometry(self) -> None:
        return

    def tool_clicked(self, name: str) -> None:
        if self.preview_mode:
            self.set_mode("select")
            self.logger.write("tool_ignored_during_preview", tool=name)
            return
        if name in {"select", "rectangle", "ellipse"}:
            self.set_mode(name)
        elif name == "edit":
            self.edit_selected_hotspot()
        elif name == "delete":
            self.delete_selected_hotspot()

    def set_mode(self, mode: str) -> None:
        if self.preview_mode and mode != "select":
            mode = "select"
        self.mode = mode
        for name, btn in self.tool_buttons.items():
            if btn.isCheckable():
                btn.setChecked(name == mode)
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor if mode in {"rectangle", "ellipse"} else Qt.CursorShape.ArrowCursor)

    def overlap_message(self) -> None:
        QMessageBox.warning(self, tr("dialog.overlap"), tr("message.overlap"))

    def candidate_for_rect(self, rect: QRectF, shape: str, hotspot_id: str = "candidate") -> Hotspot:
        return Hotspot(hotspot_id=hotspot_id, shape=shape, geometry=pixel_to_normalized((rect.x(), rect.y(), rect.width(), rect.height()), FRAME_SIZE))

    def candidate_overlaps_pause(self, hotspot: Hotspot) -> Hotspot | None:
        pause = self.current_pause()
        return first_overlap(hotspot, pause.hotspots) if pause else None

    def creation_conflict(self, rect: QRectF, shape: str) -> tuple[PausePoint | None, Hotspot | None]:
        position_ms = int(self.player.position())
        selected = self.selected_event()
        time_ms = int(selected.time_ms) if selected is not None and abs(position_ms - int(selected.time_ms)) <= PAUSE_TOLERANCE_MS else position_ms
        pause = find_pause(self.pauses, time_ms, PAUSE_TOLERANCE_MS)
        if not pause:
            return None, None
        return pause, first_overlap(self.candidate_for_rect(rect, shape), pause.hotspots)

    def eventFilter(self, obj, event) -> bool:
        if getattr(self, "_closing", False):
            return False
        try:
            viewport = self.view.viewport()
        except RuntimeError:
            return False
        if obj is viewport and self.preview_mode and self.mode in {"rectangle", "ellipse"}:
            self.set_mode("select")
            return False
        if obj is viewport and self.mode in {"rectangle", "ellipse"}:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.player.pause()
                self.clear_output_text()
                p = self.view.mapToScene(event.position().toPoint())
                if QRectF(0, 0, FRAME_WIDTH, FRAME_HEIGHT).contains(p):
                    self._creating = True
                    self._create_shape = self.mode
                    self._create_start = p
                    self._create_rect = self.scene.addRect(QRectF(p, p), QPen(QColor("#FFEA00"), 4, Qt.PenStyle.DashLine))
                    self._create_rect.setZValue(9999)
                    return True
            if event.type() == QEvent.Type.MouseMove and self._creating and self._create_rect and self._create_start:
                p = self.view.mapToScene(event.position().toPoint())
                rect = QRectF(self._create_start, p).normalized().intersected(QRectF(0, 0, FRAME_WIDTH, FRAME_HEIGHT))
                self._create_rect.setRect(rect)
                _, conflict = self.creation_conflict(rect, self._create_shape)
                self._create_rect.setPen(QPen(QColor("#D50000") if conflict else QColor("#FFEA00"), 4, Qt.PenStyle.DashLine))
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and self._creating and self._create_rect and self._create_start:
                p = self.view.mapToScene(event.position().toPoint())
                rect = QRectF(self._create_start, p).normalized().intersected(QRectF(0, 0, FRAME_WIDTH, FRAME_HEIGHT))
                self.scene.removeItem(self._create_rect)
                self._create_rect = None
                self._creating = False
                self._create_start = None
                if rect.width() >= MIN_SIZE_PX and rect.height() >= MIN_SIZE_PX:
                    pause, conflict = self.creation_conflict(rect, self._create_shape)
                    if conflict:
                        self.logger.write("hotspot_overlap_rejected", action="create", pause_time_ms=pause.time_ms if pause else None, candidate_geometry=self.candidate_for_rect(rect, self._create_shape).geometry, conflict_hotspot_id=conflict.hotspot_id, conflict_geometry=conflict.geometry)
                        self.overlap_message()
                        self.set_mode("select")
                        return True
                    self.create_hotspot(rect, self._create_shape)
                self.set_mode("select")
                return True
        return super().eventFilter(obj, event)

    def pause_state(self, time_ms: int) -> str:
        return self.pause_states.get(int(time_ms), "armed")

    def set_pause_state(self, time_ms: int, state: str) -> None:
        self.pause_states[int(time_ms)] = state
        self.update_continue_button()

    def update_continue_button(self) -> None:
        if self.preview_mode:
            enabled = (
                self.active_event_id is not None
                and self._temporal_mode is PlaybackMode.INTERACTION_PAUSED
            )
        else:
            enabled = self.selected_pause_ms is not None and self.pause_state(self.selected_pause_ms) == "active"
        if hasattr(self, "continue_btn"):
            self.continue_btn.setEnabled(enabled)

    def rearm_pauses_before_or_at(self, position_ms: int) -> None:
        changed = []
        for pause in self.pauses:
            if pause.time_ms >= position_ms and self.pause_state(pause.time_ms) == "consumed_for_current_pass":
                self.pause_states[pause.time_ms] = "armed"
                changed.append(pause.time_ms)
                self.research.record_pause_rearmed(
                    pause_event_id=pause.pause_id,
                    video_id=self.current_video().video_id,
                    video_name=self.current_video().name,
                    scheduled_time_ms=int(pause.time_ms),
                    from_ms=int(self._last_position_ms),
                    to_ms=int(position_ms),
                    video_position_ms=int(position_ms),
                )
        if changed:
            self.logger.write("pauses_rearmed", reason="navigation", pause_times=changed, position_ms=position_ms)

    def activate_pause(self, pause: PausePoint, reason: str) -> None:
        self._playback_running = False
        self.player.pause()
        self.player.setPosition(pause.time_ms)
        self._last_position_ms = pause.time_ms
        self.select_event(pause)
        self.active_hotspot_id = None
        self.active_support_id = None
        self.set_pause_state(pause.time_ms, "active")
        self.reload_hotspots_for_pause()
        self.refresh_support_panel()
        self.logger.write("pause_activated", pause_time_ms=pause.time_ms, reason=reason, state="active")

    def clear_active_interaction(self) -> None:
        """Remove every visual/audio element owned by the active PauseEvent."""
        self.hotspot_audio_player.stop()
        if self.support_tts is not None:
            self.support_tts.stop()
        self.clear_output_text()
        self.active_hotspot_id = None
        self.active_support_id = None
        self.current_hotspot_id = None
        for item in list(self.items.values()):
            self.scene.removeItem(item)
        self.items.clear()
        self.active_event_id = None
        # En modo usuario no debe quedar ninguna selección de edición visible.
        if self.preview_mode:
            self.clear_selected_event()
        else:
            self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.refresh_support_panel()
        self.update_continue_button()

    def resume_continue_if_still_pending(self, exit_position: int, video_id: str) -> None:
        if not self.preview_mode:
            return
        if self.current_video().video_id != video_id:
            return
        if self.active_event_id is not None:
            return
        if self.playback_controller.mode is not PlaybackMode.SEEKING:
            return
        if self.playback_controller.pending_continue_position_ms != int(exit_position):
            return
        self.playback_controller.pending_continue_position_ms = None
        self.playback_controller.previous_ms = int(exit_position)
        self.playback_controller.mode = PlaybackMode.PLAYING
        self.playback_controller.running = True
        self.player.play()

    def continue_from_pause(self) -> None:
        pause = self.current_pause()
        if not pause:
            return

        if self.preview_mode and self._temporal_mode is PlaybackMode.INTERACTION_PAUSED:
            event_time_ms = int(pause.time_ms)
            video_id = self.current_video().video_id
            exit_position, next_pause_ms = safe_continue_exit_position(
                event_time_ms,
                self.active_pauses(),
                self.effective_end_time(),
            )
            self.playback_controller.begin_continue(event_time_ms, self.effective_end_time())
            self.playback_controller.pending_continue_position_ms = exit_position
            self.set_pause_state(event_time_ms, "consumed_for_current_pass")

            # El controlador conserva la transición SEEKING hasta que QMediaPlayer
            # confirme el nuevo fotograma mediante positionChanged.
            self.clear_active_interaction()
            self.player.setPosition(exit_position)
            QTimer.singleShot(
                CONTINUE_RESUME_FALLBACK_MS,
                lambda expected=exit_position, expected_video=video_id: self.resume_continue_if_still_pending(expected, expected_video),
            )
            self.update_continue_button()
            self.research.record_continue(
                video_id=self.current_video().video_id,
                video_name=self.current_video().name,
                video_position_ms=event_time_ms,
            )
            self.logger.write(
                "continue_clicked",
                pause_time_ms=event_time_ms,
                exit_position_ms=exit_position,
                post_event_margin_ms=exit_position - event_time_ms,
                next_pause_ms=next_pause_ms,
                engine="pause_event",
                interaction_cleared=True,
                playback_waiting_for_seek=True,
            )
            return

        before_state = self.pause_state(pause.time_ms)
        self.hotspot_audio_player.stop()
        self.clear_output_text()
        self.active_hotspot_id = None
        self.active_support_id = None
        self.set_pause_state(pause.time_ms, "consumed_for_current_pass")
        self.selected_pause_ms = None
        self.reload_hotspots_for_pause()
        self.refresh_support_panel()
        self.research.record_continue(
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            video_position_ms=int(pause.time_ms),
        )
        exit_position, next_pause_ms = safe_continue_exit_position(pause.time_ms, self.active_pauses(), self.effective_end_time(), MARKER_TOLERANCE_MS)
        self.player.setPosition(exit_position)
        self._last_position_ms = exit_position
        self.logger.write("continue_clicked", pause_time_ms=pause.time_ms, before_state=before_state, after_state=self.pause_state(pause.time_ms), exit_position_ms=exit_position, next_pause_ms=next_pause_ms, audio_stopped=True, text_cleared=True)
        self._playback_running = True
        self.player.play()
    def current_pause(self) -> PausePoint | None:
        # Compatibilidad temporal para métodos existentes: nunca mezclar los dos estados.
        return self.active_event() if self.preview_mode else self.selected_event()

    def find_pause_at_current_position(self) -> PausePoint | None:
        return find_pause(self.pauses, int(self.player.position()), PAUSE_TOLERANCE_MS)

    def goto_pause(self, time_ms: int) -> None:
        pause = find_pause(self.pauses, time_ms, PAUSE_TOLERANCE_MS)
        if not pause:
            return
        self.set_pause_state(pause.time_ms, "armed")
        self.logger.write("pause_marker_selected", requested_time_ms=time_ms, pause_time_ms=pause.time_ms)
        if self.preview_mode:
            self.pause_at_temporal_event(pause)
            return
        self.player.pause()
        self.player.setPosition(pause.time_ms)
        self._last_position_ms = pause.time_ms
        self.timeline.blockSignals(True)
        self.timeline.setValue(pause.time_ms)
        self.timeline.blockSignals(False)
        self.select_event(pause)
        self.active_event_id = None
        self.active_hotspot_id = None
        self.active_support_id = None
        self.reload_hotspots_for_pause()
        self.refresh_support_panel(pause.time_ms)
        self.update_continue_button()

    def reload_hotspots_for_pause(self) -> None:
        for item in list(self.items.values()):
            self.scene.removeItem(item)
        self.items.clear()
        self.current_hotspot_id = None
        pause = self.current_pause()
        if pause:
            for hotspot in pause.hotspots:
                self.add_hotspot_item(hotspot)
        self.apply_preview_mode_to_items()

    def add_hotspot_item(self, hotspot: Hotspot) -> None:
        item = HotspotItem(hotspot, self.logger)
        item.changed.connect(self.on_hotspot_geometry_changed)
        item.editRequested.connect(lambda hotspot_id: self.edit_selected_hotspot(hotspot_id))
        item.activated.connect(self.activate_hotspot)
        item.setZValue(10 + len(self.items))
        item.set_preview_mode(self.preview_mode)
        self.scene.addItem(item)
        self.items[hotspot.hotspot_id] = item

    def create_hotspot(self, rect: QRectF, shape: str) -> None:
        position_ms = int(self.player.position())
        selected = self.selected_event()
        time_ms = int(selected.time_ms) if selected is not None else position_ms
        hotspot = Hotspot(
            hotspot_id=str(uuid.uuid4()),
            name="Hotspot",
            shape=shape,
            geometry=pixel_to_normalized((rect.x(), rect.y(), rect.width(), rect.height()), FRAME_SIZE),
            color=DEFAULT_HOTSPOT_COLOR,
            fill_opacity=DEFAULT_FILL_OPACITY,
        )
        pause, created = find_or_create_pause(self.pauses, time_ms, PAUSE_TOLERANCE_MS)
        conflict = first_overlap(hotspot, pause.hotspots)
        if conflict:
            self.logger.write("hotspot_overlap_rejected", action="create", pause_time_ms=pause.time_ms, candidate_geometry=hotspot.geometry, conflict_hotspot_id=conflict.hotspot_id, conflict_geometry=conflict.geometry)
            self.overlap_message()
            if created:
                self.pauses = [p for p in self.pauses if p is not pause]
            return
        pause.hotspots.append(hotspot)
        self.select_event(pause)
        self.logger.write("pause_auto_created" if created else "pause_reused", requested_time_ms=time_ms, pause_time_ms=pause.time_ms, tolerance_ms=PAUSE_TOLERANCE_MS)
        self.logger.write("hotspot_drawn", hotspot_id=hotspot.hotspot_id, shape=shape, geometry=hotspot.geometry)
        self.reload_hotspots_for_pause()
        self.select_hotspot(hotspot.hotspot_id)
        dialog = HotspotContentDialog(hotspot, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.result_hotspot()
            hotspot.message_text = updated.message_text
            hotspot.show_message_text = updated.show_message_text
            hotspot.communication_category = updated.communication_category
            hotspot.color = updated.color
            hotspot.audio_asset = updated.audio_asset
            hotspot.font_family = updated.font_family
            hotspot.font_size_px = updated.font_size_px
            hotspot.font_bold = updated.font_bold
            hotspot.uppercase = updated.uppercase
            hotspot.text_color = updated.text_color
            hotspot.background_color = updated.background_color
            hotspot.background_opacity = updated.background_opacity
            self.logger.write("hotspot_created", hotspot_id=hotspot.hotspot_id, shape=shape, communication_category=hotspot.communication_category, color=hotspot.color, audio_asset=hotspot.audio_asset)
            self.push_history("hotspot_created")
            self.reload_hotspots_for_pause()
            self.select_hotspot(hotspot.hotspot_id)
        else:
            removed_pause = self.cancel_provisional_hotspot(pause, hotspot)
            self.logger.write("hotspot_creation_cancelled", hotspot_id=hotspot.hotspot_id, pause_removed=removed_pause)
            self.reload_hotspots_for_pause()
            self.timeline.set_pauses(self.pauses, self.selected_pause_ms)

    def cancel_provisional_hotspot(self, pause: PausePoint, hotspot: Hotspot) -> bool:
        remove_hotspot_from_pause(pause, hotspot.hotspot_id)
        removed_pause = False
        has_configured_supports = any(
            support.is_configured() for support in normalize_supports(pause.supports)
        )
        if not pause.hotspots and not has_configured_supports:
            self.pauses = [p for p in self.pauses if p is not pause]
            removed_pause = True
            self.selected_pause_ms = None
            self.selected_label.setText(tr("label.selected_pause_none"))
        return removed_pause

    def select_hotspot(self, hotspot_id: str) -> None:
        self.current_hotspot_id = hotspot_id
        for item_id, item in self.items.items():
            item.setSelected((item_id == hotspot_id) and not self.preview_mode)

    def selected_hotspot(self) -> Hotspot | None:
        pause = self.current_pause()
        if not pause:
            return None
        selected = [item for item in self.scene.selectedItems() if isinstance(item, HotspotItem)]
        if selected:
            self.current_hotspot_id = selected[-1].hotspot.hotspot_id
        return next((h for h in pause.hotspots if h.hotspot_id == self.current_hotspot_id), None)

    def edit_selected_hotspot(self, hotspot_id: str | None = None) -> None:
        if self.preview_mode:
            self.logger.write("edit_ignored_during_preview")
            return
        if hotspot_id:
            self.select_hotspot(hotspot_id)
        hotspot = self.selected_hotspot()
        if not hotspot:
            QMessageBox.information(self, tr("dialog.edit_hotspot"), tr("message.select_hotspot"))
            return
        dialog = HotspotContentDialog(hotspot, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.result_hotspot()
            hotspot.message_text = updated.message_text
            hotspot.show_message_text = updated.show_message_text
            hotspot.communication_category = updated.communication_category
            hotspot.color = updated.color
            hotspot.audio_asset = updated.audio_asset
            hotspot.font_family = updated.font_family
            hotspot.font_size_px = updated.font_size_px
            hotspot.font_bold = updated.font_bold
            hotspot.uppercase = updated.uppercase
            hotspot.text_color = updated.text_color
            hotspot.background_color = updated.background_color
            hotspot.background_opacity = updated.background_opacity
            if hotspot.hotspot_id in self.items:
                self.items[hotspot.hotspot_id].update()
            self.logger.write("hotspot_edited", hotspot_id=hotspot.hotspot_id, communication_category=hotspot.communication_category, color=hotspot.color, audio_asset=hotspot.audio_asset)
            self.push_history("hotspot_edited")

    def delete_prompt_text(self, is_last_in_pause: bool) -> tuple[str, str, str, str]:
        title = tr("dialog.delete_hotspot")
        if is_last_in_pause:
            message = tr("message.delete_last_hotspot")
        else:
            message = tr("message.delete_hotspot")
        return title, message, tr("button.delete"), tr("button.cancel")
    def confirm_delete_hotspot(self, is_last_in_pause: bool) -> bool:
        box = QMessageBox(self)
        title, message, delete_text, cancel_text = self.delete_prompt_text(is_last_in_pause)
        box.setWindowTitle(title)
        box.setText(message)
        delete_button = box.addButton(delete_text, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(cancel_text, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(delete_button)
        box.exec()
        confirmed = box.clickedButton() is delete_button
        self.logger.write("hotspot_delete_confirmed" if confirmed else "hotspot_delete_cancelled", last_in_pause=is_last_in_pause)
        return confirmed

    def delete_selected_hotspot(self) -> None:
        if self.preview_mode:
            self.logger.write("delete_ignored_during_preview")
            return
        hotspot = self.selected_hotspot()
        pause = self.current_pause()
        if not hotspot or not pause:
            QMessageBox.information(self, tr("dialog.delete_hotspot"), tr("message.select_hotspot"))
            return
        is_last = len(pause.hotspots) == 1
        if not self.confirm_delete_hotspot(is_last):
            return
        item = self.items.pop(hotspot.hotspot_id, None)
        if item:
            self.scene.removeItem(item)
        remove_hotspot_from_pause(pause, hotspot.hotspot_id)
        removed_pause = False
        has_configured_supports = any(
            support.is_configured() for support in normalize_supports(pause.supports)
        )
        if not pause.hotspots and not has_configured_supports:
            self.pauses = [p for p in self.pauses if p is not pause]
            self.pause_states.pop(pause.time_ms, None)
            removed_pause = True
            self.selected_pause_ms = None
            self.selected_label.setText(tr("label.selected_pause_none"))
        self.current_hotspot_id = None
        self.clear_output_text()
        self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.update_continue_button()
        self.logger.write("hotspot_deleted", hotspot_id=hotspot.hotspot_id, pause_removed=removed_pause)
        self.push_history("hotspot_deleted")
    def on_hotspot_geometry_changed(self, hotspot_id: str, before: dict, after: dict) -> None:
        self.current_hotspot_id = hotspot_id
        pause = self.current_pause()
        hotspot = self.selected_hotspot()
        conflict = first_overlap(hotspot, pause.hotspots) if pause and hotspot else None
        if conflict and hotspot:
            hotspot.geometry = before
            if hotspot_id in self.items:
                self.items[hotspot_id].apply_from_model()
            self.logger.write("hotspot_overlap_rejected", action="move_or_resize", pause_time_ms=pause.time_ms if pause else None, hotspot_id=hotspot_id, candidate_geometry=after, last_valid_geometry=before, conflict_hotspot_id=conflict.hotspot_id, restored=True)
            self.overlap_message()
            return
        self.push_history("hotspot_geometry_changed")

    def toggle_preview_mode(self) -> None:
        requested_preview = self.preview_btn.isChecked()
        if requested_preview and not self.preview_mode and not self.resolve_pending_segment_changes():
            self.preview_btn.blockSignals(True)
            self.preview_btn.setChecked(False)
            self.preview_btn.blockSignals(False)
            return
        self.preview_mode = requested_preview
        if self.preview_mode:
            self.set_mode("select")
        self.mode_label.setText(tr("mode.user" if self.preview_mode else "mode.professional"))
        for name, button in self.tool_buttons.items():
            button.setEnabled(not self.preview_mode)
            button.setToolTip(tr("tooltip.return_edit") if self.preview_mode else button.accessibleName())
        if self.preview_mode:
            self.start_preview_pass()
        else:
            self.finish_preview_pass()
        self.apply_preview_mode_to_items()
        self.update_mode_controls()
        self.refresh_support_panel()
        self.logger.write("preview_mode_entered" if self.preview_mode else "preview_mode_exited")

    def start_preview_pass(self) -> None:
        self._playback_running = False
        self.sync_current_video()
        self.player.pause()
        self._manual_seek_target_ms = None
        self.clear_output_text()
        self.pause_states = {pause.time_ms: "armed" for pause in self.pauses}
        self.active_event_id = None
        self.selected_pause_ms = None
        self.current_hotspot_id = None
        self.active_hotspot_id = None
        self.active_support_id = None
        start = self.effective_start_time()
        self.playback_controller.reset(start)
        self.timeline.blockSignals(True)
        self.timeline.setValue(start)
        self.timeline.blockSignals(False)
        self.timeline.set_pauses(self.pauses, None)
        self.player.setPosition(start)
        self._last_position_ms = start
        self.reload_hotspots_for_pause()
        self.refresh_support_panel()
        self.update_continue_button()
        self.activate_pause_at_start_if_armed("user_mode_entered")
        self.logger.write("preview_pass_started", position_ms=self._last_position_ms, armed_pause_times=[pause.time_ms for pause in self.active_pauses()])

    def finish_preview_pass(self) -> None:
        self._playback_running = False
        self.player.pause()
        self._manual_seek_target_ms = None
        self.clear_output_text()
        self.pause_states = {pause.time_ms: "armed" for pause in self.pauses}
        self.active_event_id = None
        self.current_hotspot_id = None
        self.active_hotspot_id = None
        self.active_support_id = None
        selected = self.selected_event()
        self.selected_pause_ms = selected.time_ms if selected is not None else None
        self.selected_label.setText(
            tr("label.selected_pause", time=format_time(selected.time_ms))
            if selected is not None
            else tr("label.selected_pause_none")
        )
        if selected is not None:
            self.player.setPosition(selected.time_ms)
            self._last_position_ms = selected.time_ms
            self.timeline.blockSignals(True)
            self.timeline.setValue(selected.time_ms)
            self.timeline.blockSignals(False)
        self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.reload_hotspots_for_pause()
        self.refresh_support_panel()
        self.playback_controller.reset(int(self.player.position()))
        self.update_continue_button()
        self.logger.write("preview_pass_finished", position_ms=self._last_position_ms)

    def refresh_hotspot_visibility(self) -> None:
        show = True if self.preview_mode else bool(self.show_hotspots_toggle.isChecked())
        for item in self.items.values():
            item.setVisible(show)

    def apply_preview_mode_to_items(self) -> None:
        for item in self.items.values():
            item.set_preview_mode(self.preview_mode)
        self.refresh_hotspot_visibility()

    def activate_hotspot(self, hotspot_id: str) -> None:
        # Solo puede activarse un hotspot perteneciente al PauseEvent activo.
        pause = self.active_event() if self.preview_mode else self.selected_event()
        hotspot = next((h for h in pause.hotspots if h.hotspot_id == hotspot_id), None) if pause else None
        if pause is None or hotspot is None:
            return

        played_audio = False
        if hotspot.audio_asset:
            audio_path = self.hotspot_audio_asset_path(hotspot.audio_asset)
            played_audio = self.play_interaction_audio(audio_path)
            if played_audio:
                self.logger.write(
                    "hotspot_audio_played",
                    hotspot_id=hotspot_id,
                    audio_asset=hotspot.audio_asset,
                )
            else:
                self.logger.write(
                    "hotspot_audio_error",
                    hotspot_id=hotspot_id,
                    error="audio_file_not_found_or_invalid",
                    audio_asset=hotspot.audio_asset,
                )

        used_tts = False
        text = " ".join(str(hotspot.message_text or "").split())
        if not played_audio and text and getattr(hotspot, HOTSPOT_TTS_FIELD, True) and self.support_tts is not None:
            self.hotspot_audio_player.stop()
            self.support_tts.stop()
            self.support_tts.say(text)
            used_tts = True

        # El registro se produce en el mismo flujo del clic real y conserva
        # el contexto necesario para el resumen.
        self.research.record_hotspot_activation(
            hotspot_id,
            audio_played=played_audio,
            tts_played=used_tts,
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            pause_id=pause.pause_id,
            hotspot_text=hotspot.message_text,
            text=hotspot.message_text,
            communication_category=hotspot.communication_category,
            typology=hotspot.communication_category,
            shape=hotspot.shape,
            audio_available=bool(hotspot.audio_asset),
            tts_enabled=bool(getattr(hotspot, HOTSPOT_TTS_FIELD, True) and text),
            video_position_ms=int(self.player.position()),
        )
        self.logger.write(
            "hotspot_activated",
            hotspot_id=hotspot_id,
            pause_id=pause.pause_id,
            message_text=hotspot.message_text,
            communication_category=hotspot.communication_category,
            audio_played=played_audio,
            tts_played=used_tts,
        )

        self.active_hotspot_id = hotspot_id
        self.active_support_id = None
        if hotspot.show_message_text and hotspot.message_text:
            self.show_hotspot_message(hotspot)
            self.logger.write("message_text_shown", hotspot_id=hotspot_id)
        else:
            self.clear_output_text()

    def show_hotspot_message(self, hotspot: Hotspot) -> None:
        item = self.items.get(hotspot.hotspot_id)
        if not item:
            return
        text = " ".join(str(hotspot.message_text or "").split())
        if hotspot.uppercase:
            text = text.upper()
        text_color = validate_hex_color(hotspot.text_color, HOTSPOT_TEXT_COLOR_DEFAULT)
        background_color = validate_hex_color(hotspot.background_color, HOTSPOT_TEXT_BACKGROUND_DEFAULT)
        background_alpha = opacity_percent_to_alpha(validate_opacity_percent(hotspot.background_opacity))
        background = QColor(background_color)
        background_css = (
            background_color
            if background_alpha == 255
            else f"rgba({background.red()},{background.green()},{background.blue()},{background_alpha})"
        )
        self.output_label.setStyleSheet(
            f"background:{background_css};color:{text_color};padding:6px 10px;border:0;border-radius:5px;"
        )
        self.output_label.setAutoFillBackground(True)
        family = str(hotspot.font_family or HOTSPOT_TEXT_FONT_FAMILY_DEFAULT)
        font = QFont(family)
        font.setPixelSize(validate_font_size(hotspot.font_size_px))
        font.setBold(bool(hotspot.font_bold))
        self.output_label.setFont(font)
        metrics = QFontMetrics(font)
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, 420)
        self.output_label.setText(text)
        width = min(max(metrics.horizontalAdvance(text) + 20, 82), 460)
        height = max(metrics.height() + 14, 38)
        self.output_label.setFixedSize(width, height)
        x, y, item_w, item_h = item.pixel_rect()
        target_x = x + item_w / 2 - width / 2
        target_y = y + item_h + 12
        if target_y + height > FRAME_HEIGHT:
            target_y = y - height - 12
        target_x = clamp(target_x, 0, max(0, FRAME_WIDTH - width))
        target_y = clamp(target_y, 0, max(0, FRAME_HEIGHT - height))
        self.output_proxy.setPos(target_x, target_y)
        self.output_proxy.show()

    def clear_output_text(self) -> None:
        if hasattr(self, "hotspot_audio_player"):
            self.hotspot_audio_player.stop()
        if self.output_label.text():
            self.logger.write("message_text_cleared")
        self.output_label.setText("")
        if hasattr(self, "output_proxy"):
            self.output_proxy.hide()

    def pause_at_temporal_event(self, pause: PausePoint) -> None:
        """Pause at a crossed PauseEvent and load its interaction UI."""
        event_time_ms = int(pause.time_ms)
        self.clear_output_text()
        self.playback_controller.begin_interaction(event_time_ms)
        self.player.pause()
        self.player.setPosition(event_time_ms)
        self.active_event_id = pause.pause_id
        # Una activación de reproducción nunca selecciona el evento para edición.
        self.selected_event_id = None
        self.selected_pause_ms = None
        self.current_hotspot_id = None
        self.active_hotspot_id = None
        self.active_support_id = None
        self.selected_label.setText(tr("label.active_pause", time=format_time(event_time_ms)))
        self.timeline.set_pauses(self.pauses, event_time_ms)
        self.reload_hotspots_for_pause()
        self.refresh_support_panel()
        self.update_continue_button()
        self.research.present_pause(
            pause_event_id=pause.pause_id,
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            scheduled_time_ms=event_time_ms,
            activated_position_ms=event_time_ms,
            hotspots_present=self.research_hotspots_for_pause(pause),
            supports_present=self.research_supports_for_pause(pause),
        )
        self.logger.write(
            "pause_event_engine_triggered",
            pause_time_ms=event_time_ms,
            interaction_ui_loaded=True,
            hotspot_count=len(pause.hotspots),
            visible_support_count=sum(
                1 for support in normalize_supports(pause.supports)
                if support.visible and support.is_configured()
            ),
        )

    def on_position_changed(self, position: int) -> None:
        position = int(position)
        segment_end = self.effective_end_time()
        if segment_end > 0 and position >= segment_end:
            video_id = self.current_video().video_id
            self.player.pause()
            self.playback_controller.stop_playback(segment_end)
            self.clear_active_interaction()
            if position != segment_end:
                self.player.setPosition(segment_end)
            self.timeline.blockSignals(True)
            self.timeline.setValue(segment_end)
            self.timeline.blockSignals(False)
            self.time_label.setText(f"{format_time(segment_end)} / {format_time(self.duration_ms)}")
            if video_id not in self._research_completed_videos:
                self._research_completed_videos.add(video_id)
                self.research.record_event(
                    "video_completed",
                    video_id=video_id,
                    video_name=self.current_video().name,
                    video_position_ms=segment_end,
                    target_type="video",
                    target_id=video_id,
                    start_time=self.current_video().start_time,
                    end_time=self.current_video().end_time,
                )
            return
        manual_seek_target = self._manual_seek_target_ms
        if manual_seek_target is not None:
            if abs(position - manual_seek_target) <= MANUAL_SEEK_CONFIRM_TOLERANCE_MS:
                self._manual_seek_target_ms = None
            elif position < manual_seek_target - MANUAL_SEEK_CONFIRM_TOLERANCE_MS:
                self.timeline.blockSignals(True)
                self.timeline.setValue(manual_seek_target)
                self.timeline.blockSignals(False)
                self.time_label.setText(
                    f"{format_time(manual_seek_target)} / {format_time(self.duration_ms)}"
                )
                return

        decision = self.playback_controller.observe_position(
            position,
            self.active_pauses(),
            user_mode=self.preview_mode,
        )

        if not self.preview_mode:
            selected = self.selected_event()
            if selected is not None and abs(position - int(selected.time_ms)) > PAUSE_TOLERANCE_MS:
                self.clear_selected_event()
                self.reload_hotspots_for_pause()
                self.refresh_support_panel(position)

        if decision.continue_target_ms is not None:
            self.timeline.blockSignals(True)
            self.timeline.setValue(position)
            self.timeline.blockSignals(False)
            self.time_label.setText(
                f"{format_time(position)} / {format_time(self.duration_ms)}"
            )
            if decision.continue_seek_completed:
                self.logger.write(
                    "continue_seek_completed",
                    target_position_ms=decision.continue_target_ms,
                    reported_position_ms=position,
                )
                QTimer.singleShot(0, self.player.play)
            return

        if decision.moved_backward:
            self.rearm_pauses_before_or_at(position)
            if self.preview_mode:
                self.clear_active_interaction()
            self.logger.write(
                "playback_moved_backward",
                from_ms=decision.previous_ms,
                to_ms=position,
            )

        if not self._seeking:
            self.timeline.blockSignals(True)
            self.timeline.setValue(position)
            self.timeline.blockSignals(False)

        self.time_label.setText(
            f"{format_time(position)} / {format_time(self.duration_ms)}"
        )

        if self.preview_mode:
            pause = decision.crossed_event
            self.logger.write(
                "pause_event_engine_check",
                previous_position_ms=decision.previous_ms,
                current_position_ms=position,
                playback_mode=self._temporal_mode.value,
                crossed_pause_time_ms=pause.time_ms if pause else None,
            )
            if pause is not None:
                self.pause_at_temporal_event(pause)
                return

    def on_duration_changed(self, duration: int) -> None:
        self.duration_ms = duration
        try:
            self.current_video().validate_bounds(duration)
        except ValueError as exc:
            self.logger.write("invalid_video_segment_loaded", video_id=self.current_video().video_id, error=str(exc))
        self.timeline.setRange(0, max(1, duration))
        self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.update_segment_controls()
        self.time_label.setText(f"{format_time(self.player.position())} / {format_time(duration)}")

    def begin_slider_seek(self) -> None:
        if self.preview_mode and not self.navigation_enabled_for_user():
            return
        self._manual_seek_target_ms = None
        self.playback_controller.begin_seek(int(self.player.position()))
        self._last_drag_seek_ms = -100000
        self.player.pause()
        self.rearm_pauses_before_or_at(self._seek_start_ms)
        if self.preview_mode:
            self.clear_active_interaction()
        else:
            self.clear_output_text()
            self.clear_selected_event()
            self.reload_hotspots_for_pause()
        self.logger.write("timeline_drag_started", from_ms=self._seek_start_ms)

    def seek_during_drag(self, value: int) -> None:
        if self.preview_mode and not self.navigation_enabled_for_user():
            return
        if self.preview_mode:
            value = self.segment_clamped_position(value)
        self.time_label.setText(f"{format_time(value)} / {format_time(self.duration_ms)}")
        if abs(value - self._last_drag_seek_ms) >= 120:
            self._last_drag_seek_ms = value
            self.player.setPosition(value)

    def finish_slider_seek(self) -> None:
        if self.preview_mode and not self.navigation_enabled_for_user():
            return
        value = self.timeline.value()
        if self.preview_mode:
            value = self.segment_clamped_position(value)
            self.timeline.setValue(value)
        before = int(self._seek_start_ms)
        self.playback_controller.finish_seek(value)
        self._manual_seek_target_ms = value
        self.player.pause()
        self.player.setPosition(value)
        self.research.record_event(
            "video_seeked",
            video_position_ms=value,
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            target_type="timeline",
            target_id="timeline_drag",
            seek_action="slider_drag",
            from_ms=before,
            to_ms=value,
            delta_ms=value - before,
            direction="forward" if value >= before else "backward",
        )
        self.rearm_pauses_before_or_at(value)
        pause = find_pause(self.pauses, value, PAUSE_TOLERANCE_MS)
        if pause and not self.preview_mode:
            self.activate_pause(pause, "timeline_drag")
        else:
            self.clear_selected_event()
            self.reload_hotspots_for_pause()
            self.refresh_support_panel(value)
            self.update_continue_button()
        self.logger.write("timeline_drag_finished", from_ms=self._seek_start_ms, to_ms=value, selected_pause_ms=self.selected_pause_ms)

    def seek_from_click(self, value: int) -> None:
        if self.preview_mode and not self.navigation_enabled_for_user():
            return
        if self.preview_mode:
            value = self.segment_clamped_position(value)
            self.timeline.blockSignals(True)
            self.timeline.setValue(value)
            self.timeline.blockSignals(False)
        before = int(self.player.position())
        self._manual_seek_target_ms = None
        self.playback_controller.begin_seek(before)
        self.player.pause()
        if self.preview_mode:
            # Un desplazamiento manual abandona la interacción activa. Hotspots y
            # supports no reaparecen hasta que la reproducción alcance otra pausa.
            self.clear_active_interaction()
        self.player.setPosition(value)
        self.playback_controller.finish_seek(value)
        self._manual_seek_target_ms = value
        self.research.record_event(
            "video_seeked",
            video_position_ms=value,
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            target_type="timeline",
            target_id="timeline_click",
            seek_action="timeline_click",
            from_ms=before,
            to_ms=value,
            delta_ms=value - before,
            direction="forward" if value >= before else "backward",
        )
        self.rearm_pauses_before_or_at(value)
        pause = find_pause(self.pauses, value, PAUSE_TOLERANCE_MS)
        if pause and not self.preview_mode:
            self.select_event(pause)
            self.reload_hotspots_for_pause()
            self.refresh_support_panel(value)
            self.update_continue_button()
        elif pause:
            self.pause_at_temporal_event(pause)
        else:
            self.clear_selected_event()
            self.reload_hotspots_for_pause()
            self.refresh_support_panel(value)
            self.update_continue_button()
        self.time_label.setText(f"{format_time(value)} / {format_time(self.duration_ms)}")
        self.clear_output_text()
        self.logger.write("timeline_clicked", from_ms=before, to_ms=value, selected_pause_ms=self.selected_pause_ms)

    def on_slider_value_changed(self, value: int) -> None:
        if self._seeking:
            self.time_label.setText(f"{format_time(value)} / {format_time(self.duration_ms)}")

    def toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            position = int(self.player.position())
            self.playback_controller.stop_playback(position)
            self.player.pause()
            self.research.record_event(
                "video_paused",
                video_id=self.current_video().video_id,
                video_name=self.current_video().name,
                video_position_ms=position,
            )
        else:
            self.selected_pause_ms = None
            self.selected_label.setText(tr("label.selected_pause_none"))
            self.timeline.set_pauses(self.pauses, None)
            self.reload_hotspots_for_pause()
            self.clear_output_text()
            current_position = int(self.player.position())
            segment_start = self.effective_start_time()
            segment_end = self.effective_end_time()
            if current_position < segment_start or (segment_end > 0 and current_position >= segment_end):
                current_position = segment_start
                self.player.setPosition(current_position)
                self.playback_controller.reset(current_position)
                self._research_completed_videos.discard(self.current_video().video_id)
            self.rearm_pauses_before_or_at(current_position)
            self._last_position_ms = current_position
            if self.preview_mode:
                nearby_pause = find_pause(self.active_pauses(), current_position, PAUSE_TOLERANCE_MS)
                if nearby_pause and self.pause_state(nearby_pause.time_ms) == "armed":
                    self.pause_at_temporal_event(nearby_pause)
                    return
            self.playback_controller.start_playback(
                current_position,
                user_mode=self.preview_mode,
            )
            self.research.record_event(
                "video_started" if current_position == segment_start else "video_resumed",
                video_id=self.current_video().video_id,
                video_name=self.current_video().name,
                video_position_ms=current_position,
            )
            self.player.play()

    def stop_video(self) -> None:
        previous_position = int(self.player.position())
        start = self.effective_start_time()
        self._manual_seek_target_ms = None
        self.playback_controller.reset(start)
        self.player.stop()
        self.player.setPosition(start)
        self.research.record_event(
            "video_stopped",
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            video_position_ms=previous_position,
            target_type="navigation",
            target_id="stop",
        )
        self.selected_pause_ms = None
        self.selected_label.setText(tr("label.selected_pause_none"))
        self.timeline.set_pauses(self.pauses, None)
        self.reload_hotspots_for_pause()
        self.clear_output_text()
        self.rearm_pauses_before_or_at(start)
        self._last_position_ms = start
        self.timeline.setValue(start)
        self._research_completed_videos.discard(self.current_video().video_id)
        self.activate_pause_at_start_if_armed("video_stopped")

    def go_to_start(self) -> None:
        previous_position = int(self.player.position())
        start = self.effective_start_time()
        self._manual_seek_target_ms = None
        self.playback_controller.reset(start)
        self.hotspot_audio_player.stop()
        self.player.pause()
        self.research.record_event(
            "video_seeked",
            video_id=self.current_video().video_id,
            video_name=self.current_video().name,
            video_position_ms=start,
            target_type="navigation",
            target_id="home",
            seek_action="go_to_start",
            from_ms=previous_position,
            to_ms=start,
            delta_ms=start - previous_position,
            direction="backward" if previous_position > 0 else "none",
        )
        self.clear_output_text()
        self.active_event_id = None
        self.clear_selected_event()
        self.current_hotspot_id = None
        self.active_hotspot_id = None
        self.active_support_id = None
        self.pause_states = {pause.time_ms: "armed" for pause in self.pauses}
        self.timeline.blockSignals(True)
        self.timeline.setValue(start)
        self.timeline.blockSignals(False)
        self.timeline.set_pauses(self.pauses, None)
        self.player.setPosition(start)
        self._last_position_ms = start
        self.reload_hotspots_for_pause()
        self.update_continue_button()
        self.time_label.setText(f"{format_time(start)} / {format_time(self.duration_ms)}")
        self._research_completed_videos.discard(self.current_video().video_id)
        self.activate_pause_at_start_if_armed("go_to_start")
        self.logger.write("home_clicked", position_ms=start, armed_pause_times=[pause.time_ms for pause in self.active_pauses()])

    def update_play_button(self, state) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState and self.preview_mode and not self._seeking:
            self._temporal_mode = PlaybackMode.PLAYING
        elif state != QMediaPlayer.PlaybackState.PlayingState and self._temporal_mode == PlaybackMode.PLAYING:
            self._temporal_mode = PlaybackMode.STOPPED
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText(tr("button.pause"))
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_btn.setText(tr("button.play"))
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def attach_hotspot_tts_to_payload(self, payload: dict) -> dict:
        def copy_pause_values(serialized_pauses: list[dict], live_pauses: list[PausePoint]) -> None:
            for pause_payload, pause in zip(serialized_pauses, live_pauses):
                for hotspot_payload, hotspot in zip(pause_payload.get("hotspots", []), pause.hotspots):
                    hotspot_payload[HOTSPOT_TTS_FIELD] = bool(getattr(hotspot, HOTSPOT_TTS_FIELD, True))

        copy_pause_values(payload.get("pauses", []), self.pauses)
        for video_payload, video in zip(payload.get("videos", []), self.videos):
            copy_pause_values(video_payload.get("pauses", []), video.pauses)
        return payload

    def restore_hotspot_tts_from_payload(self, payload: dict) -> None:
        def restore_pause_values(serialized_pauses: list[dict], live_pauses: list[PausePoint]) -> None:
            for pause_payload, pause in zip(serialized_pauses, live_pauses):
                for hotspot_payload, hotspot in zip(pause_payload.get("hotspots", []), pause.hotspots):
                    setattr(hotspot, HOTSPOT_TTS_FIELD, bool(hotspot_payload.get(HOTSPOT_TTS_FIELD, True)))

        restore_pause_values(payload.get("pauses", []), self.pauses)
        for video_payload, video in zip(payload.get("videos", []), self.videos):
            restore_pause_values(video_payload.get("pauses", []), video.pauses)

    def snapshot(self) -> dict:
        self.sync_current_video()
        payload = serialize_project(deepcopy(self.project), deepcopy(self.pauses), self.duration_ms, deepcopy(self.videos), self.current_video_index)
        return self.attach_hotspot_tts_to_payload(payload)

    def push_history(self, event: str) -> None:
        self.history.push(self.snapshot())
        self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.logger.write(event, selected_pause_ms=self.selected_pause_ms)

    def restore_snapshot(self, payload: dict) -> None:
        self.hotspot_audio_player.stop()
        if self.support_tts is not None:
            self.support_tts.stop()
        self.clear_output_text()
        self.playback_controller.reset(0)
        self._manual_seek_target_ms = None
        self.active_event_id = None
        self.selected_event_id = None
        self.selected_pause_ms = None
        self.current_hotspot_id = None
        self.active_hotspot_id = None
        self.pause_states = {}
        for item in list(self.items.values()):
            self.scene.removeItem(item)
        self.items.clear()
        self.videos = videos_from_project_payload(payload)
        self.current_video_index = int(payload.get("current_video_index", 0))
        self.current_video_index = max(0, min(self.current_video_index, len(self.videos) - 1))
        self.pauses = self.current_video().pauses
        self.load_segment_draft()
        self.playback_controller.reset(self.effective_start_time())
        self.restore_hotspot_tts_from_payload(payload)
        self.video_thumbnails.clear()
        self.thumbnail_requests.clear()
        self.player.setSource(QUrl.fromLocalFile(str(self.resolved_video_path(self.current_video()))))
        self.project = deepcopy(payload)
        self.project["pauses"] = []
        if self.selected_event_id and self.selected_event() is None:
            self.clear_selected_event()
        else:
            selected = self.selected_event()
            self.selected_pause_ms = selected.time_ms if selected is not None else None
            self.timeline.set_pauses(self.pauses, self.selected_pause_ms)
        self.active_event_id = None
        self.refresh_video_nav()
        self.refresh_support_panel()
        self.reload_hotspots_for_pause()
        self.update_segment_controls()
        self.prime_current_video_frame()

    def undo(self) -> None:
        snap = self.history.undo(self.snapshot())
        if snap:
            self.restore_snapshot(snap)
            self.logger.write("undo")

    def redo(self) -> None:
        snap = self.history.redo(self.snapshot())
        if snap:
            self.restore_snapshot(snap)
            self.logger.write("redo")

    def save_json(self, force_dialog: bool = False) -> None:
        path = self.project_path if not force_dialog else None
        if path is None:
            if self.project_path is not None:
                suggested_path = self.project_path
            else:
                documents = QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.DocumentsLocation
                )
                suggested_path = Path(documents) / DEFAULT_PROJECT_FILENAME
            selected, _ = QFileDialog.getSaveFileName(
                self,
                tr("action.save_as"),
                str(suggested_path),
                tr("file.json_filter"),
            )
            if not selected:
                return
            path = Path(selected)
        path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.project_path = path
        self.logger.write("json_saved", filename=path.name)

    def open_json(self) -> None:
        if not self.resolve_pending_segment_changes():
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("action.open_project"), str(RESULTS_DIR), tr("file.json_filter"))
        if path:
            self.load_json(Path(path))

    def load_json(self, path: Path) -> None:
        if not self.resolve_pending_segment_changes():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.restore_snapshot(payload)
            self.project_path = path
            self.history.push(self.snapshot())
            self.logger.write("json_loaded", filename=path.name)
        except Exception as exc:
            QMessageBox.critical(self, tr("dialog.invalid_json"), str(exc))
            self.logger.write("json_load_error", filename=path.name, error=str(exc))

    def closeEvent(self, event) -> None:
        if not self.resolve_pending_segment_changes():
            event.ignore()
            return
        self._closing = True
        try:
            self.view.viewport().removeEventFilter(self)
        except RuntimeError:
            pass
        except AttributeError:
            pass
        try:
            self.player.stop()
            self.player.setVideoOutput(None)
        except RuntimeError:
            pass
        for player, sink in list(getattr(self, "thumbnail_extractors", [])):
            try:
                player.stop()
                player.setVideoOutput(None)
                sink.deleteLater()
                player.deleteLater()
            except RuntimeError:
                pass
        self.thumbnail_extractors.clear()
        self.logger.write("temporal_editor_closed")
        super().closeEvent(event)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=PRODUCT_TITLE)
    parser.add_argument("--json", type=Path, help="Proyecto JSON temporal a cargar")
    args = parser.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setWindowIcon(QIcon(str(APP_ICON)))
    window = EditorWindow(args.json)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
