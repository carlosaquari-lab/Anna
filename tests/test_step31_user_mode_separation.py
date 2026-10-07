from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QCheckBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import EditorWindow  # noqa: E402
from hotspot_model import Hotspot, PausePoint, SupportItem, VideoEntry  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step31-user-mode-separation"])


def _install_player_spies(monkeypatch, window: EditorWindow) -> tuple[dict[str, int], list[bool], list[bool], list[int]]:
    position = {"value": 700}
    paused: list[bool] = []
    played: list[bool] = []
    set_positions: list[int] = []

    monkeypatch.setattr(window.player, "pause", lambda: paused.append(True))
    monkeypatch.setattr(window.player, "play", lambda: played.append(True))
    monkeypatch.setattr(window.player, "position", lambda: position["value"])
    monkeypatch.setattr(window.player, "setSource", lambda _url: None)

    def set_position(value: int) -> None:
        position["value"] = int(value)
        set_positions.append(int(value))

    monkeypatch.setattr(window.player, "setPosition", set_position)
    return position, paused, played, set_positions


def _populate_project(window: EditorWindow) -> PausePoint:
    pause = PausePoint(
        "pause-1",
        1000,
        [Hotspot("hotspot-1", message_text="Hola")],
        [SupportItem("support_1", "Apoyo 1", "Agua", visible=True, position=0)],
    )
    window.videos = [
        VideoEntry("video-1", "Vídeo 1", "media/uno.mp4", [pause]),
        VideoEntry("video-2", "Vídeo 2", "media/dos.mp4", []),
    ]
    window.current_video_index = 0
    window.pauses = window.videos[0].pauses
    window.timeline.setRange(0, 5000)
    window.timeline.set_pauses(window.pauses, None)
    return pause


def test_user_mode_blocks_project_editing_but_keeps_interaction_and_navigation_rules(monkeypatch) -> None:
    app = _app()
    window = EditorWindow()
    position, paused, played, set_positions = _install_player_spies(monkeypatch, window)
    try:
        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: True)
        monkeypatch.setattr(window, "request_video_thumbnail", lambda _video: None)
        monkeypatch.setattr(window.scene, "removeItem", lambda _item: None)
        pause = _populate_project(window)

        window.selected_event_id = pause.pause_id
        window.current_hotspot_id = "hotspot-1"
        window.set_mode("rectangle")
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()

        assert window.preview_mode is True
        assert position["value"] == 0
        assert set_positions[-1] == 0
        assert played == []
        assert paused
        assert window.mode == "select"
        assert window.active_event_id is None
        assert window.selected_event_id == pause.pause_id
        assert all(not button.isVisible() for button in window.tool_buttons.values())
        assert all(not button.isEnabled() for button in window.tool_buttons.values())
        assert all(not action.isEnabled() for action in window.project_edit_actions)
        assert window.mode_edit_action.isEnabled()
        assert not window.mode_user_action.isEnabled()
        assert window.add_video_btn is None or not window.add_video_btn.isVisible()
        assert window.file_menu.menuAction().isVisible()
        assert window.research_menu.menuAction().isVisible()
        assert window.file_menu.menuAction().isEnabled()
        assert window.research_menu.menuAction().isEnabled()
        assert all(not action.isEnabled() for action in window.research_actions)
        assert window.exit_action.isEnabled()
        assert window.mode_menu.menuAction().isVisible()
        assert window.language_menu.menuAction().isVisible()
        assert window.help_menu.menuAction().isVisible()
        assert window.mode_menu.menuAction().isEnabled()
        assert window.language_menu.menuAction().isEnabled()
        assert window.help_menu.menuAction().isEnabled()
        menu_titles = [action.text() for action in window.menuBar().actions()]
        assert len(menu_titles) == len(set(menu_titles))

        class ExplodingMenu:
            def __init__(self, *_args, **_kwargs) -> None:
                raise AssertionError("No debe abrir menú contextual en modo usuario")

        monkeypatch.setattr(hotspot_editor, "QMenu", ExplodingMenu)
        window.show_video_context_menu("video-1", None)

        opened_dialogs: list[str] = []
        monkeypatch.setattr(hotspot_editor.HotspotContentDialog, "exec", lambda _self: opened_dialogs.append("hotspot") or 0)
        monkeypatch.setattr(hotspot_editor.SupportConfigDialog, "exec", lambda _self: opened_dialogs.append("support") or 0)

        window.edit_selected_hotspot("hotspot-1")
        window.delete_selected_hotspot()
        window.configure_support(pause.supports[0])

        assert opened_dialogs == []
        assert len(pause.hotspots) == 1
        assert pause.supports[0].text == "Agua"

        window.pause_at_temporal_event(pause)

        assert window.active_event_id == "pause-1"
        assert set(window.items) == {"hotspot-1"}
        assert all(item.preview_mode for item in window.items.values())
        assert window.support_buttons_layout.count() == 1
        app.processEvents()
        assert not any(checkbox.isVisible() for checkbox in window.support_panel.findChildren(QCheckBox))

        window.activate_hotspot("hotspot-1")
        window.activate_support(pause.supports[0])

        assert window.active_event_id == "pause-1"
        assert set(window.items) == {"hotspot-1"}
        assert window.support_buttons_layout.count() == 1
        assert window.continue_btn.isEnabled()

        window.navigation_visibility.setChecked(True)
        window.select_or_add_video(1)

        assert window.current_video().video_id == "video-2"
        assert position["value"] == 0

        window.select_video(0)
        window.pause_at_temporal_event(pause)
        window.navigation_visibility.setChecked(False)
        before_video_id = window.current_video().video_id
        before_position = position["value"]

        window.select_or_add_video(1)
        window.seek_from_click(2200)
        window.seek_during_drag(2300)

        assert window.current_video().video_id == before_video_id
        assert position["value"] == before_position

        window.continue_from_pause()

        assert window.playback_controller.pending_continue_position_ms is not None

        window.enter_edit_mode()
        app.processEvents()

        assert window.preview_mode is False
        assert all(not button.isHidden() for button in window.tool_buttons.values())
        assert all(button.isEnabled() for button in window.tool_buttons.values())
        assert all(action.isEnabled() for action in window.project_edit_actions)
        assert window.mode_user_action.isEnabled()
        assert not window.mode_edit_action.isEnabled()
        assert window.add_video_btn is None or not window.add_video_btn.isHidden()
        assert window.file_menu.menuAction().isVisible()
        assert window.research_menu.menuAction().isVisible()
        assert window.file_menu.menuAction().isEnabled()
        assert window.research_menu.menuAction().isEnabled()
        assert all(action.isEnabled() for action in window.research_actions)
        assert window.exit_action.isEnabled()
        assert window.mode_menu.menuAction().isVisible()
        assert window.language_menu.menuAction().isVisible()
        assert window.help_menu.menuAction().isVisible()
        menu_titles = [action.text() for action in window.menuBar().actions()]
        assert len(menu_titles) == len(set(menu_titles))

        window.select_event(pause)
        window.refresh_support_panel()

        assert window.support_panel.findChildren(QCheckBox)
    finally:
        window.close()
        app.processEvents()


def test_initial_screen_keeps_original_add_video_entrypoint(monkeypatch) -> None:
    app = _app()
    window = EditorWindow()
    try:
        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: False)

        window.update_project_title()
        window.refresh_video_nav()
        window.show()
        app.processEvents()

        assert window.top_label.text() == "ANNA — Interactive Video Activities for AAC"
        assert window.windowTitle() == "ANNA — Interactive Video Activities for AAC"
        add_buttons = [
            button
            for button in window.video_nav.findChildren(hotspot_editor.QToolButton)
            if button.objectName() == "addVideoButton"
        ]
        assert add_buttons
        assert any(button.text() == "+" and button.isVisible() for button in add_buttons)

        monkeypatch.setattr(window, "video_has_valid_source", lambda _video: True)
        window.current_video().name = "Vídeo 1"

        window.update_project_title()

        assert window.top_label.text() == "ANNA — Interactive Video Activities for AAC"
    finally:
        window.close()
        app.processEvents()
