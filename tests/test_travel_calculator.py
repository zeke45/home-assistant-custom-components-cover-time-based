"""Unit tests for TravelCalculator."""
from unittest.mock import patch

import pytest

from custom_components.cover_time_based.travel_calculator import (
    TravelCalculator,
    TravelStatus,
)

_NOW = 1_700_000_000.0  # arbitrary monotonic base


def _now(offset_seconds: float = 0.0) -> float:
    """Return a fake monotonic 'now' shifted by offset_seconds."""
    return _NOW + offset_seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tc(down: int = 20, up: int = 20) -> TravelCalculator:
    return TravelCalculator(down, up)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_default_position_is_100(self):
        tc = make_tc()
        assert tc.current_position() == 100

    def test_not_traveling(self):
        tc = make_tc()
        assert not tc.is_traveling()

    def test_direction_none(self):
        tc = make_tc()
        assert tc.travel_direction == TravelStatus.DIRECTION_NONE

    def test_set_position(self):
        tc = make_tc()
        tc.set_position(50)
        assert tc.current_position() == 50

    def test_position_reached_when_idle(self):
        tc = make_tc()
        assert tc.position_reached()


# ---------------------------------------------------------------------------
# Travel down
# ---------------------------------------------------------------------------

class TestTravelDown:
    def test_starts_traveling_down(self):
        tc = make_tc()
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        assert tc.travel_direction == TravelStatus.DIRECTION_DOWN

    def test_position_after_half_time(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(10)):
            pos = tc.current_position()
        assert pos == 50

    def test_position_clamped_at_0(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(999)):
            pos = tc.current_position()
        assert pos == 0

    def test_position_reached_at_end(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(20)):
            assert tc.position_reached()

    def test_is_closed_at_0(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(20)):
            assert tc.is_closed()


# ---------------------------------------------------------------------------
# Travel up
# ---------------------------------------------------------------------------

class TestTravelUp:
    def test_starts_traveling_up(self):
        tc = make_tc()
        tc.set_position(0)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_up()
        assert tc.travel_direction == TravelStatus.DIRECTION_UP

    def test_position_after_half_time(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_up()
        with patch("time.monotonic", return_value=_now(10)):
            pos = tc.current_position()
        assert pos == 50

    def test_position_clamped_at_100(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_up()
        with patch("time.monotonic", return_value=_now(999)):
            pos = tc.current_position()
        assert pos == 100

    def test_position_reached_at_100(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_up()
        with patch("time.monotonic", return_value=_now(20)):
            assert tc.position_reached()


# ---------------------------------------------------------------------------
# Target position (start_travel)
# ---------------------------------------------------------------------------

class TestTargetPosition:
    def test_travel_to_50_from_100(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel(50)
        with patch("time.monotonic", return_value=_now(10)):
            assert tc.position_reached()
            assert tc.current_position() == 50

    def test_travel_to_75_from_0(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel(75)
        with patch("time.monotonic", return_value=_now(15)):
            assert tc.position_reached()
            assert tc.current_position() == 75

    def test_no_movement_when_already_at_target(self):
        tc = make_tc()
        tc.set_position(50)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel(50)
        # direction should be down (target == current triggers down branch)
        # but position_reached immediately
        with patch("time.monotonic", return_value=_now(0)):
            assert tc.position_reached()


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_freezes_position(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(5)):
            tc.stop()
        assert tc.current_position() == 75
        assert not tc.is_traveling()
        assert tc.travel_direction == TravelStatus.DIRECTION_NONE

    def test_stop_clears_started_at(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(5)):
            tc.stop()
        assert tc._travel_started_at is None


# ---------------------------------------------------------------------------
# Asymmetric travel times
# ---------------------------------------------------------------------------

class TestAsymmetricTimes:
    def test_down_25s_up_30s(self):
        tc = TravelCalculator(25, 30)
        tc.set_position(0)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_up()
        with patch("time.monotonic", return_value=_now(15)):
            pos = tc.current_position()
        assert pos == 50  # 15/30 * 100 = 50

    def test_down_pure_time_with_slat(self):
        """Simulate pure_travel_time_down = 22 (25 - 3 slat compression)."""
        tc = TravelCalculator(22, 22)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel(50)
        with patch("time.monotonic", return_value=_now(11)):
            pos = tc.current_position()
        assert pos == 50


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_minimum_travel_time_1s(self):
        tc = TravelCalculator(0, 0)  # should be clamped to 1
        assert tc._travel_time_down == 1
        assert tc._travel_time_up == 1

    def test_is_traveling_false_after_position_reached(self):
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(20)):
            assert not tc.is_traveling()

    def test_multiple_start_travel_resets(self):
        tc = make_tc(down=20, up=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        with patch("time.monotonic", return_value=_now(10)):
            tc.stop()
        assert tc.current_position() == 50
        with patch("time.monotonic", return_value=_now(10)):
            tc.start_travel_up()
        with patch("time.monotonic", return_value=_now(20)):
            pos = tc.current_position()
        assert pos == 100

    def test_wall_clock_jump_does_not_affect_position(self):
        """A system-clock change (NTP resync, DST) must not perturb the
        elapsed-time calculation, since it now relies on time.monotonic()
        rather than the wall clock."""
        tc = make_tc(down=20)
        with patch("time.monotonic", return_value=_now(0)):
            tc.start_travel_down()
        # Only the monotonic clock matters — no dependency on wall-clock time
        with patch("time.monotonic", return_value=_now(10)):
            assert tc.current_position() == 50
