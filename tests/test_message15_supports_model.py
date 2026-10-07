from __future__ import annotations

import pytest

from hotspot_model import (
    HOTSPOT_MESSAGE_MAX_CHARS,
    Hotspot,
    PauseEvent,
    SupportItem,
    VideoEntry,
    clamp_hotspot_message,
    default_project,
    default_supports,
    message_counter_text,
    normalize_supports,
    serialize_project,
    validate_support_asset,
    videos_from_project_payload,
)


def test_hotspot_message_limit_is_40_for_new_edits_but_legacy_load_preserves_text() -> None:
    long_text = "x" * 60
    hotspot = Hotspot.from_dict({"hotspot_id": "h1", "message_text": long_text})

    assert HOTSPOT_MESSAGE_MAX_CHARS == 40
    assert hotspot.message_text == long_text
    assert clamp_hotspot_message(long_text) == "x" * 40
    assert message_counter_text(long_text) == "40/40"


def test_default_supports_are_three_empty_visible_slots() -> None:
    supports = default_supports()

    assert [support.support_id for support in supports] == ["support_1", "support_2", "support_3"]
    assert [support.label for support in supports] == ["Apoyo 1", "Apoyo 2", "Apoyo 3"]
    assert all(support.visible for support in supports)


def test_supports_are_normalized_per_video_and_serialized_independently() -> None:
    first = VideoEntry(
        "v1",
        "Video 1",
        "../../circular.mp4",
        [PauseEvent("p1", 1000, [], [SupportItem("support_1", label="Texto", text="Hola")])],
    )
    second = VideoEntry(
        "v2",
        "Video 2",
        "../../circular.mp4",
        [PauseEvent("p2", 2000, [], [SupportItem("support_2", label="Imagen", image_asset="assets/supports/images/card.png", position=1)])],
    )

    payload = serialize_project(default_project(), [], 0, [first, second], 1)
    videos = videos_from_project_payload(payload)

    assert len(payload["videos"][0]["pause_events"][0]["supports"]) == 3
    assert len(payload["videos"][1]["pause_events"][0]["supports"]) == 3
    assert videos[0].pauses[0].supports[0].text == "Hola"
    assert videos[0].pauses[0].supports[1].image_asset is None
    assert videos[1].pauses[0].supports[1].image_asset == "assets/supports/images/card.png"
    assert videos[1].pauses[0].supports[0].text == ""


def test_support_asset_paths_must_be_portable_project_relative_assets() -> None:
    assert validate_support_asset("assets/supports/images/card.png") == "assets/supports/images/card.png"
    assert validate_support_asset("assets\\supports\\audio\\voice.wav") == "assets/supports/audio/voice.wav"

    for bad_path in [
        "C:/tmp/card.png",
        "/tmp/card.png",
        "../assets/supports/card.png",
        "assets/audio/card.wav",
        "assets/supports",
    ]:
        with pytest.raises(ValueError):
            validate_support_asset(bad_path)


def test_normalize_supports_keeps_three_stable_slots() -> None:
    supports = normalize_supports([SupportItem("support_3", label="Audio", audio_asset="assets/supports/audio/a.wav", position=2)])

    assert [support.support_id for support in supports] == ["support_1", "support_2", "support_3"]
    assert supports[0].label == "Apoyo 1"
    assert supports[1].label == "Apoyo 2"
    assert supports[2].audio_asset == "assets/supports/audio/a.wav"
