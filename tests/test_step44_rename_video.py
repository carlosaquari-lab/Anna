import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QToolButton

from hotspot_editor import EditorWindow
from hotspot_model import History, Hotspot, PausePoint, SupportItem, VideoEntry, videos_from_project_payload


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_window(monkeypatch=None) -> EditorWindow:
    app()
    window = EditorWindow(auto_show=False)
    window.videos = [
        VideoEntry(
            "video-1", "Video 1", "first.mp4",
            [PausePoint("pause-1", 1_000, [Hotspot("hotspot-1")], [SupportItem("support_1", text="Support")])],
            100, 9_000,
        ),
        VideoEntry("video-2", "Video 2", "second.mp4", []),
    ]
    window.current_video_index = 0
    window.pauses = window.videos[0].pauses
    window.load_segment_draft()
    if monkeypatch is not None:
        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: True)
    window.refresh_video_nav()
    return window


def close_window(window: EditorWindow) -> None:
    window.discard_segment_draft()
    window.close()


def video_button(window: EditorWindow, name: str) -> QToolButton:
    return next(button for button in window.video_nav.findChildren(QToolButton) if button.text() == name)


def test_valid_rename_strips_and_preserves_all_video_content(monkeypatch, tmp_path: Path) -> None:
    window = make_window(monkeypatch)
    video = window.videos[0]
    source_file = tmp_path / "first.mp4"
    source_file.write_bytes(b"video")
    video.source = str(source_file)
    original = (video.video_id, video.source, video.start_time, video.end_time, video.pauses)
    try:
        assert window.rename_video(0, "  Actividad con Álex  ")
        assert video.name == "Actividad con Álex"
        assert (video.video_id, video.source, video.start_time, video.end_time, video.pauses) == original
        assert video.pauses[0].hotspots[0].hotspot_id == "hotspot-1"
        assert video.pauses[0].supports[0].text == "Support"
        assert source_file.exists()
    finally:
        close_window(window)


@pytest.mark.parametrize("value", ["", "   ", "x" * 81])
def test_invalid_empty_or_overlong_name_is_rejected(monkeypatch, value: str) -> None:
    window = make_window()
    warnings = []
    try:
        monkeypatch.setattr("hotspot_editor.QMessageBox.warning", lambda *_args: warnings.append(True))
        assert not window.rename_video(0, value)
        assert window.videos[0].name == "Video 1"
        assert warnings
    finally:
        close_window(window)


@pytest.mark.parametrize("value", ["Video 2", " video 2 ", "VIDEO 2"])
def test_duplicate_name_is_rejected_case_insensitively(monkeypatch, value: str) -> None:
    window = make_window()
    try:
        monkeypatch.setattr("hotspot_editor.QMessageBox.warning", lambda *_args: None)
        assert not window.rename_video(0, value)
        assert window.videos[0].name == "Video 1"
    finally:
        close_window(window)


def test_cancel_and_identical_name_do_not_change_or_create_history(monkeypatch) -> None:
    window = make_window()
    events = []
    try:
        monkeypatch.setattr(window, "push_history", events.append)
        monkeypatch.setattr("hotspot_editor.QInputDialog.exec", lambda _dialog: QDialog.DialogCode.Rejected)
        assert not window.prompt_rename_video(0)
        assert not window.rename_video(0, "Video 1")
        assert window.videos[0].name == "Video 1"
        assert events == []
    finally:
        close_window(window)


def test_rename_dialog_selects_current_name_and_limits_input_to_80(monkeypatch) -> None:
    window = make_window()
    observed = {}
    try:
        def reject_after_inspection(dialog):
            line_edit = dialog.findChild(QLineEdit)
            observed["text"] = dialog.textValue()
            observed["max_length"] = line_edit.maxLength()
            observed["selected"] = line_edit.selectedText()
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr("hotspot_editor.QInputDialog.exec", reject_after_inspection)
        assert not window.prompt_rename_video(0)
        assert observed == {"text": "Video 1", "max_length": 80, "selected": "Video 1"}
    finally:
        close_window(window)


def test_rename_refreshes_thumbnail_tooltip_and_active_window_title(monkeypatch) -> None:
    window = make_window(monkeypatch)
    try:
        assert window.rename_video(0, "Breakfast")
        button = video_button(window, "Breakfast")
        assert "Breakfast" in button.toolTip()
        assert "Breakfast" in window.windowTitle()
    finally:
        close_window(window)


def test_valid_rename_pushes_exactly_one_history_operation(monkeypatch) -> None:
    window = make_window()
    events = []
    try:
        monkeypatch.setattr(window, "push_history", events.append)
        assert window.rename_video(0, "Breakfast")
        assert events == ["video_renamed"]
    finally:
        close_window(window)


def test_undo_and_redo_restore_video_name(monkeypatch) -> None:
    window = make_window(monkeypatch)
    try:
        window.history = History()
        window.history.push(window.snapshot())
        assert window.rename_video(0, "Breakfast")
        window.undo()
        assert window.videos[0].name == "Video 1"
        window.redo()
        assert window.videos[0].name == "Breakfast"
    finally:
        close_window(window)


def test_name_persists_through_project_serialization(monkeypatch) -> None:
    window = make_window()
    try:
        assert window.rename_video(0, "Breakfast")
        payload = json.loads(json.dumps(window.snapshot()))
        loaded = videos_from_project_payload(payload)
        assert loaded[0].name == "Breakfast"
        assert loaded[0].video_id == "video-1"
    finally:
        close_window(window)


def test_name_persists_through_actual_save_and_load(monkeypatch, tmp_path: Path) -> None:
    window = make_window()
    loaded_window = None
    try:
        assert window.rename_video(0, "Breakfast")
        project_path = tmp_path / "renamed.anna.json"
        window.project_path = project_path
        window.save_json()
        loaded_window = EditorWindow(auto_show=False)
        loaded_window.load_json(project_path)
        assert loaded_window.videos[0].name == "Breakfast"
        assert loaded_window.videos[0].source == "first.mp4"
    finally:
        if loaded_window is not None:
            loaded_window.close()
        close_window(window)


def test_rename_is_blocked_in_user_mode_and_active_research(monkeypatch) -> None:
    window = make_window()
    try:
        window.preview_mode = True
        assert not window.rename_video(0, "Blocked in user mode")
        window.preview_mode = False
        monkeypatch.setattr(window.research, "active_session", SimpleNamespace(status="active"))
        assert window.research.is_active
        assert not window.rename_video(0, "Blocked in research")
        assert not window.prompt_rename_video(0)
        assert window.videos[0].name == "Video 1"
    finally:
        window.research.active_session = None
        close_window(window)


def test_context_menu_disables_rename_during_active_research(monkeypatch) -> None:
    window = make_window(monkeypatch)
    observed = {}
    try:
        window.research.active_session = SimpleNamespace(status="active")

        menu, rename_action, _replace_action, _delete_action = window.make_video_context_menu()
        observed["text"] = rename_action.text()
        observed["enabled"] = rename_action.isEnabled()
        assert observed == {"text": "Rename video…", "enabled": False}
        menu.deleteLater()
    finally:
        window.research.active_session = None
        close_window(window)


def test_legacy_project_without_name_still_loads() -> None:
    loaded = videos_from_project_payload({"videos": [{"video_id": "video-7", "source": "old.mp4", "pauses": []}]})
    assert loaded[0].video_id == "video-7"
    assert loaded[0].name


def test_custom_names_with_numbers_do_not_affect_next_video_number() -> None:
    app()
    window = EditorWindow(auto_show=False)
    try:
        window.videos = [
            VideoEntry("video-1", "Actividad 50", "a.mp4"),
            VideoEntry("video-3", "Unidad 200", "b.mp4"),
        ]
        assert window.next_video_number() == 2
        number = window.next_video_number()
        window.videos.append(VideoEntry(f"video-{number}", f"Video {number}", "c.mp4"))
        assert len({video.video_id for video in window.videos}) == len(window.videos)
        assert window.next_video_number() == 4
    finally:
        window.close()
