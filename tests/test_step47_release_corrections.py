from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

import hotspot_editor
from hotspot_editor import EditorWindow
from research_session import ResearchSessionManager
from users_manager import UsersManager


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_participant_selector_has_the_four_required_mode_states(tmp_path: Path) -> None:
    application = app()
    window = EditorWindow(auto_show=False)
    try:
        manager = UsersManager(tmp_path / "users.csv")
        participant_id = manager.create_user("Participant")
        manager.select_user(participant_id)
        window.users_manager = manager

        window.preview_mode = False
        window.research.active_session = None
        window.update_research_controls()
        assert not window.participant_selector.isHidden()
        assert window.participant_selector.isEnabled()

        window.research.active_session = SimpleNamespace(status="active", is_anonymous=False)
        window.update_research_controls()
        assert not window.participant_selector.isHidden()
        assert not window.participant_selector.isEnabled()

        window.preview_mode = True
        window.research.active_session = None
        window.update_research_controls()
        assert window.participant_selector.isHidden()
        assert not window.participant_selector.isEnabled()

        window.research.active_session = SimpleNamespace(status="active", is_anonymous=False)
        window.update_research_controls()
        assert not window.participant_selector.isHidden()
        assert not window.participant_selector.isEnabled()
    finally:
        window.close()
        application.processEvents()


def test_participant_change_handler_rejects_user_mode_even_if_widget_is_enabled(tmp_path: Path) -> None:
    application = app()
    window = EditorWindow(auto_show=False)
    try:
        manager = UsersManager(tmp_path / "users.csv")
        first_id = manager.create_user("First")
        second_id = manager.create_user("Second")
        manager.select_user(first_id)
        window.users_manager = manager
        window.preview_mode = True
        window.research.active_session = None
        window.refresh_participant_selector()

        window.participant_selector.setEnabled(True)
        window.participant_selector.setVisible(True)
        second_index = window.participant_selector.findData(second_id)
        window.participant_selector.setCurrentIndex(second_index)

        assert manager.current_user_id == first_id
        assert window.participant_selector.currentData() == first_id
        assert window.participant_selector.isHidden()
        assert not window.participant_selector.isEnabled()
    finally:
        window.close()
        application.processEvents()


def test_csv_menu_flow_uses_existing_exporter_and_creates_expected_files(monkeypatch, tmp_path: Path) -> None:
    application = app()
    results_dir = tmp_path / "results"
    destination = tmp_path / "export"
    manager = ResearchSessionManager(results_dir / "sessions")
    manager.start_session(project_id="project", project_name="Project", video_id="video", video_position_ms=0)
    manager.record_event("video_started", video_position_ms=0)
    manager.finish_session(video_position_ms=0)

    window = EditorWindow(auto_show=False)
    calls: list[tuple[Path, Path]] = []
    real_exporter = hotspot_editor.export_sessions_csv

    def recording_exporter(sessions_root: Path, export_dir: Path):
        calls.append((sessions_root, export_dir))
        return real_exporter(sessions_root, export_dir)

    try:
        monkeypatch.setattr(hotspot_editor, "RESULTS_DIR", results_dir)
        monkeypatch.setattr(hotspot_editor, "export_sessions_csv", recording_exporter)
        monkeypatch.setattr(hotspot_editor.QFileDialog, "getExistingDirectory", lambda *_args: str(destination))
        monkeypatch.setattr(hotspot_editor.QMessageBox, "information", lambda *_args: None)
        monkeypatch.setattr(hotspot_editor.QMessageBox, "critical", lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected export error")))

        window.export_csv_action.trigger()

        assert calls == [(results_dir / "sessions", destination)]
        assert (destination / "events.csv").exists()
        assert (destination / "session_summaries.csv").exists()
    finally:
        window.close()
        application.processEvents()


def test_csv_export_cancel_is_a_no_op_and_errors_are_controlled(monkeypatch, tmp_path: Path) -> None:
    application = app()
    window = EditorWindow(auto_show=False)
    calls: list[str] = []
    try:
        monkeypatch.setattr(hotspot_editor.QFileDialog, "getExistingDirectory", lambda *_args: "")
        monkeypatch.setattr(hotspot_editor, "export_sessions_csv", lambda *_args: calls.append("export"))
        window.export_research_csv()
        assert calls == []

        monkeypatch.setattr(hotspot_editor.QFileDialog, "getExistingDirectory", lambda *_args: str(tmp_path))
        monkeypatch.setattr(hotspot_editor, "export_sessions_csv", lambda *_args: (_ for _ in ()).throw(OSError("blocked")))
        monkeypatch.setattr(hotspot_editor.QMessageBox, "critical", lambda *_args: calls.append("error"))
        window.export_research_csv()
        assert calls == ["error"]
    finally:
        window.close()
        application.processEvents()
