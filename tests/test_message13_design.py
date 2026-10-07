from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

import hotspot_editor
import hotspot_model


EXPECTED_CATEGORIES = [
    "No especificado",
    "Persona / nombre propio",
    "Sustantivo / objeto",
    "Verbo / acción",
    "Adjetivo",
    "Adverbio",
    "Expresión social",
    "Palabra funcional",
    "Lugar",
    "Otro",
]


def app() -> QApplication:
    return QApplication.instance() or QApplication(["message13-design"])


def test_hotspots_and_supports_share_exact_category_source_and_defaults():
    assert list(hotspot_model.COMMUNICATION_CATEGORIES.values()) == EXPECTED_CATEGORIES
    assert len(hotspot_model.COMMUNICATION_CATEGORIES) == 10
    assert hotspot_model.Hotspot("h").communication_category == "unspecified"
    assert hotspot_model.SupportItem("s").communication_category == "unspecified"
    assert hotspot_model.SupportItem("s").visible is True

    hotspot = hotspot_model.Hotspot.from_dict(
        {"hotspot_id": "h", "communication_category": "descriptor"}
    )
    support = hotspot_model.SupportItem.from_dict(
        {"support_id": "s", "communication_category": "descriptor"}
    )
    assert hotspot.communication_category == "adjective"
    assert support.communication_category == "adjective"
    assert hotspot_model.Hotspot.from_dict(
        {"hotspot_id": "h2", "communication_category": "priority_emergency"}
    ).communication_category == "other"
    assert hotspot_model.SupportItem.from_dict(
        {"support_id": "s2", "communication_category": "Prioridad / emergencia"}
    ).communication_category == "other"
    assert hotspot_model.HOTSPOT_MESSAGE_MAX_CHARS == 40
    assert len(hotspot_model.clamp_hotspot_message("x" * 90)) == 40


def test_support_image_widgets_keep_aspect_ratio_and_original_pixmap():
    app()
    original = QPixmap(800, 200)
    original.fill(QColor("#2266AA"))

    label = hotspot_editor.AspectRatioPixmapLabel()
    label.resize(240, 135)
    label.set_original_pixmap(original)
    shown = label.pixmap()
    assert label.original_pixmap.size() == QSize(800, 200)
    assert shown.width() <= 240
    assert shown.height() <= 135
    assert abs((shown.width() / shown.height()) - 4.0) < 0.05

    button = hotspot_editor.SupportImageButton()
    button.setText("Imagen")
    button.resize(188, 116)
    button.set_original_pixmap(original)
    first_size = button.iconSize()
    button.resize(188, 132)
    button.update_icon_size()
    assert button.original_pixmap.size() == QSize(800, 200)
    assert button.iconSize().width() <= 176
    assert button.iconSize().height() <= 100
    assert button.iconSize().height() >= first_size.height()


def test_menu_structure_header_mode_texts_and_icons_are_design_safe():
    app()
    hotspot_editor.EditorWindow.request_video_thumbnail = lambda self, video: None
    hotspot_editor.EditorWindow.prime_current_video_frame = lambda self: None
    hotspot_editor.VIDEO_PATH = Path(__file__).resolve().parent / "missing_design_video.mp4"
    window = hotspot_editor.EditorWindow()
    try:
        menus = [action.text() for action in window.menuBar().actions()]
        assert menus[0] == "File"
        assert menus[1] == "Mode"
        assert menus[-2:] == ["Language", "Help"]
        assert len(menus) == 5
        assert "Proyecto" not in menus

        file_actions = [
            action.text()
            for action in window.file_menu.actions()
            if not action.isSeparator()
        ]
        assert file_actions[0] == "New project"
        assert file_actions[2] == "Save"
        assert file_actions[-1] == "Exit"
        assert "Properties…" not in file_actions
        assert len(file_actions) == 7

        research_actions = [
            action.text()
            for action in window.research_menu.actions()
            if not action.isSeparator()
        ]
        assert research_actions[0].startswith("Enable / disable")
        assert research_actions[1].startswith("Manage participants")
        assert research_actions[2].startswith("Session summary")
        assert research_actions[3] == "Export CSV…"
        assert len(research_actions) == 4

        assert "Lola · Proyecto:" not in window.top_label.text()
        assert "Proyecto:" not in window.top_label.text()
        assert window.top_label.text()
        assert "ANNA" in window.windowTitle()

        assert window.mode_label.text() == "Professional mode"
        assert window.mode_quick_btn.toolTip() == "User mode"
        assert window.preview_btn.toolTip()
        assert window.mode_quick_btn.toolTip()

        for name in ["select", "rectangle", "ellipse", "edit", "delete"]:
            assert not window.tool_buttons[name].icon().isNull()
            assert window.tool_buttons[name].toolTip()
    finally:
        window.close()

def test_support_text_limit_and_visible_defaults_are_synchronized():
    app()
    new_support = hotspot_model.SupportItem("support_1", text="Nuevo")
    new_dialog = hotspot_editor.SupportConfigDialog(new_support, "Apoyo 1")
    try:
        assert new_dialog.visible.isChecked() is True
        new_dialog.text_edit.setPlainText("x" * 60)
        assert new_dialog.text_counter.text() == "40/40"
        assert new_dialog.result_support().text == "x" * 40
        assert new_dialog.result_support().visible is True
    finally:
        new_dialog.close()

    old_support = hotspot_model.SupportItem.from_dict(
        {"support_id": "support_1", "text": "Antiguo visible no", "visible": False}
    )
    old_dialog = hotspot_editor.SupportConfigDialog(old_support, "Apoyo 1")
    try:
        assert old_dialog.visible.isChecked() is False
        assert old_dialog.result_support().visible is False
    finally:
        old_dialog.close()


def test_visible_support_appears_only_when_pause_event_is_active():
    app()
    hotspot_editor.EditorWindow.request_video_thumbnail = lambda self, video: None
    hotspot_editor.EditorWindow.prime_current_video_frame = lambda self: None
    hotspot_editor.VIDEO_PATH = Path(__file__).resolve().parent / "missing_design_video.mp4"
    window = hotspot_editor.EditorWindow()
    try:
        visible_support = hotspot_model.SupportItem(
            "support_1", "Apoyo 1", text="Visible", visible=True
        )
        hidden_support = hotspot_model.SupportItem.from_dict(
            {"support_id": "support_2", "label": "Apoyo 2", "text": "Oculto", "visible": False, "position": 1}
        )
        pause = hotspot_model.PauseEvent(
            "pause-supports",
            4000,
            [hotspot_model.Hotspot("h")],
            [visible_support, hidden_support],
        )
        window.pauses = [pause]
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.pause_at_temporal_event(pause)
        buttons = []
        for index in range(window.support_buttons_layout.count()):
            card = window.support_buttons_layout.itemAt(index).widget()
            if card is not None:
                buttons.extend(card.findChildren(hotspot_editor.SupportImageButton))
        visible_buttons = [button for button in buttons if not button.isHidden() and button.isEnabled()]
        assert len(visible_buttons) == 1
        assert visible_buttons[0].text() == "Visible"
    finally:
        window.close()
