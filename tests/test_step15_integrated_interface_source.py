from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "hotspot_editor.py").read_text(encoding="utf-8")


def test_mode_button_uses_generated_icons_and_changes_mode():
    assert 'self.mode_quick_btn.setIcon(mode_icon("user"))' in SOURCE
    assert 'self.mode_quick_btn.setIcon(mode_icon("professional"))' in SOURCE
    assert 'self.preview_btn.setChecked(True)' in SOURCE
    assert 'self.mode_quick_btn.clicked.connect(self.handle_mode_quick_button)' in SOURCE


def test_professional_annotations_keep_toolbar_pattern_without_legacy_literals():
    assert 'self.professional_annotation_bar = QWidget()' in SOURCE
    assert '("turn", tr("annotation.turn"))' in SOURCE
    assert '("adequate", tr("annotation.appropriate"))' in SOURCE
    assert '("review", tr("annotation.review"))' in SOURCE
    assert 'self.professional_annotation_bar.setVisible(user_mode)' in SOURCE
    assert 'button.setEnabled(user_mode and active)' in SOURCE
    assert 'response_mark_status' not in SOURCE


def test_first_empty_video_slot_is_reused_and_numbering_is_available_based():
    assert 'def video_has_valid_source' in SOURCE
    assert 'def select_or_add_video' in SOURCE
    assert 'def next_video_number' in SOURCE
    assert 'self.add_video(replace_index=index)' in SOURCE
    assert 'len(self.videos) == 1 and not self.video_has_valid_source(self.videos[0])' in SOURCE
    assert 'VideoEntry(f"video-{number}", tr("video.automatic_name", number=number)' in SOURCE


def test_research_on_off_remains_accessible_from_professional_mode():
    assert 'self.research_label = QLabel(tr("label.research"))' in SOURCE
    assert 'self.research_quick_btn = QPushButton("OFF")' in SOURCE
    assert 'self.research_quick_btn.setText("ON" if active else "OFF")' in SOURCE
    assert 'self.research_quick_btn.setVisible(not user_mode)' in SOURCE
