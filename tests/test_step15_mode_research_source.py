from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'hotspot_editor.py').read_text(encoding='utf-8')


def test_research_toolbar_logic_is_present_without_legacy_menu_assumptions():
    assert 'self.research_label = QLabel(tr("label.research"))' in SOURCE
    assert 'self.research_quick_btn = QPushButton("OFF")' in SOURCE
    assert 'self.research_quick_btn.setText("ON" if active else "OFF")' in SOURCE
    assert 'self.research_quick_btn.setEnabled(not user_mode)' in SOURCE


def test_mode_icons_are_generated_without_external_assets():
    assert 'def mode_icon(name: str) -> QIcon:' in SOURCE
    assert 'mode_icon("user")' in SOURCE
    assert 'mode_icon("professional")' in SOURCE
    assert not (ROOT / 'assets' / 'icons' / 'mode_user_play_bw.png').exists()
    assert not (ROOT / 'assets' / 'icons' / 'gear_fine_36.png').exists()


def test_no_obsolete_research_header_buttons_remain():
    assert 'self.turn_btn = QPushButton' not in SOURCE
    assert 'self.adequate_btn = QPushButton' not in SOURCE
    assert 'self.review_btn = QPushButton' not in SOURCE
    assert 'INVESTIGACIÓN ACTIVA' not in SOURCE


def test_keyboard_annotation_pattern_is_present():
    assert '("Space", "turn")' in SOURCE
    assert '("+", "adequate")' in SOURCE
    assert '("-", "review")' in SOURCE
    assert 'handle_research_shortcut' in SOURCE
