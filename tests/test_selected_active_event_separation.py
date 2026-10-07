from pathlib import Path


def test_editor_declares_independent_selected_and_active_event_ids():
    source = (Path(__file__).parents[1] / "hotspot_editor.py").read_text(encoding="utf-8")
    assert "self.selected_event_id: str | None = None" in source
    assert "self.active_event_id: str | None = None" in source
    assert "return self.active_event() if self.preview_mode else self.selected_event()" in source


def test_runtime_activation_does_not_select_event_for_editing():
    source = (Path(__file__).parents[1] / "hotspot_editor.py").read_text(encoding="utf-8")
    runtime_block = source.split("def pause_at_temporal_event", 1)[1].split("def on_position_changed", 1)[0]
    assert "self.active_event_id = pause.pause_id" in runtime_block
    assert "self.selected_event_id = None" in runtime_block
