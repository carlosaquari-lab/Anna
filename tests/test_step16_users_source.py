from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_participant_research_policy_is_present():
    source = (ROOT / "hotspot_editor.py").read_text(encoding="utf-8")
    assert 'tr("message.research_participant")' in source
    assert 'tr("button.select_participant")' in source
    assert 'tr("button.new_participant")' in source
    assert 'tr("button.start_anonymous")' in source
    assert 'tr("button.cancel")' in source


def test_user_is_written_into_research_session():
    model = (ROOT / "research_models.py").read_text(encoding="utf-8")
    session = (ROOT / "research_session.py").read_text(encoding="utf-8")
    assert 'user_id: str = ""' in model
    assert 'user_name: str = ""' in model
    assert '"user_id": session.user_id' in session
    assert '"user_name": session.user_name' in session


def test_research_menu_contains_participant_management_summary_and_csv_export():
    source = (ROOT / "hotspot_editor.py").read_text(encoding="utf-8")
    assert 'tr("action.manage_participants")' in source
    assert 'self.select_user_action.triggered.connect(self.manage_participants)' in source
    assert 'tr("action.session_summary")' in source
    assert 'tr("action.export_csv")' in source
    assert 'self.export_csv_action.triggered.connect(self.export_research_csv)' in source
