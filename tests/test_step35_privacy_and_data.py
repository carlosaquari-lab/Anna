from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from research_export import export_sessions_csv, export_sessions_csv_anonymized
from research_session import ResearchSessionManager
from users_manager import UsersManager


ABSOLUTE_MARKERS = ("C:\\", "\\Users\\", "\\OneDrive\\", "\\Desktop\\", "\\Documents\\")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def assert_no_absolute_paths(text: str) -> None:
    assert not any(marker in text for marker in ABSOLUTE_MARKERS)


def test_participants_are_separate_from_project_and_legacy_users_csv_is_compatible(tmp_path: Path):
    project_payload = {
        "schema_version": 2,
        "project_id": "demo",
        "videos": [{"video_id": "video-1", "name": "Vídeo 1", "source": "media/video.mp4"}],
        "pause_events": [],
    }

    assert "users" not in project_payload
    assert "current_user_id" not in project_payload
    assert "participant" not in json.dumps(project_payload, ensure_ascii=False).casefold()

    csv_path = tmp_path / "lola_data" / "users.csv"
    csv_path.parent.mkdir()
    csv_path.write_text(
        "id,name,notes,group,date_created,last_session_date,last_session_end,total_sessions\n"
        "1,Ana,legacy note,legacy group,2026-01-01,,,0\n",
        encoding="utf-8",
    )
    manager = UsersManager(csv_path)

    assert manager.users["1"]["name"] == "Ana"
    assert manager.users["1"]["notes"] == "legacy note"
    assert manager.users["1"]["group"] == "legacy group"
    assert manager.is_active_user("1")
    assert manager.current_user_id is None


def test_sessions_are_separate_utf8_safe_and_do_not_store_absolute_paths(tmp_path: Path):
    manager = ResearchSessionManager(tmp_path / "results" / "sessions")
    session_a = manager.start_session(
        project_id="demo",
        project_name="Proyecto",
        video_id="video-1",
        video_name="Vídeo 1",
        user_id="1",
        user_name="Ana",
    )
    manager.record_event(
        "video_started",
        video_id="video-1",
        video_name="Vídeo 1",
        video_position_ms=0,
        source_path="C:\\Users\\Ana\\Videos\\personal.mp4",
        nested={"safe": "ok", "path": "C:\\Users\\Ana\\Desktop\\file.wav"},
    )
    manager.finish_session(video_id="video-1", video_name="Vídeo 1", video_position_ms=0)

    manager_b = ResearchSessionManager(tmp_path / "results" / "sessions")
    session_b = manager_b.start_session(
        project_id="demo",
        project_name="Proyecto",
        video_id="video-2",
        video_name="Vídeo 2",
        user_id="2",
        user_name="Berta",
    )
    manager_b.record_event("video_started", video_id="video-2", video_name="Vídeo 2", video_position_ms=0)
    manager_b.finish_session(video_id="video-2", video_name="Vídeo 2", video_position_ms=0)

    assert session_a.session_id != session_b.session_id
    assert "Ana" not in session_a.session_id
    assert re.match(r"^\d{8}_\d{6}_\d{6}_[0-9a-f]{8}$", session_a.session_id)

    session_a_dir = tmp_path / "results" / "sessions" / session_a.session_id
    events_text = (session_a_dir / "events.jsonl").read_text(encoding="utf-8")
    session_text = (session_a_dir / "session.json").read_text(encoding="utf-8")
    summary_text = (session_a_dir / "summary.json").read_text(encoding="utf-8")

    assert (session_a_dir / "session.json").exists()
    assert (session_a_dir / "events.jsonl").exists()
    assert (session_a_dir / "summary.json").exists()
    assert_no_absolute_paths(events_text)
    assert_no_absolute_paths(session_text)
    assert_no_absolute_paths(summary_text)
    assert "Berta" not in session_text
    assert "Berta" not in summary_text
    assert "Vídeo 1" in session_text


def test_exports_can_be_complete_or_anonymized_without_notes_group_or_absolute_paths(tmp_path: Path):
    sessions_root = tmp_path / "sessions"
    manager = ResearchSessionManager(sessions_root)
    session = manager.start_session(
        project_id="demo",
        project_name="Proyecto",
        video_id="video-1",
        video_name="Vídeo 1",
        user_id="1",
        user_name="Ana",
    )
    manager.record_event(
        "video_started",
        video_id="video-1",
        video_name="Vídeo 1",
        video_position_ms=0,
        participant_name="Ana",
        notes="clinical note",
        group="legacy group",
        absolute_path="C:\\Users\\Ana\\Videos\\personal.mp4",
    )
    manager.finish_session(video_id="video-1", video_name="Vídeo 1", video_position_ms=0)

    legacy_dir = sessions_root / "legacy"
    legacy_dir.mkdir()
    (legacy_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "session_id": "legacy",
                "event_type": "video_started",
                "elapsed_session_ms": 0,
                "participant_id": "9",
                "participant_name": "Legacy",
                "notes": "old",
                "group": "old",
                "path": "C:\\Users\\Legacy\\file.mp4",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (legacy_dir / "summary.json").write_text(
        json.dumps({"session_id": "legacy", "participant_id": "9", "participant_name": "Legacy"}, ensure_ascii=False),
        encoding="utf-8",
    )

    events_csv, summaries_csv = export_sessions_csv(sessions_root, tmp_path / "export")
    anon_events_csv, anon_summaries_csv = export_sessions_csv_anonymized(sessions_root, tmp_path / "export_anon")

    complete_events = read_csv(events_csv)
    anon_events = read_csv(anon_events_csv)
    anon_summaries = read_csv(anon_summaries_csv)

    assert any(row["session_id"] == session.session_id and row["participant_name"] == "Ana" for row in complete_events)
    assert all(row.get("participant_name", "") == "" for row in anon_events)
    assert all(row.get("user_name", "") == "" for row in anon_events)
    assert any(row.get("participant_id") == "1" for row in anon_events)
    assert any(row.get("participant_id") == "9" for row in anon_summaries)
    assert "notes" not in read_csv(anon_events_csv)[0]
    assert "group" not in read_csv(anon_events_csv)[0]
    assert_no_absolute_paths(events_csv.read_text(encoding="utf-8"))
    assert_no_absolute_paths(summaries_csv.read_text(encoding="utf-8"))
    assert_no_absolute_paths(anon_events_csv.read_text(encoding="utf-8"))
    assert_no_absolute_paths(anon_summaries_csv.read_text(encoding="utf-8"))


def test_technical_logs_are_separate_and_summary_copy_preserves_scroll_without_layout_changes():
    root = Path(__file__).resolve().parents[1]
    editor_source = (root / "hotspot_editor.py").read_text(encoding="utf-8")
    privacy_doc = (root / "DATA_PRIVACY.md").read_text(encoding="utf-8")

    assert "LOG_PATH = RESULTS_DIR / \"editor_hotspots_log.jsonl\"" in editor_source
    assert "sessions/" in privacy_doc
    assert "editor_hotspots_log.jsonl" in privacy_doc
    assert "verticalScrollBar().value()" in editor_source
    assert "horizontalScrollBar().value()" in editor_source
    assert "setFocusPolicy(Qt.FocusPolicy.NoFocus)" in editor_source
    assert "setText(\"Copiado" not in editor_source
    assert "Resumen copiado al portapapeles" not in editor_source
    assert "statusBar().showMessage" not in editor_source
    assert "QApplication.clipboard().setText(text.toPlainText())" in editor_source


def test_data_privacy_document_is_present_and_excludes_clinical_data():
    root = Path(__file__).resolve().parents[1]
    text = (root / "DATA_PRIVACY.md").read_text(encoding="utf-8")

    assert "Proyecto" in text
    assert "Participantes" in text
    assert "Sesiones" in text
    assert "Exportaciones" in text
    assert "anonimizada" in text
    assert "diagnóstico" in text
    assert "dirección" in text
    assert_no_absolute_paths(text)
