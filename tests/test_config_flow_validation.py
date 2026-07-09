"""Unit tests for config_flow timing validation helper."""
# Home Assistant stubs are installed by tests/conftest.py before collection.
import custom_components.cover_time_based.config_flow as cf

_validate = cf._validate_timing


class TestValidateTiming:
    # ---- No errors ----

    def test_valid_basic(self):
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 25,
            "slat_compression_time_down": 0,
            "slat_compression_time_up": 0,
        })
        assert errors == {}

    def test_valid_with_slat(self):
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 26,
            "slat_compression_time_down": 3,
            "slat_compression_time_up": 4,
        })
        assert errors == {}

    def test_slat_equal_to_travel_minus_1_is_valid(self):
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 25,
            "slat_compression_time_down": 24,
            "slat_compression_time_up": 24,
        })
        assert errors == {}

    # ---- Travel time errors ----

    def test_travel_time_down_zero(self):
        errors = _validate({
            "travelling_time_down": 0,
            "travelling_time_up": 25,
            "slat_compression_time_down": 0,
            "slat_compression_time_up": 0,
        })
        assert "travelling_time_down" in errors
        assert errors["travelling_time_down"] == "travel_time_too_low"

    def test_travel_time_up_zero(self):
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 0,
            "slat_compression_time_down": 0,
            "slat_compression_time_up": 0,
        })
        assert "travelling_time_up" in errors

    def test_both_travel_times_zero(self):
        errors = _validate({
            "travelling_time_down": 0,
            "travelling_time_up": 0,
            "slat_compression_time_down": 0,
            "slat_compression_time_up": 0,
        })
        assert "travelling_time_down" in errors
        assert "travelling_time_up" in errors

    # ---- Slat time errors ----

    def test_slat_down_equal_to_travel_down(self):
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 25,
            "slat_compression_time_down": 25,
            "slat_compression_time_up": 0,
        })
        assert "slat_compression_time_down" in errors
        assert errors["slat_compression_time_down"] == "slat_time_too_high"

    def test_slat_down_greater_than_travel_down(self):
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 25,
            "slat_compression_time_down": 30,
            "slat_compression_time_up": 0,
        })
        assert "slat_compression_time_down" in errors

    def test_slat_up_equal_to_travel_up(self):
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 25,
            "slat_compression_time_down": 0,
            "slat_compression_time_up": 25,
        })
        assert "slat_compression_time_up" in errors

    def test_slat_disabled_zero_no_error(self):
        """slat = 0 means disabled, should never raise slat_time_too_high."""
        errors = _validate({
            "travelling_time_down": 1,
            "travelling_time_up": 1,
            "slat_compression_time_down": 0,
            "slat_compression_time_up": 0,
        })
        assert "slat_compression_time_down" not in errors
        assert "slat_compression_time_up" not in errors

    # ---- Missing keys (defaults) ----

    def test_missing_slat_keys_use_defaults(self):
        """Missing slat keys should not raise errors."""
        errors = _validate({
            "travelling_time_down": 25,
            "travelling_time_up": 25,
        })
        assert errors == {}

