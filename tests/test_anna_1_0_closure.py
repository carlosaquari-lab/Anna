from __future__ import annotations

import os
import sys
import json
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import hotspot_editor
from hotspot_model import DEFAULT_PROJECT_ID, SCHEMA_VERSION, default_project, videos_from_project_payload
from research_session import ResearchSessionManager
from version import APP_VERSION


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-anna-1-0-closure"])


def _isolated_window(monkeypatch, tmp_path: Path, project: Path | None = None):
    monkeypatch.setattr(hotspot_editor, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(hotspot_editor, "LOG_PATH", tmp_path / "results" / "app_log.jsonl")
    monkeypatch.setattr(hotspot_editor, "USERS_CSV", tmp_path / "anna_data" / "users.csv")
    monkeypatch.setattr(hotspot_editor, "load_language", lambda _root: "en-US")
    monkeypatch.setattr(hotspot_editor, "save_language", lambda *_args: None)
    return hotspot_editor.EditorWindow(project)


def test_application_and_schema_versions_are_independent() -> None:
    assert APP_VERSION == "1.0.0"
    assert SCHEMA_VERSION == "0.4.0-pause-event"
    assert ResearchSessionManager.SCHEMA_VERSION == 2


def test_packaged_app_root_copies_legacy_emma_data_once(monkeypatch, tmp_path: Path) -> None:
    legacy = tmp_path / "Emma"
    legacy.mkdir()
    (legacy / "kept.txt").write_text("legacy", encoding="utf-8")
    monkeypatch.setattr(hotspot_editor.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    current = hotspot_editor.application_data_root()

    assert current == tmp_path / "ANNA"
    assert (current / "kept.txt").read_text(encoding="utf-8") == "legacy"
    assert (legacy / "kept.txt").read_text(encoding="utf-8") == "legacy"


def test_new_project_is_empty_and_uses_anna_identity() -> None:
    project = default_project()
    assert project["project_id"] == DEFAULT_PROJECT_ID == "anna-interactive-video"
    assert project["video"]["source"] == ""
    assert project["videos"][0]["source"] == ""
    assert project["pause_events"] == []


def test_new_project_action_restores_startup_state(monkeypatch, tmp_path: Path) -> None:
    _app()
    window = _isolated_window(monkeypatch, tmp_path)
    try:
        window.project_path = tmp_path / "old.json"
        window.videos[0].source = "old.mp4"
        window.duration_ms = 5000
        window.new_project_action.trigger()
        assert window.project_path is None
        assert window.duration_ms == 0
        assert window.project["project_id"] == "anna-interactive-video"
        assert window.videos[0].source == ""
        assert window.pauses == []
        assert len(window.history.undo_stack) == 1
    finally:
        window.close()


def test_about_help_menu_and_neutral_save_name(monkeypatch, tmp_path: Path) -> None:
    _app()
    window = _isolated_window(monkeypatch, tmp_path)
    try:
        messages = []
        monkeypatch.setattr(
            QMessageBox,
            "information",
            lambda _parent, title, text: messages.append((title, text)),
        )
        window.show_about_anna()
        assert messages[-1][1] == (
            "ANNA — Interactive Video Activities for AAC\n"
            "Version 1.0.0\n\n"
            "Interactive video activity editor for AAC.\n\n"
            "Copyright © 2026 Carlos Máñez-Carvajal\n"
            "License: GPL-3.0-or-later"
        )
        assert [action.text().replace("&", "") for action in window.help_menu.actions()] == [
            "Open sample project",
            "About ANNA"
        ]
        window.change_language("es")
        assert [action.text().replace("&", "") for action in window.help_menu.actions()] == [
            "Abrir proyecto de ejemplo",
            "Acerca de ANNA",
        ]
        window.show_about_anna()
        assert messages[-1][1] == (
            "ANNA — Interactive Video Activities for AAC\n"
            "Versión 1.0.0\n\n"
            "Editor de actividades de vídeo interactivo para CAA.\n\n"
            "Copyright © 2026 Carlos Máñez-Carvajal\n"
            "Licencia: GPL-3.0-or-later"
        )
        assert not hasattr(window, "quick_guide_action")

        requested = []
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda _parent, _title, initial, _filter: requested.append(initial) or ("", ""),
        )
        window.save_json()
        assert Path(requested[-1]).name == "anna_project.json"
    finally:
        window.close()


def test_sample_project_is_not_loaded_at_startup_and_its_resources_resolve(monkeypatch, tmp_path: Path) -> None:
    _app()
    demo = Path(hotspot_editor.__file__).parent / "demo_project" / "washing_hands.json"
    blank = _isolated_window(monkeypatch, tmp_path)
    try:
        assert blank.videos[0].source == ""
    finally:
        blank.close()

    payload = json.loads(demo.read_text(encoding="utf-8"))
    videos = videos_from_project_payload(payload)
    assert [Path(video.source).name for video in videos] == [
        "VID_20260906_121554.mp4",
        "VID_20260906_121715.mp4",
    ]
    assert all((Path(hotspot_editor.__file__).parent / video.source).is_file() for video in videos)
    image_assets = [
        support.image_asset
        for video in videos
        for pause in video.pauses
        for support in pause.supports
        if support.image_asset
    ]
    assert set(image_assets) == {
        "assets/supports/images/support_85c3b242f5bd4db49e9c6d543860c8cc.jpg"
    }
    assert all((Path(hotspot_editor.__file__).parent / asset).is_file() for asset in image_assets)


def test_help_action_opens_packaged_sample_through_normal_loader(monkeypatch, tmp_path: Path) -> None:
    _app()
    window = _isolated_window(monkeypatch, tmp_path)
    try:
        loaded = []
        monkeypatch.setattr(window, "load_json", lambda path: loaded.append(path))
        window.open_sample_project_action.trigger()

        expected = Path(hotspot_editor.__file__).parent / "demo_project" / "washing_hands.json"
        assert loaded == [expected]
        assert expected.is_file()
        assert all((Path(hotspot_editor.__file__).parent / video).is_file() for video in (
            "demo_project/videos/VID_20260906_121554.mp4",
            "demo_project/videos/VID_20260906_121715.mp4",
        ))
        assert (
            Path(hotspot_editor.__file__).parent
            / "assets/supports/images/support_85c3b242f5bd4db49e9c6d543860c8cc.jpg"
        ).is_file()
        spec = (Path(hotspot_editor.__file__).parent / "ANNA.spec").read_text(encoding="utf-8")
        assert '("demo_project", "demo_project")' in spec
    finally:
        window.close()


def test_production_sources_have_no_improper_legacy_brand_references() -> None:
    root = Path(hotspot_editor.__file__).parent
    production = [
        path
        for path in root.glob("*.py")
        if path.name not in {"data_storage.py"}
    ]
    prohibited = []
    for path in production:
        text = path.read_text(encoding="utf-8").lower()
        for brand in ("lola", "sara", "carla"):
            if brand in text:
                prohibited.append((path.name, brand))
    assert prohibited == []

    compatibility = (root / "data_storage.py").read_text(encoding="utf-8")
    assert 'DATA_DIR_NAME = "anna_data"' in compatibility
    assert 'LEGACY_DATA_DIR_NAMES = ("emma_data", "lola_data")' in compatibility
