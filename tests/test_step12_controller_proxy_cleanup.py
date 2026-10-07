from pathlib import Path


def test_editor_uses_playback_controller_for_runtime_state_without_stale_proxy_storage():
    source = (Path(__file__).parents[1] / "hotspot_editor.py").read_text(
        encoding="utf-8"
    )

    forbidden_storage = (
        "self._seeking =",
        "self._seek_start_ms =",
        "self._pending_continue_position_ms =",
    )
    for legacy_name in forbidden_storage:
        assert legacy_name not in source

    assert "return self.playback_controller.running" in source
    assert "self.playback_controller.running = bool(value)" in source
    assert "return self.playback_controller.seeking" in source
    assert "self.playback_controller.mode" in source
    assert "self.playback_controller.previous_ms" in source
    assert "self.playback_controller.seek_start_ms" in source
