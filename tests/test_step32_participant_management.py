from __future__ import annotations

import sys
import json
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot_editor  # noqa: E402
from hotspot_editor import EditorWindow  # noqa: E402
from users_manager import UsersManager  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication(["test-step32-participant-management"])


class FakeResearch:
    def __init__(self) -> None:
        self.active_session = None
        self.started: list[dict[str, object]] = []
        self.finished: list[str] = []
        self.events: list[dict[str, object]] = []

    @property
    def is_active(self) -> bool:
        return self.active_session is not None and self.active_session.status == "active"

    def start_session(self, **kwargs):
        self.started.append(kwargs)
        self.active_session = SimpleNamespace(
            status="active",
            is_anonymous=bool(kwargs.get("is_anonymous")),
        )
        return self.active_session

    def finish_session(self, *, status: str = "completed", **_payload) -> None:
        self.finished.append(status)
        if self.active_session is not None:
            self.active_session.status = status

    def record_event(self, event_type: str, **payload):
        self.events.append({"event_type": event_type, **payload})


def test_participant_manager_uses_visible_names_stable_codes_archive_and_legacy_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "users.csv"
    manager = UsersManager(csv_path)

    first_id = manager.create_user(" Ana ")

    assert first_id == "1"
    assert manager.users[first_id]["name"] == "Ana"
    assert manager.participant_code(first_id) == "P0001"
    assert manager.participant_display_name(first_id) == "Ana — P0001"
    assert manager.users[first_id]["active"] == "1"

    try:
        manager.create_user("   ")
    except ValueError:
        pass
    else:
        raise AssertionError("empty participant name must be rejected")

    try:
        manager.create_user(" ana ")
    except ValueError:
        pass
    else:
        raise AssertionError("equivalent duplicate participant name must be rejected")

    manager.users[first_id]["notes"] = "legacy"
    manager.users[first_id]["group"] = "legacy-group"
    manager.rename_user(first_id, "Ana Maria")

    assert manager.users[first_id]["id"] == first_id
    assert manager.users[first_id]["name"] == "Ana Maria"
    assert manager.users[first_id]["notes"] == "legacy"
    assert manager.users[first_id]["group"] == "legacy-group"
    assert manager.participant_code(first_id) == "P0001"

    manager.select_user(first_id)
    manager.clear_current_user()

    assert manager.current_user_id is None
    assert "Sin participante" not in csv_path.read_text(encoding="utf-8")

    reloaded = UsersManager(csv_path)

    assert reloaded.users[first_id]["name"] == "Ana Maria"
    assert reloaded.users[first_id]["notes"] == "legacy"
    assert reloaded.users[first_id]["group"] == "legacy-group"
    assert reloaded.is_active_user(first_id)

    second_id = reloaded.create_user("Berta")
    assert second_id == "2"
    assert reloaded.participant_code(second_id) == "P0002"

    reloaded.delete_user(second_id)
    third_id = reloaded.create_user("Clara")
    assert third_id == "3"

    sessions_root = tmp_path / "sessions"
    session_dir = sessions_root / "session-1"
    session_dir.mkdir(parents=True)
    (session_dir / "session.json").write_text(json.dumps({"user_id": first_id}), encoding="utf-8")

    assert reloaded.has_recorded_sessions(first_id, sessions_root)
    assert reloaded.remove_or_archive_user(first_id, sessions_root) == "archived"
    assert not reloaded.is_active_user(first_id)
    assert first_id not in reloaded.sorted_participant_ids()
    assert first_id in reloaded.sorted_participant_ids(show_archived=True)
    assert reloaded.participant_display_name(first_id).endswith("(archivado)")

    reloaded.reactivate_user(first_id)
    assert reloaded.is_active_user(first_id)
    assert reloaded.participant_code(first_id) == "P0001"

    legacy_csv = tmp_path / "legacy_users.csv"
    legacy_csv.write_text(
        "id,name,notes,group,date_created,last_session_date,last_session_end,total_sessions\n"
        "1,Zeta,,,2026-01-01,2026-07-01,,1\n"
        "2,Alfa,,,2026-01-01,,,0\n",
        encoding="utf-8",
    )
    legacy = UsersManager(legacy_csv)
    assert legacy.is_active_user("1")
    assert legacy.is_active_user("2")

    legacy.users["2"]["last_session_date"] = "2026-07-02"
    legacy.users["1"]["last_session_date"] = "2026-07-01"
    legacy.users["3"] = {"id": "3", "name": "Beta", "last_session_date": "", "active": "1"}
    assert legacy.sorted_participant_ids() == ["2", "1", "3"]


def test_participant_is_active_only_inside_research_session(monkeypatch, tmp_path: Path) -> None:
    app = _app()
    window = EditorWindow()
    try:
        manager = UsersManager(tmp_path / "users.csv")
        participant_id = manager.create_user("PX-01")
        window.users_manager = manager
        window.research = FakeResearch()

        window.update_research_controls()

        assert window.participant_selector.currentText() == "No participant"

        manager.select_user(participant_id)
        window.update_research_controls()

        assert manager.current_user_id == participant_id
        assert window.participant_selector.currentText() == "PX-01"

        current_index = window.current_video_index
        window.select_video(current_index)
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.preview_btn.setChecked(False)
        window.toggle_preview_mode()

        assert manager.current_user_id == participant_id
        assert window.participant_selector.currentText() == "PX-01"

        payload = window.snapshot()

        assert "users" not in payload
        assert "current_user_id" not in payload

        window.select_video(current_index)
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        window.preview_btn.setChecked(False)
        window.toggle_preview_mode()

        assert manager.current_user_id == participant_id

        window.toggle_research()

        assert window.research.started[-1]["user_id"] == participant_id
        assert window.research.started[-1]["user_name"] == "PX-01"
        assert window.research.started[-1]["is_anonymous"] is False
        assert window.participant_selector.currentText() == "Research: PX-01"

        window.toggle_research()

        assert manager.current_user_id == participant_id
        assert window.participant_selector.currentText() == "PX-01"

        manager.clear_current_user()
        window.update_research_controls()
        monkeypatch.setattr(window, "ensure_research_participant", lambda: (True, "", "", "test", True))

        window.toggle_research()

        assert window.research.started[-1]["user_id"] == ""
        assert window.research.started[-1]["user_name"] == ""
        assert window.research.started[-1]["is_anonymous"] is True
        assert manager.current_user_id is None
        assert window.participant_selector.currentText() == "Research: anonymous session"

        window.toggle_research()

        assert manager.current_user_id is None
        assert window.participant_selector.currentText() == "No participant"

        monkeypatch.setattr(window, "ensure_research_participant", lambda: (False, "", "", "", False))

        window.toggle_research()

        assert len(window.research.started) == 2
    finally:
        window.close()
        app.processEvents()


def test_participant_management_is_blocked_while_research_is_active(monkeypatch, tmp_path: Path) -> None:
    app = _app()
    window = EditorWindow()
    messages: list[str] = []
    try:
        window.users_manager = UsersManager(tmp_path / "users.csv")
        window.research = FakeResearch()
        window.research.active_session = SimpleNamespace(status="active", is_anonymous=False)
        monkeypatch.setattr(
            hotspot_editor.QMessageBox,
            "information",
            lambda _parent, _title, text: messages.append(text),
        )

        result = window.manage_participants()

        assert result is False
        assert messages == ["Finish the research session before changing the participant."]
    finally:
        window.close()
        app.processEvents()
