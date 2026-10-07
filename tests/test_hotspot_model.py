from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_model import (  # noqa: E402
    COMMUNICATION_CATEGORIES,
    DEFAULT_FILL_OPACITY,
    HOTSPOT_PALETTE,
    FRAME_SIZE,
    History,
    Hotspot,
    PAUSE_TOLERANCE_MS,
    PAUSE_TRIGGER_TOLERANCE_MS,
    PausePoint,
    SupportItem,
    add_hotspot_to_time,
    crossed_pause_times,
    default_project,
    effective_video_rect,
    first_overlap,
    hotspots_overlap,
    find_pause,
    find_or_create_pause,
    move_pixel_rect,
    next_temporal_pause,
    normalized_to_pixel,
    opacity_percent_to_alpha,
    pixel_to_normalized,
    remove_hotspot_from_pause,
    resize_pixel_rect,
    safe_continue_exit_position,
    serialize_project,
    validate_audio_asset,
    validate_category,
    validate_project_payload,
)


def test_pixel_normalized_round_trip():
    pixel = (120, 90, 360, 180)
    normalized = pixel_to_normalized(pixel, FRAME_SIZE)
    restored = normalized_to_pixel(normalized, FRAME_SIZE)
    assert restored == pytest.approx(pixel)


def test_repeated_move_keeps_size_and_stays_inside_video_bounds():
    rect = (1400.0, 780.0, 120.0, 70.0)
    first = move_pixel_rect(rect, (80.0, 80.0), FRAME_SIZE)
    second = move_pixel_rect(first, (80.0, 80.0), FRAME_SIZE)
    assert first[2:] == pytest.approx(rect[2:])
    assert second[2:] == pytest.approx(rect[2:])
    assert 0 <= second[0] <= FRAME_SIZE[0] - second[2]
    assert 0 <= second[1] <= FRAME_SIZE[1] - second[3]


def test_resize_with_handle_clamps_to_bounds_and_minimum_size():
    rect = (10.0, 10.0, 60.0, 60.0)
    resized = resize_pixel_rect(rect, "nw", (200.0, 200.0), FRAME_SIZE, 24.0)
    assert resized[2] >= 24.0
    assert resized[3] >= 24.0
    assert resized[0] >= 0
    assert resized[1] >= 0


def test_new_project_starts_without_pauses_and_no_absolute_video_path():
    payload = default_project(duration_ms=74000)
    assert payload["pauses"] == []
    assert payload["project_id"] == "anna-interactive-video"
    assert payload["video"]["source"] == ""
    assert payload["videos"][0]["source"] == ""


def test_auto_pause_created_when_first_hotspot_is_added():
    pauses: list[PausePoint] = []
    hotspot = Hotspot("h1", shape="rectangle")
    pause, created = add_hotspot_to_time(pauses, 12345, hotspot)
    assert created is True
    assert pause.time_ms == 12345
    assert len(pauses) == 1
    assert pauses[0].hotspots == [hotspot]


def test_second_hotspot_same_pause_does_not_duplicate_marker():
    pauses: list[PausePoint] = []
    first_pause, first_created = add_hotspot_to_time(pauses, 10000, Hotspot("h1"))
    second_pause, second_created = add_hotspot_to_time(pauses, 10100, Hotspot("h2"), PAUSE_TOLERANCE_MS)
    assert first_created is True
    assert second_created is False
    assert second_pause is first_pause
    assert len(pauses) == 1
    assert [h.hotspot_id for h in pauses[0].hotspots] == ["h1", "h2"]


def test_cancel_creation_removes_hotspot_and_empty_pause():
    pauses: list[PausePoint] = []
    pause, _ = add_hotspot_to_time(pauses, 20000, Hotspot("h1"))
    assert remove_hotspot_from_pause(pause, "h1") is True
    if not pause.hotspots:
        pauses = [p for p in pauses if p is not pause]
    assert pauses == []


def test_deleting_last_hotspot_leaves_empty_pause_detectable_for_prompt():
    pause = PausePoint("pause-1", 1, [Hotspot("h1")])
    assert remove_hotspot_from_pause(pause, "h1") is True
    assert pause.hotspots == []


def test_find_pause_uses_documented_tolerance():
    pauses = [PausePoint("pause-10000", 10000)]
    assert find_pause(pauses, 10000 + PAUSE_TOLERANCE_MS) is pauses[0]
    assert find_pause(pauses, 10000 + PAUSE_TOLERANCE_MS + 1) is None


def test_rectangle_and_ellipse_are_valid_shapes():
    rectangle = Hotspot("r", shape="rectangle", geometry=pixel_to_normalized((100, 100, 120, 90)))
    ellipse = Hotspot("e", shape="ellipse", geometry=pixel_to_normalized((300, 100, 120, 90)))
    payload = serialize_project(default_project(), [PausePoint("p", 1, [rectangle, ellipse])])
    pauses = validate_project_payload(payload)
    assert [h.shape for h in pauses[0].hotspots] == ["rectangle", "ellipse"]


def test_default_opacity_15_percent_converts_to_alpha():
    assert DEFAULT_FILL_OPACITY == 15
    assert opacity_percent_to_alpha(15) == 38
    assert opacity_percent_to_alpha(0) == 0
    assert opacity_percent_to_alpha(100) == 255


def test_serializes_message_label_visibility_and_category():
    hotspot = Hotspot("h1", message_text="Quiero agua", hotspot_label="", show_message_text=True, communication_category="noun_object")
    payload = serialize_project(default_project(), [PausePoint("p", 1, [hotspot])], duration_ms=74000)
    raw = payload["pauses"][0]["hotspots"][0]
    assert raw["message_text"] == "Quiero agua"
    assert raw["hotspot_label"] == ""
    assert raw["show_message_text"] is True
    assert raw["communication_category"] == "noun_object"
    assert raw["style"]["fill_opacity"] == 15
    assert raw["style"]["color"] == "#00A6C8"
    assert raw["audio_asset"] is None


def test_rejects_unknown_communication_category():
    payload = serialize_project(default_project(), [PausePoint("p", 1, [Hotspot("h")])])
    payload["pause_events"][0]["hotspots"][0]["communication_category"] = "invented"
    with pytest.raises(ValueError, match="communication_category"):
        validate_project_payload(payload)


def test_current_and_legacy_communication_categories_are_explicit():
    assert validate_category("noun_object") == "noun_object"
    assert validate_category("noun") == "noun_object"
    assert validate_category("descriptor") == "adjective"
    assert validate_category("Descriptor") == "adjective"
    assert validate_category("priority_emergency") == "other"
    assert validate_category("Prioridad / emergencia") == "other"
    with pytest.raises(ValueError, match="unsupported communication_category"):
        validate_category("legacy-but-not-real")


def test_all_initial_categories_are_documented():
    assert set(COMMUNICATION_CATEGORIES) == {
        "unspecified",
        "proper_person",
        "noun_object",
        "verb_action",
        "adjective",
        "adverb",
        "social_expression",
        "function_word",
        "place",
        "other",
    }


def test_temporal_project_round_trip_with_hotspot():
    pause = PausePoint("pause-10000", 10000, [Hotspot(hotspot_id="h1", message_text="Mama", geometry={"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2})])
    payload = serialize_project(default_project(), [pause], duration_ms=74000)
    pauses = validate_project_payload(copy.deepcopy(payload))
    assert len(pauses) == 1
    assert pauses[0].time_ms == 10000
    assert pauses[0].hotspots[0].message_text == "Mama"


def test_invalid_schema_version_is_rejected():
    payload = default_project()
    payload["schema_version"] = "future-version"
    with pytest.raises(ValueError, match="schema_version"):
        validate_project_payload(payload)


def test_duplicate_pause_times_are_rejected():
    payload = serialize_project(default_project(), [PausePoint("a", 1), PausePoint("b", 1)])
    with pytest.raises(ValueError, match="duplicate pause"):
        validate_project_payload(payload)


def test_duplicate_hotspot_ids_inside_pause_are_rejected():
    payload = default_project()
    payload["pauses"] = [PausePoint("p", 1, [Hotspot("same"), Hotspot("same")]).to_dict()]
    with pytest.raises(ValueError, match="duplicate hotspot_id in pause p: same"):
        validate_project_payload(payload)


def test_duplicate_support_ids_inside_pause_are_rejected():
    payload = default_project()
    payload["pauses"] = [
        PausePoint(
            "p",
            1,
            supports=[
                SupportItem("same", position=0),
                SupportItem("same", position=1),
            ],
        ).to_dict()
    ]
    with pytest.raises(ValueError, match="duplicate support_id in pause p: same"):
        validate_project_payload(payload)


def test_support_ids_with_hyphen_are_preserved_and_serialization_does_not_mutate():
    support = SupportItem("support-1", label="Apoyo legado", text="Texto", position=0)
    pause = PausePoint("p", 1, supports=[support])
    raw = pause.to_dict()
    assert raw["supports"][0]["support_id"] == "support-1"
    assert support.support_id == "support-1"

    payload = serialize_project(default_project(), [pause])
    assert payload["pauses"][0]["supports"][0]["support_id"] == "support-1"
    assert support.support_id == "support-1"

    loaded = validate_project_payload(payload)
    assert loaded[0].supports[0].support_id == "support-1"


def test_legacy_pauses_are_used_when_pause_events_is_empty():
    payload = default_project()
    payload["pause_events"] = []
    payload["pauses"] = [
        {
            "pause_id": "legacy-pause",
            "time_ms": 1000,
            "hotspots": [{"hotspot_id": "h1", "communication_category": "descriptor"}],
            "supports": [{"support_id": "support-1", "text": "Ayuda", "position": 0}],
        }
    ]
    pauses = validate_project_payload(payload)
    assert pauses[0].pause_id == "legacy-pause"
    assert pauses[0].hotspots[0].communication_category == "adjective"
    assert pauses[0].supports[0].support_id == "support-1"


def test_history_undo_redo():
    history = History()
    history.push({"step": 1})
    history.push({"step": 2})
    assert history.undo() == {"step": 1}
    assert history.redo() == {"step": 2}


def test_palette_is_limited_and_persisted():
    assert set(HOTSPOT_PALETTE.values()) == {"#00A6C8", "#2A7FD1", "#45A84A", "#FF8C24", "#D94A9C", "#D94848"}
    hotspot = Hotspot("h1", color="#45A84A")
    payload = serialize_project(default_project(), [PausePoint("p", 1, [hotspot])])
    assert payload["pauses"][0]["hotspots"][0]["style"]["color"] == "#45A84A"


def test_audio_asset_serializes_relative_path():
    hotspot = Hotspot("h1", audio_asset="assets/audio/test.wav")
    payload = serialize_project(default_project(), [PausePoint("p", 1, [hotspot])])
    raw = payload["pauses"][0]["hotspots"][0]
    assert raw["audio_asset"] == "assets/audio/test.wav"


def test_audio_asset_rejects_absolute_and_traversal_paths():
    with pytest.raises(ValueError, match="relative"):
        validate_audio_asset("C:/secret/test.wav")
    with pytest.raises(ValueError, match="traversal"):
        validate_audio_asset("assets/audio/../secret.wav")
    with pytest.raises(ValueError, match="assets/audio"):
        validate_audio_asset("recordings/test.wav")


def test_hotspot_without_audio_is_valid():
    payload = serialize_project(default_project(), [PausePoint("p", 1, [Hotspot("h1")])])
    pauses = validate_project_payload(payload)
    assert pauses[0].hotspots[0].audio_asset is None


def test_effective_video_rect_same_ratio_side_and_top_bottom_letterboxing():
    assert effective_video_rect(1536, 864) == pytest.approx((0, 0, 1536, 864))
    assert effective_video_rect(2000, 864) == pytest.approx((232, 0, 1536, 864))
    assert effective_video_rect(1536, 1200) == pytest.approx((0, 168, 1536, 864))


def test_overlap_detection_by_effective_shape_and_touching_edges_allowed():
    rect_a = Hotspot("a", shape="rectangle", geometry=pixel_to_normalized((100, 100, 200, 120)))
    rect_b = Hotspot("b", shape="rectangle", geometry=pixel_to_normalized((250, 150, 200, 120)))
    rect_touch = Hotspot("touch", shape="rectangle", geometry=pixel_to_normalized((300, 100, 80, 120)))
    rect_far = Hotspot("far", shape="rectangle", geometry=pixel_to_normalized((500, 500, 80, 80)))
    ellipse_a = Hotspot("ea", shape="ellipse", geometry=pixel_to_normalized((100, 100, 200, 120)))
    ellipse_b = Hotspot("eb", shape="ellipse", geometry=pixel_to_normalized((220, 130, 200, 120)))
    rect_ellipse = Hotspot("re", shape="rectangle", geometry=pixel_to_normalized((210, 130, 120, 80)))
    assert hotspots_overlap(rect_a, rect_b)
    assert hotspots_overlap(ellipse_a, ellipse_b)
    assert hotspots_overlap(ellipse_a, rect_ellipse)
    assert not hotspots_overlap(rect_a, rect_touch)
    assert not hotspots_overlap(rect_a, rect_far)
    assert first_overlap(rect_a, [rect_far, rect_b]).hotspot_id == "b"


def test_same_geometry_allowed_across_pauses_but_rejected_inside_one_pause():
    first = Hotspot("h1", geometry=pixel_to_normalized((100, 100, 200, 120)))
    second = Hotspot("h2", geometry=pixel_to_normalized((100, 100, 200, 120)))
    validate_project_payload(serialize_project(default_project(), [PausePoint("a", 1000, [first]), PausePoint("b", 2000, [second])]))
    with pytest.raises(ValueError, match="overlap"):
        validate_project_payload(serialize_project(default_project(), [PausePoint("a", 1000, [first, second])]))


def test_safe_continue_considers_next_pause_and_separates_creation_from_trigger_tolerance():
    pauses = [PausePoint("a", 2000), PausePoint("b", 2500), PausePoint("c", 9000)]
    exit_position, next_pause = safe_continue_exit_position(2000, pauses, 10000, PAUSE_TRIGGER_TOLERANCE_MS)
    assert exit_position == 2000 + PAUSE_TRIGGER_TOLERANCE_MS + 1
    assert next_pause == 2500
    close_exit, close_next = safe_continue_exit_position(2000, [PausePoint("a", 2000), PausePoint("b", 2110)], 10000, PAUSE_TRIGGER_TOLERANCE_MS)
    assert close_exit == 2109
    assert close_next == 2110


def test_temporal_crossing_detects_single_pause_without_exact_position_signal():
    pauses = [PausePoint("p4000", 4000)]
    pause, diagnostics = next_temporal_pause(pauses, {}, 3890, 4250)
    assert pause is pauses[0]
    assert diagnostics["direction"] == "forward"
    assert diagnostics["crossed"] == [4000]
    assert diagnostics["activated_pause"] == 4000
    assert crossed_pause_times(pauses, 3890, 4250) == [4000]


def test_temporal_crossing_detects_first_of_two_pauses_in_order():
    pauses = [PausePoint("p4000", 4000), PausePoint("p12000", 12000)]
    pause, diagnostics = next_temporal_pause(pauses, {}, 0, 4500)
    assert pause.pause_id == "p4000"
    assert diagnostics["crossed"] == [4000]
    states = {4000: "consumed_for_current_pass"}
    pause, diagnostics = next_temporal_pause(pauses, states, 4121, 12500)
    assert pause.pause_id == "p12000"
    assert diagnostics["crossed"] == [12000]


def test_temporal_crossing_jump_over_multiple_pauses_activates_only_first_armed():
    pauses = [PausePoint("p4000", 4000), PausePoint("p12000", 12000)]
    pause, diagnostics = next_temporal_pause(pauses, {}, 3500, 13000)
    assert pause.pause_id == "p4000"
    assert diagnostics["crossed"] == [4000]
    states = {4000: "consumed_for_current_pass"}
    pause, diagnostics = next_temporal_pause(pauses, states, 3500, 13000)
    assert pause.pause_id == "p12000"
    assert diagnostics["crossed"] == [4000, 12000]
    assert diagnostics["ignored"] == [{"pause_time": 4000, "reason": "state_consumed_for_current_pass"}]


def test_temporal_crossing_from_zero_requires_no_marker_selection():
    pauses = [PausePoint("p4000", 4000)]
    pause, diagnostics = next_temporal_pause(pauses, {}, 0, 4000)
    assert pause.pause_id == "p4000"
    assert diagnostics["pause_states"] == {"4000": "armed"}


def test_temporal_continue_consumes_current_and_allows_next_pause():
    pauses = [PausePoint("p4000", 4000), PausePoint("p12000", 12000)]
    exit_position, next_pause = safe_continue_exit_position(4000, pauses, 20000)
    assert next_pause == 12000
    states = {4000: "consumed_for_current_pass", 12000: "armed"}
    pause, diagnostics = next_temporal_pause(pauses, states, exit_position, 12100)
    assert pause.pause_id == "p12000"
    assert diagnostics["activated_pause"] == 12000


def test_temporal_rearm_after_backward_navigation():
    pauses = [PausePoint("p4000", 4000)]
    states = {4000: "consumed_for_current_pass"}
    position_ms = 1000
    for pause in pauses:
        if pause.time_ms >= position_ms and states.get(pause.time_ms, "armed") == "consumed_for_current_pass":
            states[pause.time_ms] = "armed"
    pause, diagnostics = next_temporal_pause(pauses, states, 1000, 4100)
    assert pause.pause_id == "p4000"
    assert diagnostics["pause_states"] == {"4000": "armed"}


def test_temporal_does_not_activate_twice_in_same_pass_or_during_scrubbing():
    pauses = [PausePoint("p4000", 4000)]
    states = {4000: "consumed_for_current_pass"}
    pause, diagnostics = next_temporal_pause(pauses, states, 3500, 4250)
    assert pause is None
    assert diagnostics["ignored"] == [{"pause_time": 4000, "reason": "state_consumed_for_current_pass"}]
    pause, diagnostics = next_temporal_pause(pauses, {4000: "armed"}, 3500, 4250, scrubbing=True)
    assert pause is None
    assert diagnostics["ignored"] == [{"reason": "scrubbing"}]


def test_temporal_ignores_backward_or_still_positions():
    pauses = [PausePoint("p4000", 4000)]
    pause, diagnostics = next_temporal_pause(pauses, {}, 4500, 3500)
    assert pause is None
    assert diagnostics["direction"] == "backward"
    pause, diagnostics = next_temporal_pause(pauses, {}, 4000, 4000)
    assert pause is None
    assert diagnostics["direction"] == "still"
