import json
import os
import sys
import ast
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QAbstractButton, QDialog, QLabel, QMessageBox, QTableWidget

import hotspot_editor
import localization


class FakeTextToSpeech:
    available_locale_names = ["en_US", "es_ES"]
    constructor_args = []

    def __init__(self, *args):
        self.constructor_args.append(args)
        self.locales = []

    def availableLocales(self):
        return [QLocale(name) for name in self.available_locale_names]

    def setLocale(self, locale):
        self.locales.append(locale.name())

    def stop(self):
        pass


def _app():
    return QApplication.instance() or QApplication([])


def _menu_titles(window):
    return [action.text().replace("&", "") for action in window.menuBar().actions()]


def test_tts_locale_follows_initial_and_changed_interface_language(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(localization, "settings_path", lambda _root: tmp_path / "preferences.json")
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    monkeypatch.setattr(hotspot_editor, "save_language", lambda *_args: None)
    monkeypatch.setattr(hotspot_editor, "QTextToSpeech", FakeTextToSpeech)
    monkeypatch.setattr(FakeTextToSpeech, "constructor_args", [])
    window = hotspot_editor.EditorWindow()
    try:
        assert window.support_tts.constructor_args == [("sapi", window)]
        assert window.support_tts.locales == ["en_US"]
        window.change_language("es")
        assert window.support_tts.locales == ["en_US", "es_ES"]
        window.change_language("en-US")
        assert window.support_tts.locales == ["en_US", "es_ES", "en_US"]
    finally:
        window.close()


def test_tts_locale_keeps_current_locale_when_language_is_unavailable(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(localization, "settings_path", lambda _root: tmp_path / "preferences.json")
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    monkeypatch.setattr(hotspot_editor, "QTextToSpeech", FakeTextToSpeech)
    monkeypatch.setattr(FakeTextToSpeech, "available_locale_names", ["fr_FR"])
    window = hotspot_editor.EditorWindow()
    try:
        assert window.support_tts.locales == []
    finally:
        window.close()


def test_brand_title_subtitle_and_first_start_default(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(localization, "settings_path", lambda _root: tmp_path / "preferences.json")
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    window = hotspot_editor.EditorWindow()
    try:
        assert "ANNA" in window.windowTitle()
        assert localization.PRODUCT_SUBTITLE in window.windowTitle()
        assert window.language == "en-US"
        assert _menu_titles(window) == ["File", "Mode", "Research", "Language", "Help"]
        assert [a.text() for a in window.language_menu.actions()] == [
            "English (United States)",
            "Español",
        ]
        assert window.professional_annotation_buttons["adequate"].text() == "Appropriate"
        assert window.tool_buttons["select"].text() == "Select/move"
        assert window.participant_selector.currentText() == "No participant"
        assert window.windowTitle() == localization.PRODUCT_TITLE
    finally:
        window.close()


def _dialog_texts(dialog):
    texts = [dialog.windowTitle()]
    texts.extend(label.text() for label in dialog.findChildren(QLabel) if label.text())
    texts.extend(button.text() for button in dialog.findChildren(QAbstractButton) if button.text())
    for table in dialog.findChildren(QTableWidget):
        texts.extend(
            table.horizontalHeaderItem(i).text()
            for i in range(table.columnCount())
            if table.horizontalHeaderItem(i)
        )
    return texts


def test_dynamic_research_and_participant_dialogs_are_bilingual(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(localization, "settings_path", lambda _root: tmp_path / "preferences.json")
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    monkeypatch.setattr(hotspot_editor, "save_language", lambda *_args: None)
    window = hotspot_editor.EditorWindow()
    try:
        research_dialogs = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: research_dialogs.append(self) or 0)
        window.ensure_research_participant()
        assert _dialog_texts(research_dialogs[-1]) == [
            "Research",
            "Select the participant for this research session.",
            "Select participant",
            "New participant…",
            "Start anonymous session",
            "Cancel",
        ]

        participant_dialogs = []
        monkeypatch.setattr(QDialog, "exec", lambda self: participant_dialogs.append(self) or 0)
        window.manage_participants()
        english = _dialog_texts(participant_dialogs[-1])
        for expected in ("Participants", "Select a registered participant or add a new one.", "Participant", "Code", "Show archived", "New…", "Edit…", "Deactivate…", "Reactivate", "Close"):
            assert expected in english

        window.change_language("es")
        research_dialogs.clear()
        window.ensure_research_participant()
        assert _dialog_texts(research_dialogs[-1]) == [
            "Investigación",
            "Selecciona el participante de esta sesión de investigación.",
            "Seleccionar participante",
            "Nuevo participante…",
            "Iniciar sesión anónima",
            "Cancelar",
        ]
        participant_dialogs.clear()
        window.manage_participants()
        spanish = _dialog_texts(participant_dialogs[-1])
        for expected in ("Participantes", "Selecciona un participante registrado o añade uno nuevo.", "Participante", "Código", "Mostrar archivados", "Nuevo…", "Editar…", "Dar de baja…", "Reactivar", "Cerrar"):
            assert expected in spanish
    finally:
        window.close()


def test_automatic_video_name_and_title_refresh_without_mutating_identity(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(localization, "settings_path", lambda _root: tmp_path / "preferences.json")
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    monkeypatch.setattr(hotspot_editor, "save_language", lambda *_args: None)
    window = hotspot_editor.EditorWindow()
    try:
        window.videos[0].name = "Vídeo 1"
        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: True)
        monkeypatch.setattr(window, "request_video_thumbnail", lambda _video: None)
        window.refresh_video_nav()
        assert window.project_display_name() == "Video 1"
        assert window.windowTitle() == f"{localization.PRODUCT_TITLE} — Video 1"
        window.change_language("es")
        assert window.project_display_name() == "Vídeo 1"
        assert window.windowTitle() == f"{localization.PRODUCT_TITLE} — Vídeo 1"
        window.change_language("en-US")
        assert window.project_display_name() == "Video 1"
        assert window.videos[0].name == "Vídeo 1"
    finally:
        window.close()


def test_catalogs_match_and_known_visible_literals_are_not_direct():
    assert set(localization.EN_US) == set(localization.ES)
    source_path = Path(hotspot_editor.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    visible_calls = {
        "QLabel", "QPushButton", "QCheckBox", "QAction", "addMenu", "addAction",
        "setText", "setWindowTitle", "setToolTip", "setAccessibleName",
    }
    prohibited = {
        "Seleccionar/mover", "Vídeo 1", "Sin participante", "Participantes",
        "Investigación", "Cancelar", "Guardar", "Abrir proyecto…",
    }
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if name not in visible_calls:
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and argument.value in prohibited:
                found.append((node.lineno, argument.value))
    assert found == []


def test_hotspot_support_delete_and_summary_surfaces_are_bilingual(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(localization, "settings_path", lambda _root: tmp_path / "preferences.json")
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    monkeypatch.setattr(hotspot_editor, "save_language", lambda *_args: None)
    window = hotspot_editor.EditorWindow()
    try:
        hotspot = hotspot_editor.Hotspot("h-visible", message_text="User text")
        support = hotspot_editor.SupportItem("s-visible", "Apoyo 1", text="User support")
        hotspot_dialog = hotspot_editor.HotspotContentDialog(hotspot, window)
        support_dialog = hotspot_editor.SupportConfigDialog(support, localization.tr("support.automatic_name", number=1), window)
        assert hotspot_dialog.windowTitle() == "Hotspot content"
        assert support_dialog.windowTitle() == "Configure Support 1"
        assert hotspot_dialog.message.toPlainText() == "User text"
        assert support_dialog.text_edit.toPlainText() == "User support"
        assert window.delete_prompt_text(False) == (
            "Delete hotspot", "Do you want to delete this hotspot?", "Delete", "Cancel"
        )
        english_summary = hotspot_editor.format_research_summary(
            {"user_name": "Ana", "duration_ms": 1000}, "en-US"
        )
        assert "SESSION SUMMARY" in english_summary
        assert "Participant: Ana" in english_summary

        hotspot_dialog.close()
        support_dialog.close()
        window.change_language("es")
        hotspot_dialog = hotspot_editor.HotspotContentDialog(hotspot, window)
        support_dialog = hotspot_editor.SupportConfigDialog(support, localization.tr("support.automatic_name", number=1), window)
        assert hotspot_dialog.windowTitle() == "Contenido del hotspot"
        assert support_dialog.windowTitle() == "Configurar Apoyo 1"
        assert window.delete_prompt_text(False) == (
            "Eliminar hotspot", "¿Desea eliminar este hotspot?", "Eliminar", "Cancelar"
        )
        spanish_summary = hotspot_editor.format_research_summary(
            {"user_name": "Ana", "duration_ms": 1000}, "es"
        )
        assert "RESUMEN DE LA SESIÓN" in spanish_summary
        assert "Participante: Ana" in spanish_summary
        assert hotspot_dialog.message.toPlainText() == "User text"
        assert support_dialog.text_edit.toPlainText() == "User support"
        hotspot_dialog.close()
        support_dialog.close()
    finally:
        window.close()


def test_complete_basic_switch_and_persistence(monkeypatch, tmp_path):
    _app()
    preference = tmp_path / "preferences.json"
    monkeypatch.setattr(localization, "settings_path", lambda _root: preference)
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    monkeypatch.setattr(hotspot_editor, "save_language", localization.save_language)
    window = hotspot_editor.EditorWindow()
    try:
        window.change_language("es")
        assert _menu_titles(window) == ["Archivo", "Modo", "Investigación", "Idioma", "Ayuda"]
        assert [window.professional_annotation_buttons[k].text() for k in ("turn", "adequate", "review")] == [
            "Turno", "Adecuada", "Revisar"
        ]
        assert json.loads(preference.read_text(encoding="utf-8"))["language"] == "es"
        window.change_language("en-US")
        assert _menu_titles(window) == ["File", "Mode", "Research", "Language", "Help"]
        assert [window.professional_annotation_buttons[k].text() for k in ("turn", "adequate", "review")] == [
            "Turn", "Appropriate", "Review"
        ]
        assert json.loads(preference.read_text(encoding="utf-8"))["language"] == "en-US"
    finally:
        window.close()


def test_legacy_project_load_does_not_translate_content(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(localization, "settings_path", lambda _root: tmp_path / "preferences.json")
    monkeypatch.setattr(hotspot_editor, "load_language", localization.load_language)
    hotspot = hotspot_editor.Hotspot(
        hotspot_id="legacy-hotspot",
        name="Hotspot antiguo",
        shape="rectangle",
        geometry={"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
        message_text="Quiero jugar",
    )
    pause = hotspot_editor.PausePoint(pause_id="legacy-pause", time_ms=1000, hotspots=[hotspot])
    video = hotspot_editor.VideoEntry(
        "legacy-video", "Vídeo creado por la profesional", "", [pause]
    )
    payload = hotspot_editor.serialize_project(
        hotspot_editor.default_project(), [pause], 2000, [video], 0
    )
    payload["project_name"] = "Proyecto antiguo de Lola"
    legacy = tmp_path / "legacy_lola.json"
    legacy.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    window = hotspot_editor.EditorWindow(legacy)
    try:
        original = window.videos[0].pauses[0].hotspots[0].message_text
        window.change_language("es")
        window.change_language("en-US")
        assert original == "Quiero jugar"
        assert window.videos[0].name == "Vídeo creado por la profesional"
        assert window.project["project_name"] == "Proyecto antiguo de Lola"
    finally:
        window.close()
