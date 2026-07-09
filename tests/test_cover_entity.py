"""Regression tests for CoverTimeBased — flag centralization, tilt race
condition guard, task lifecycle, and the three race-condition bugs fixed
in v2.7.0 (spurious stop, transient "open" state, concurrent auto-stop
tasks).

Home Assistant stubs are installed by tests/conftest.py before collection.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from custom_components.cover_time_based.const import CONTROL_TYPE_SWITCH_IMPULSE, DOMAIN
from custom_components.cover_time_based.cover import CoverTimeBased

pytestmark = pytest.mark.asyncio


class FakeHass:
    """Minimal hass double: real asyncio tasks, recorded service calls,
    and a `.data` dict so entities can share coordination state exactly
    like the real hass.data[DOMAIN]."""

    def __init__(self):
        self.services = MagicMock()
        self.services.async_call = AsyncMock()
        self.data = {}

    def async_create_task(self, coro):
        return asyncio.ensure_future(coro)


def make_cover(hass: "FakeHass | None" = None, **overrides) -> CoverTimeBased:
    kwargs = dict(
        device_id="test_cover",
        name="Test Cover",
        travel_time_down=20,
        travel_time_up=20,
        control_type=CONTROL_TYPE_SWITCH_IMPULSE,
        open_switch_entity_id="switch.open",
        close_switch_entity_id="switch.close",
    )
    kwargs.update(overrides)
    cover = CoverTimeBased(**kwargs)
    cover.hass = hass if hass is not None else FakeHass()
    return cover


# ---------------------------------------------------------------------------
# 1. Tilt auto-stop race condition guard
# ---------------------------------------------------------------------------

async def test_tilt_second_command_reuses_the_running_auto_stop_task():
    """A second tilt command issued before the first one finishes (e.g. a
    slider dragged quickly) must NOT spawn a second concurrent auto-stop
    task — that would risk a duplicate STOP command, exactly like the
    _auto_stop_running bug fixed for the position side in v2.7.0."""
    cover = make_cover(tilt_time_open=10, tilt_time_close=10)

    with freeze_time("2024-01-01 12:00:00", tick=True) as frozen:
        await cover._async_set_tilt_position(0)
        assert cover._tilt_auto_stop_running is True
        first_task = cover._tilt_auto_stop_task
        assert first_task is not None

        frozen.tick(1)  # still traveling (1s of 10s elapsed)
        await cover._async_set_tilt_position(50)

        assert cover._tilt_auto_stop_task is first_task, (
            "a second _tilt_auto_stop task was spawned while one was already running"
        )

        frozen.tick(20)  # now well past target — is_traveling() becomes False
        await asyncio.wait_for(first_task, timeout=1)

    assert cover._tilt_auto_stop_running is False
    assert cover._tilt_auto_stop_task is None
    assert not cover._tilt_calculator.is_traveling()


# ---------------------------------------------------------------------------
# 2. command_delay applied to tilt commands
# ---------------------------------------------------------------------------

async def test_tilt_position_applies_command_delay():
    cover = make_cover(tilt_time_open=10, tilt_time_close=10, command_delay=50)

    with patch.object(
        cover, "_async_apply_command_delay", wraps=cover._async_apply_command_delay
    ) as mock_delay:
        with freeze_time("2024-01-01 12:00:00", tick=True) as frozen:
            await cover._async_set_tilt_position(0)
            frozen.tick(20)
            await asyncio.wait_for(cover._tilt_auto_stop_task, timeout=1)

    mock_delay.assert_any_call("_async_set_tilt_position")


# ---------------------------------------------------------------------------
# 3. async_stop_cover stops tilt tracking too
# ---------------------------------------------------------------------------

async def test_stop_cover_stops_tilt_and_cancels_its_task():
    cover = make_cover(tilt_time_open=10, tilt_time_close=10)

    with freeze_time("2024-01-01 12:00:00", tick=True):
        await cover._async_set_tilt_position(0)
        tilt_task = cover._tilt_auto_stop_task
        assert cover._tilt_calculator.is_traveling()

        await cover.async_stop_cover()

        assert not cover._tilt_calculator.is_traveling()
        with pytest.raises(asyncio.CancelledError):
            await tilt_task

    assert cover._tilt_auto_stop_running is False
    assert cover._tilt_auto_stop_task is None


# ---------------------------------------------------------------------------
# 4. Centralized flag reset — async_set_ajoure no longer leaks stale flags
# ---------------------------------------------------------------------------

async def test_set_ajoure_resets_leftover_flags_from_a_previous_run():
    cover = make_cover(slat_compression_time_down=5)
    cover._slat_phase_cancelled = True
    cover._auto_stop_running = True

    with freeze_time("2024-01-01 12:00:00", tick=True):
        await cover.async_set_ajoure()

    assert cover._slat_phase_cancelled is False
    assert cover._auto_stop_running is False


# ---------------------------------------------------------------------------
# 5. Background tasks are tied to the entity's lifecycle
# ---------------------------------------------------------------------------

async def test_background_tasks_are_cancelled_on_entity_removal():
    cover = make_cover()

    async def never_ending():
        await asyncio.sleep(1000)

    task = cover._create_tracked_task(never_ending())
    assert task in cover._background_tasks

    cover._async_cleanup_on_remove()

    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# 6. v2.7.0 regression: spurious stop after resuming an interrupted close
# ---------------------------------------------------------------------------

async def test_close_cover_resets_cancelled_flag_left_by_a_previous_stop():
    cover = make_cover(slat_compression_time_down=5)

    with freeze_time("2024-01-01 12:00:00", tick=True) as frozen:
        await cover.async_close_cover()
        frozen.tick(1)
        await cover.async_stop_cover()
        assert cover._slat_phase_cancelled is True  # stop_cover cancels the slat phase

        await cover.async_close_cover()
        assert cover._slat_phase_cancelled is False, (
            "close_cover must clear a _slat_phase_cancelled flag left over from a "
            "previous stop, or the next slat-compression phase silently aborts and "
            "sends a spurious STOP a moment after the CLOSE (v2.7.0 regression)"
        )


# ---------------------------------------------------------------------------
# 7. v2.7.0 regression: transient "open" state during slat compression
# ---------------------------------------------------------------------------

async def test_auto_updater_hook_avoids_transient_open_state():
    cover = make_cover(slat_compression_time_down=5, travel_time_down=20, travel_time_up=20)

    with freeze_time("2024-01-01 12:00:00", tick=True) as frozen:
        await cover.async_close_cover()
        # pure_travel_time_down = 20 - 5 = 15s
        frozen.tick(15)
        assert cover._travel_calculator.position_reached()

        cover.auto_updater_hook(None)

        # Immediately after this synchronous call (before any awaited work),
        # the cover must already report "closing", never a transient "open".
        assert cover.is_closing is True
        assert cover.is_opening is False
        assert cover.current_cover_position == 0


# ---------------------------------------------------------------------------
# 8. v2.7.0 regression: concurrent auto_stop_if_necessary tasks
# ---------------------------------------------------------------------------

async def test_auto_updater_hook_only_spawns_one_auto_stop_task_at_a_time():
    cover = make_cover(travel_time_down=20, travel_time_up=20)

    with freeze_time("2024-01-01 12:00:00", tick=True) as frozen:
        await cover.async_close_cover()
        frozen.tick(25)  # past the end of travel

        cover.auto_updater_hook(None)
        assert cover._auto_stop_running is True
        tasks_after_first_tick = set(cover._background_tasks)

        # A second 100 ms tick fires before the first auto_stop task has run —
        # must not spawn a second one.
        cover.auto_updater_hook(None)
        assert cover._background_tasks == tasks_after_first_tick

        await asyncio.sleep(0)  # let the single task run to completion

    assert cover._auto_stop_running is False


# ---------------------------------------------------------------------------
# 9. Production bug: spurious STOP fired right behind an OPEN/CLOSE that is
#    already at its target (e.g. retriggered right after a HA restart, when
#    the cover is almost always already sitting at 0 % or 100 %).
# ---------------------------------------------------------------------------

async def test_close_cover_already_at_zero_does_not_arm_spurious_stop():
    """Retriggering close_cover while already at 0 % must resend the CLOSE
    command (as a retry/nudge) but must NOT arm the 100 ms auto-updater —
    doing so would make position_reached() true on the very next tick and
    fire a STOP a moment behind the CLOSE (dangerous with send_stop_at_end
    enabled: some RF/relay receivers treat back-to-back opposite commands
    as a conflicting signal)."""
    cover = make_cover(send_stop_at_end=True)
    cover._travel_calculator.set_position(0)

    with freeze_time("2024-01-01 12:00:00", tick=True):
        await cover.async_close_cover()

    assert cover._unsubscribe_auto_updater is None, (
        "auto-updater must not be armed for a zero-distance close"
    )
    assert cover.hass.services.async_call.await_count == 1
    call = cover.hass.services.async_call.await_args_list[0]
    assert call.kwargs["service_data"]["entity_id"] == "switch.close"


async def test_close_cover_retry_is_not_mistaken_for_physical_bypass():
    """Regression: the zero-distance CLOSE retry never marks the
    TravelCalculator as traveling (nothing to travel), so the close switch's
    own state_changed event — fired as a side effect of OUR turn_on call —
    must not be mistaken by the physical-bypass detector for an externally
    triggered close. Otherwise the detector re-arms the exact same
    zero-distance travel itself and fires a spurious STOP a moment later,
    even after the fix in test_close_cover_already_at_zero_does_not_arm_spurious_stop."""
    cover = make_cover(send_stop_at_end=True, stop_switch_entity_id="switch.stop")
    cover._travel_calculator.set_position(0)

    with freeze_time("2024-01-01 12:00:00", tick=True):
        await cover.async_close_cover()

        # Simulate HA delivering the close switch's own state_changed event
        # shortly after our turn_on call — this is exactly what the physical
        # bypass detector is subscribed to.
        event = MagicMock()
        event.data = {"entity_id": "switch.close", "new_state": MagicMock(state="on")}
        cover._async_switch_state_changed(event)

        assert not cover._travel_calculator.is_traveling(), (
            "the echo of our own CLOSE command must not re-arm travel tracking"
        )
        assert cover._unsubscribe_auto_updater is None


async def test_genuine_physical_close_is_still_detected():
    """Make sure the echo suppression above doesn't break real bypass
    detection: a close switch turning on WITHOUT a preceding close_cover()
    call must still be tracked as an external trigger."""
    cover = make_cover()
    cover._travel_calculator.set_position(100)

    with freeze_time("2024-01-01 12:00:00", tick=True):
        event = MagicMock()
        event.data = {"entity_id": "switch.close", "new_state": MagicMock(state="on")}
        cover._async_switch_state_changed(event)

        assert cover._travel_calculator.is_traveling()
        assert cover._last_physical_action == "close"


async def test_open_cover_already_at_hundred_does_not_arm_spurious_stop():
    """Symmetric case for open_cover at 100 %."""
    cover = make_cover(send_stop_at_end=True)
    cover._travel_calculator.set_position(100)

    with freeze_time("2024-01-01 12:00:00", tick=True):
        await cover.async_open_cover()

    assert cover._unsubscribe_auto_updater is None
    assert cover.hass.services.async_call.await_count == 1
    call = cover.hass.services.async_call.await_args_list[0]
    assert call.kwargs["service_data"]["entity_id"] == "switch.open"


# ---------------------------------------------------------------------------
# 10. Production bug: close_cover must always retrigger, even if a previous
#     run wrongly believes the cover is already fully closed.
# ---------------------------------------------------------------------------

async def test_close_cover_always_retriggers_even_if_marked_fully_closed():
    cover = make_cover(slat_compression_time_down=5)
    cover._travel_calculator.set_position(0)
    cover._is_fully_closed = True  # stale/wrong belief — shutter isn't really closed

    with freeze_time("2024-01-01 12:00:00", tick=True):
        task = asyncio.ensure_future(cover.async_close_cover())
        await asyncio.sleep(0)  # let it start and reach the inline slat-compression phase

        assert cover._slat_phase_running is True, (
            "close_cover must always re-attempt, even if a previous run "
            "believed the cover was already fully closed — otherwise a stuck "
            "or wrong _is_fully_closed flag permanently blocks the close button"
        )

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# 11. Production bug: command_delay must stagger commands ACROSS entities,
#     not just shift every entity's send time by the same constant.
# ---------------------------------------------------------------------------

async def test_command_delay_staggers_commands_across_entities():
    hass = FakeHass()
    cover_a = make_cover(hass=hass, device_id="cover_a", command_delay=100)
    cover_b = make_cover(hass=hass, device_id="cover_b", command_delay=100)
    cover_a._travel_calculator.set_position(0)
    cover_b._travel_calculator.set_position(0)

    loop = asyncio.get_event_loop()
    start = loop.time()
    await asyncio.gather(cover_a.async_close_cover(), cover_b.async_close_cover())
    elapsed = loop.time() - start

    # If the two entities' delays were independent (the bug), both would
    # fire after ~1x command_delay, elapsed ~0.1s. Staggered via the shared
    # lock, the second entity must wait for the first's full delay too.
    assert elapsed >= 0.15, (
        f"expected the two close commands to be staggered by command_delay "
        f"(≥150ms), got {elapsed:.3f}s — they were sent essentially at once"
    )
    assert DOMAIN in hass.data
    assert "_command_delay_lock" in hass.data[DOMAIN]
