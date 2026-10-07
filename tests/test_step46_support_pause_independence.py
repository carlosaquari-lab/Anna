from PySide6.QtWidgets import QApplication, QDialog

import hotspot_editor
from hotspot_editor import EditorWindow
from hotspot_model import Hotspot, PausePoint, SupportItem, videos_from_project_payload


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_window(monkeypatch, position: int = 4_000) -> EditorWindow:
    app()
    window = EditorWindow(auto_show=False)
    window.duration_ms = 10_000
    window.timeline.setRange(0, 10_000)
    monkeypatch.setattr(window.player, "position", lambda: position)
    return window


def accept_support_dialog(monkeypatch, result: SupportItem) -> None:
    monkeypatch.setattr(hotspot_editor.SupportConfigDialog, "exec", lambda _dialog: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(hotspot_editor.SupportConfigDialog, "result_support", lambda _dialog: result)


def test_configuring_support_without_pause_creates_selected_support_only_pause(monkeypatch) -> None:
    window = make_window(monkeypatch)
    configured = SupportItem("support_1", text="Necesito ayuda", visible=True, position=0)
    accept_support_dialog(monkeypatch, configured)
    try:
        window.configure_support(SupportItem("support_1", position=0))
        assert len(window.pauses) == 1
        pause = window.pauses[0]
        assert pause.time_ms == 4_000
        assert pause.hotspots == []
        assert pause.supports[0].text == "Necesito ayuda"
        assert window.selected_event_id == pause.pause_id
        assert window.timeline.pause_times == [4_000]
    finally:
        window.close()


def test_configuring_support_reuses_nearby_pause_with_tolerance(monkeypatch) -> None:
    window = make_window(monkeypatch, 4_050)
    existing = PausePoint("existing", 4_000, [])
    window.pauses = [existing]
    window.current_video().pauses = window.pauses
    configured = SupportItem("support_2", text="Más", visible=True, position=1)
    accept_support_dialog(monkeypatch, configured)
    try:
        window.configure_support(SupportItem("support_2", position=1))
        assert window.pauses == [existing]
        assert existing.supports[1].text == "Más"
    finally:
        window.close()


def test_cancel_new_support_dialog_removes_provisional_pause(monkeypatch) -> None:
    window = make_window(monkeypatch)
    monkeypatch.setattr(hotspot_editor.SupportConfigDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)
    try:
        window.configure_support(SupportItem("support_1", position=0))
        assert window.pauses == []
        assert window.current_video().pauses == []
        assert window.timeline.pause_times == []
        assert window.selected_event_id is None
    finally:
        window.close()


def test_cancel_support_dialog_preserves_existing_pause(monkeypatch) -> None:
    window = make_window(monkeypatch)
    existing = PausePoint("existing", 4_000, [])
    window.pauses = [existing]
    window.current_video().pauses = window.pauses
    monkeypatch.setattr(hotspot_editor.SupportConfigDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)
    try:
        window.configure_support(existing.supports[0])
        assert window.pauses == [existing]
    finally:
        window.close()


def test_support_only_pause_round_trips_and_is_presented_in_user_mode(monkeypatch) -> None:
    window = make_window(monkeypatch)
    support = SupportItem("support_1", text="Agua", visible=True, position=0)
    pause = PausePoint("support-only", 4_000, [], [support])
    window.pauses = [pause]
    window.current_video().pauses = window.pauses
    try:
        payload = window.snapshot()
        restored = videos_from_project_payload(payload)[0].pauses[0]
        assert restored.hotspots == []
        assert restored.supports[0].text == "Agua"

        window.preview_mode = True
        window.pause_at_temporal_event(pause)
        assert window.active_event_id == "support-only"
        assert window.items == {}
        assert window.support_buttons_layout.count() == 1
        assert window.research_hotspots_for_pause(pause) == []
        assert len(window.research_supports_for_pause(pause)) == 1
    finally:
        window.close()


def test_last_hotspot_removal_keeps_pause_with_supports_and_removes_empty_pause(monkeypatch) -> None:
    window = make_window(monkeypatch)
    kept_hotspot = Hotspot("kept-hotspot")
    configured = SupportItem("support_1", text="Conservar", position=0)
    kept = PausePoint("kept", 4_000, [kept_hotspot], [configured])
    empty_hotspot = Hotspot("empty-hotspot")
    empty = PausePoint("empty", 6_000, [empty_hotspot])
    window.pauses = [kept, empty]
    window.current_video().pauses = window.pauses
    try:
        assert not window.cancel_provisional_hotspot(kept, kept_hotspot)
        assert kept in window.pauses
        assert kept.hotspots == []
        assert kept.supports[0].text == "Conservar"

        assert window.cancel_provisional_hotspot(empty, empty_hotspot)
        assert empty not in window.pauses
    finally:
        window.close()


def test_delete_last_hotspot_preserves_support_pause(monkeypatch) -> None:
    window = make_window(monkeypatch)
    hotspot = Hotspot("hotspot")
    pause = PausePoint("pause", 4_000, [hotspot], [SupportItem("support_1", text="Conservar", position=0)])
    window.pauses = [pause]
    window.current_video().pauses = window.pauses
    window.current_hotspot_id = hotspot.hotspot_id
    monkeypatch.setattr(window, "selected_hotspot", lambda: hotspot)
    monkeypatch.setattr(window, "current_pause", lambda: pause)
    monkeypatch.setattr(window, "confirm_delete_hotspot", lambda _is_last: True)
    try:
        window.delete_selected_hotspot()
        assert pause in window.pauses
        assert pause.hotspots == []
        assert pause.supports[0].text == "Conservar"
        assert 4_000 in window.timeline.pause_times
    finally:
        window.close()
