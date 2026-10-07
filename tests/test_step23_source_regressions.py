from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "hotspot_editor.py"
TEXT = SOURCE.read_text(encoding="utf-8")


def test_support_text_limit_is_40():
    assert "class SupportConfigDialog(QDialog):\n    TEXT_MAX_CHARS = 40" in TEXT


def test_hotspot_audio_controls_match_support_audio_controls():
    for label in (
        'QPushButton(tr("button.select_audio"))',
        'QPushButton(tr("button.record"))',
        'QPushButton(tr("button.stop"))',
        'QPushButton(tr("button.listen"))',
        'QPushButton(tr("button.delete_audio"))',
    ):
        assert label in TEXT
    assert "self.choose_audio_btn.clicked.connect(self.choose_audio)" in TEXT


def test_professional_buttons_do_not_show_status_bar_message():
    block = TEXT.split("def handle_professional_annotation", 1)[1].split("def undo_last_professional_mark", 1)[0]
    assert "statusBar().showMessage" not in block
