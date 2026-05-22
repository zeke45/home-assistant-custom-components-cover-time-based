"""Unit tests for TravelCalculator."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

# Patch dt_util before importing TravelCalculator (avoids homeassistant dependency at import)
from unittest.mock import MagicMock
import sys

# Stub homeassistant.util.dt so TravelCalculator can be imported standalone
dt_stub = MagicMock()
_NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
dt_stub.utcnow.return_value = _NOW
sys.modules.setdefault("homeassistant", MagicMock())
sys.modules.setdefault("homeassistant.util", MagicMock())
sys.modules["homeassistant.util.dt"] = dt_stub

from custom_components.cover_time_based.travel_calculator import (  # noqa: E402
    TravelCalculator,
    TravelStatus,
)


def _now(offset_seconds: float = 0.0) -> datetime:
    """Return a fake 'now' shifted by offset_seconds."""
    from datetime import timedelta
    return _NOW + timedelta(seconds=offset_seconds)


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
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        assert tc.travel_direction == TravelStatus.DIRECTION_DOWN

    def test_position_after_half_time(self):
        tc = make_tc(down=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(10)):
            pos = tc.current_position()
        assert pos == 50

    def test_position_clamped_at_0(self):
        tc = make_tc(down=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(999)):
            pos = tc.current_position()
        assert pos == 0

    def test_position_reached_at_end(self):
        tc = make_tc(down=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(20)):
            assert tc.position_reached()

    def test_is_closed_at_0(self):
        tc = make_tc(down=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(20)):
            assert tc.is_closed()


# ---------------------------------------------------------------------------
# Travel up
# ---------------------------------------------------------------------------

class TestTravelUp:
    def test_starts_traveling_up(self):
        tc = make_tc()
        tc.set_position(0)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_up()
        assert tc.travel_direction == TravelStatus.DIRECTION_UP

    def test_position_after_half_time(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_up()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(10)):
            pos = tc.current_position()
        assert pos == 50

    def test_position_clamped_at_100(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_up()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(999)):
            pos = tc.current_position()
        assert pos == 100

    def test_position_reached_at_100(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_up()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(20)):
            assert tc.position_reached()


# ---------------------------------------------------------------------------
# Target position (start_travel)
# ---------------------------------------------------------------------------

class TestTargetPosition:
    def test_travel_to_50_from_100(self):
        tc = make_tc(down=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel(50)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(10)):
            assert tc.position_reached()
            assert tc.current_position() == 50

    def test_travel_to_75_from_0(self):
        tc = make_tc(up=20)
        tc.set_position(0)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel(75)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(15)):
            assert tc.position_reached()
            assert tc.current_position() == 75

    def test_no_movement_when_already_at_target(self):
        tc = make_tc()
        tc.set_position(50)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel(50)
        # direction should be down (target == current triggers down branch)
        # but position_reached immediately
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            assert tc.position_reached()


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_freezes_position(self):
        tc = make_tc(down=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(5)):
            tc.stop()
        assert tc.current_position() == 75
        assert not tc.is_traveling()
        assert tc.travel_direction == TravelStatus.DIRECTION_NONE

    def test_stop_clears_started_at(self):
        tc = make_tc(down=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(5)):
            tc.stop()
        assert tc._travel_started_at is None


# ---------------------------------------------------------------------------
# Asymmetric travel times
# ---------------------------------------------------------------------------

class TestAsymmetricTimes:
    def test_down_25s_up_30s(self):
        tc = TravelCalculator(25, 30)
        tc.set_position(0)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_up()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(15)):
            pos = tc.current_position()
        assert pos == 50  # 15/30 * 100 = 50

    def test_down_pure_time_with_slat(self):
        """Simulate pure_travel_time_down = 22 (25 - 3 slat compression)."""
        tc = TravelCalculator(22, 22)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel(50)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(11)):
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
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(20)):
            assert not tc.is_traveling()

    def test_multiple_start_travel_resets(self):
        tc = make_tc(down=20, up=20)
        with patch("homeassistant.util.dt.utcnow", return_value=_now(0)):
            tc.start_travel_down()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(10)):
            tc.stop()
        assert tc.current_position() == 50
        with patch("homeassistant.util.dt.utcnow", return_value=_now(10)):
            tc.start_travel_up()
        with patch("homeassistant.util.dt.utcnow", return_value=_now(20)):
            pos = tc.current_position()
        assert pos == 100

