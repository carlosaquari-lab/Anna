from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hotspot_model import effective_video_rect, message_strip_geometry  # noqa: E402


def test_message_strip_matches_video_when_aspect_ratio_is_equal() -> None:
    assert effective_video_rect(1600, 900, 1600, 900) == pytest.approx((0, 0, 1600, 900))
    assert message_strip_geometry(1600, 900, 1600, 900) == pytest.approx((0, 1600))


def test_message_strip_uses_left_offset_and_width_with_side_letterboxing() -> None:
    assert effective_video_rect(2000, 900, 1600, 900) == pytest.approx((200, 0, 1600, 900))
    assert message_strip_geometry(2000, 900, 1600, 900) == pytest.approx((200, 1600))


def test_message_strip_ignores_top_bottom_letterboxing_for_horizontal_alignment() -> None:
    assert effective_video_rect(1600, 1200, 1600, 900) == pytest.approx((0, 150, 1600, 900))
    assert message_strip_geometry(1600, 1200, 1600, 900) == pytest.approx((0, 1600))


def test_message_strip_recalculates_after_resize() -> None:
    small_left, small_width = message_strip_geometry(1000, 900, 1600, 900)
    large_left, large_width = message_strip_geometry(2400, 900, 1600, 900)
    assert (small_left, small_width) == pytest.approx((0, 1000))
    assert (large_left, large_width) == pytest.approx((400, 1600))


def test_message_strip_supports_different_video_aspect_ratio() -> None:
    left, width = message_strip_geometry(1600, 900, 1000, 1000)
    assert left == pytest.approx(350)
    assert width == pytest.approx(900)
