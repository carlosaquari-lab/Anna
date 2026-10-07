from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "hotspot_editor.py"
TEXT = SOURCE.read_text(encoding="utf-8")


def test_hotspot_and_support_use_same_audio_helper() -> None:
    assert "def play_interaction_audio" in TEXT
    assert "played_audio = self.play_interaction_audio(\n                self.support_asset_path" in TEXT
    assert "played_audio = self.play_interaction_audio(audio_path)" in TEXT


def test_user_seek_clears_active_interaction_and_support_panel() -> None:
    assert "if self.preview_mode:\n            # Un desplazamiento manual abandona la interacción activa" in TEXT
    assert "self.clear_active_interaction()" in TEXT
    assert "self.refresh_support_panel(value)" in TEXT


def test_professional_buttons_keep_fixed_geometry_when_pressed() -> None:
    assert "#professionalAnnotationButton:pressed" in TEXT
    assert "border:1px solid #667789" in TEXT
    assert "border:2px solid #2f6fa7" not in TEXT


def test_summary_actions_are_real_buttons() -> None:
    assert 'button.setObjectName("summaryActionButton")' in TEXT
    assert "#summaryActionButton:pressed" in TEXT
