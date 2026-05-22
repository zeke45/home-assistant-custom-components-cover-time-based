"""Cover Time Based."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    PLATFORM_SCHEMA,
    CoverEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.core import callback
from homeassistant.helpers import template as template_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AJOURE_POSITION,
    ATTR_CONTROL_TYPE,
    ATTR_POSITION_UNCERTAIN,
    CONF_ALIASES,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_SWITCH_SUSTAINED_TIME,
    CONF_CLOSE_SCRIPT_ENTITY_ID,
    CONF_CLOSE_SWITCH_ENTITY_ID,
    CONF_COMMAND_DELAY,
    CONF_CONTROL_TYPE,
    CONF_COVER_ENTITY_ID,
    CONF_DEVICES,
    CONF_IMPULSE_MODE,
    CONF_OPEN_SCRIPT_ENTITY_ID,
    CONF_OPEN_SWITCH_ENTITY_ID,
    CONF_SEND_STOP_AT_END,
    CONF_SLAT_COMPRESSION_TIME_DOWN,
    CONF_SLAT_COMPRESSION_TIME_UP,
    CONF_STOP_SCRIPT_ENTITY_ID,
    CONF_STOP_SWITCH_ENTITY_ID,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    CONTROL_TYPE_COVER,
    CONTROL_TYPE_SCRIPT,
    CONTROL_TYPE_SWITCH,
    CONTROL_TYPE_SWITCH_IMPULSE,
    CONTROL_TYPE_SWITCH_SUSTAINED,
    DEFAULT_SWITCH_SUSTAINED_TIME,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_CONTROL_TYPE,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_IMPULSE_MODE,
    DEFAULT_SEND_STOP_AT_END,
    DEFAULT_SLAT_COMPRESSION_TIME_DOWN,
    DEFAULT_SLAT_COMPRESSION_TIME_UP,
    DEFAULT_TRAVEL_TIME,
)
from .travel_calculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): vol.Schema(
            {
                cv.string: {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_CONTROL_TYPE, default=DEFAULT_CONTROL_TYPE): vol.In(
                        [CONTROL_TYPE_SWITCH, CONTROL_TYPE_SWITCH_IMPULSE,
                         CONTROL_TYPE_SWITCH_SUSTAINED, CONTROL_TYPE_SCRIPT, CONTROL_TYPE_COVER]
                    ),
                    # switch
                    vol.Optional(CONF_OPEN_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_CLOSE_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_STOP_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(
                        CONF_SWITCH_SUSTAINED_TIME,
                        default=DEFAULT_SWITCH_SUSTAINED_TIME,
                    ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                    vol.Optional(CONF_IMPULSE_MODE, default=DEFAULT_IMPULSE_MODE): cv.boolean,
                    # script
                    vol.Optional(CONF_OPEN_SCRIPT_ENTITY_ID): cv.string,
                    vol.Optional(CONF_CLOSE_SCRIPT_ENTITY_ID): cv.string,
                    vol.Optional(CONF_STOP_SCRIPT_ENTITY_ID): cv.string,
                    # cover delegation
                    vol.Optional(CONF_COVER_ENTITY_ID): cv.string,
                    # common
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional(
                        CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_SEND_STOP_AT_END, default=DEFAULT_SEND_STOP_AT_END
                    ): cv.boolean,
                    vol.Optional(CONF_DEVICE_CLASS): cv.string,
                    vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
                    vol.Optional(
                        CONF_COMMAND_DELAY, default=DEFAULT_COMMAND_DELAY
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
                    vol.Optional(
                        CONF_SLAT_COMPRESSION_TIME_DOWN,
                        default=DEFAULT_SLAT_COMPRESSION_TIME_DOWN,
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                    vol.Optional(
                        CONF_SLAT_COMPRESSION_TIME_UP,
                        default=DEFAULT_SLAT_COMPRESSION_TIME_UP,
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                }
            }
        ),
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def devices_from_config(domain_config: dict) -> list["CoverTimeBased"]:
    """Parse legacy YAML configuration and return cover entities."""
    devices: list[CoverTimeBased] = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        name = config.pop(CONF_NAME, device_id)
        control_type = config.pop(CONF_CONTROL_TYPE, DEFAULT_CONTROL_TYPE)
        travel_time_down = config.pop(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)
        travel_time_up = config.pop(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)
        send_stop_at_end = config.pop(CONF_SEND_STOP_AT_END, DEFAULT_SEND_STOP_AT_END)
        device_class = config.pop(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS)
        availability_template = config.pop(CONF_AVAILABILITY_TEMPLATE, None)
        command_delay = config.pop(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY)
        slat_compression_time_down = config.pop(CONF_SLAT_COMPRESSION_TIME_DOWN, DEFAULT_SLAT_COMPRESSION_TIME_DOWN)
        slat_compression_time_up   = config.pop(CONF_SLAT_COMPRESSION_TIME_UP,   DEFAULT_SLAT_COMPRESSION_TIME_UP)

        device = CoverTimeBased(
            device_id=device_id,
            name=name,
            control_type=control_type,
            travel_time_down=travel_time_down,
            travel_time_up=travel_time_up,
            open_switch_entity_id=config.pop(CONF_OPEN_SWITCH_ENTITY_ID, None),
            close_switch_entity_id=config.pop(CONF_CLOSE_SWITCH_ENTITY_ID, None),
            stop_switch_entity_id=config.pop(CONF_STOP_SWITCH_ENTITY_ID, None),
            switch_sustained_time=config.pop(
                CONF_SWITCH_SUSTAINED_TIME, DEFAULT_SWITCH_SUSTAINED_TIME
            ),
            impulse_mode=config.pop(CONF_IMPULSE_MODE, DEFAULT_IMPULSE_MODE),
            open_script_entity_id=config.pop(CONF_OPEN_SCRIPT_ENTITY_ID, None),
            close_script_entity_id=config.pop(CONF_CLOSE_SCRIPT_ENTITY_ID, None),
            stop_script_entity_id=config.pop(CONF_STOP_SCRIPT_ENTITY_ID, None),
            cover_entity_id=config.pop(CONF_COVER_ENTITY_ID, None),
            send_stop_at_end=send_stop_at_end,
            device_class=device_class,
            availability_template=availability_template,
            command_delay=command_delay,
            slat_compression_time_down=slat_compression_time_down,
            slat_compression_time_up=slat_compression_time_up,
            unique_id=device_id,
        )
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the cover platform (legacy YAML)."""
    async_add_entities(devices_from_config(config))


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Cover Time Based from a config entry (UI flow)."""
    data = {**config_entry.data, **config_entry.options}

    name = config_entry.title or data.get(CONF_NAME, config_entry.entry_id)

    avail_tpl_str = data.get(CONF_AVAILABILITY_TEMPLATE)
    avail_tpl = template_helper.Template(avail_tpl_str, hass) if avail_tpl_str else None

    device = CoverTimeBased(
        device_id=config_entry.entry_id,
        name=name,
        control_type=data.get(CONF_CONTROL_TYPE, DEFAULT_CONTROL_TYPE),
        travel_time_down=data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
        travel_time_up=data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
        open_switch_entity_id=data.get(CONF_OPEN_SWITCH_ENTITY_ID, ""),
        close_switch_entity_id=data.get(CONF_CLOSE_SWITCH_ENTITY_ID, ""),
        stop_switch_entity_id=data.get(CONF_STOP_SWITCH_ENTITY_ID),
        switch_sustained_time=data.get(
            CONF_SWITCH_SUSTAINED_TIME, DEFAULT_SWITCH_SUSTAINED_TIME
        ),
        impulse_mode=data.get(CONF_IMPULSE_MODE, DEFAULT_IMPULSE_MODE),
        open_script_entity_id=data.get(CONF_OPEN_SCRIPT_ENTITY_ID),
        close_script_entity_id=data.get(CONF_CLOSE_SCRIPT_ENTITY_ID),
        stop_script_entity_id=data.get(CONF_STOP_SCRIPT_ENTITY_ID),
        cover_entity_id=data.get(CONF_COVER_ENTITY_ID),
        send_stop_at_end=data.get(CONF_SEND_STOP_AT_END, DEFAULT_SEND_STOP_AT_END),
        device_class=data.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
        availability_template=avail_tpl,
        command_delay=data.get(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY),
        slat_compression_time_down=data.get(CONF_SLAT_COMPRESSION_TIME_DOWN, DEFAULT_SLAT_COMPRESSION_TIME_DOWN),
        slat_compression_time_up=data.get(CONF_SLAT_COMPRESSION_TIME_UP, DEFAULT_SLAT_COMPRESSION_TIME_UP),
        unique_id=config_entry.entry_id,
    )
    async_add_entities([device])

    # Register custom entity service
    from homeassistant.helpers import entity_platform as ep  # noqa: PLC0415
    platform = ep.async_get_current_platform()
    platform.async_register_entity_service("set_ajoure", {}, "async_set_ajoure")
    platform.async_register_entity_service(
        "set_known_position",
        {vol.Required("position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100))},
        "async_set_known_position",
    )


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class CoverTimeBased(CoverEntity, RestoreEntity):
    """Representation of a time-based cover."""

    def __init__(
        self,
        device_id: str,
        name: str,
        travel_time_down: int,
        travel_time_up: int,
        # switch mode
        open_switch_entity_id: str | None = None,
        close_switch_entity_id: str | None = None,
        stop_switch_entity_id: str | None = None,
        switch_sustained_time: int = DEFAULT_SWITCH_SUSTAINED_TIME,
        impulse_mode: bool = DEFAULT_IMPULSE_MODE,
        # script mode
        open_script_entity_id: str | None = None,
        close_script_entity_id: str | None = None,
        stop_script_entity_id: str | None = None,
        # cover delegation
        cover_entity_id: str | None = None,
        # common
        control_type: str = DEFAULT_CONTROL_TYPE,
        send_stop_at_end: bool = DEFAULT_SEND_STOP_AT_END,
        device_class: str | None = DEFAULT_DEVICE_CLASS,
        availability_template=None,
        command_delay: int = DEFAULT_COMMAND_DELAY,
        slat_compression_time_down: int = DEFAULT_SLAT_COMPRESSION_TIME_DOWN,
        slat_compression_time_up: int = DEFAULT_SLAT_COMPRESSION_TIME_UP,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the cover."""
        self._travel_time_down: int = max(int(travel_time_down), 1)
        self._travel_time_up: int = max(int(travel_time_up), 1)

        # Normalize the two explicit UI types → switch + impulse_mode derived
        if control_type == CONTROL_TYPE_SWITCH_IMPULSE:
            self._control_type = CONTROL_TYPE_SWITCH
            self._impulse_mode = True
        elif control_type == CONTROL_TYPE_SWITCH_SUSTAINED:
            self._control_type = CONTROL_TYPE_SWITCH
            self._impulse_mode = False
        else:
            # Legacy YAML: control_type=switch honours the impulse_mode flag as-is
            self._control_type = control_type
            self._impulse_mode = impulse_mode

        # Switch mode
        self._open_switch_entity_id: str | None = open_switch_entity_id
        self._close_switch_entity_id: str | None = close_switch_entity_id
        self._stop_switch_entity_id: str | None = stop_switch_entity_id
        self._switch_sustained_time: int = switch_sustained_time

        # Script mode
        self._open_script_entity_id: str | None = open_script_entity_id
        self._close_script_entity_id: str | None = close_script_entity_id
        self._stop_script_entity_id: str | None = stop_script_entity_id

        # Cover delegation
        self._cover_entity_id: str | None = cover_entity_id

        # Common
        self._send_stop_at_end: bool = send_stop_at_end
        self._device_class_value: str | None = device_class
        self._availability_template = availability_template
        self._command_delay: int = max(int(command_delay), 0)
        self._slat_compression_time_down: int = max(int(slat_compression_time_down), 0)
        self._slat_compression_time_up: int   = max(int(slat_compression_time_up), 0)
        self._availability_error_count: int = 0

        self._name: str = name if name else device_id
        self._unique_id: str = unique_id or device_id
        self._unsubscribe_auto_updater = None
        self._position_uncertain: bool = False

        # Slat-phase state
        self._is_fully_closed: bool = False      # slats compressed (≠ ajouré)
        self._slat_phase_running: bool = False   # motor running during slat phase
        self._slat_phase_cancelled: bool = False # set by stop_cover to abort slat task
        self._going_to_fully_closed: bool = False  # True ↔ close_cover / set_position(0)

        # Physical bypass detection — last action detected from relay state change
        self._last_physical_action: str | None = None      # "open" | "close" | "stop"
        self._last_physical_action_at: str | None = None   # ISO timestamp

        # Both directions: TravelCalculator uses the EFFECTIVE travel time only
        # (slat compression/decompression phases are excluded from position tracking)
        # → set_position(50 %) = truly 50 % of physical shutter travel in both directions
        #
        # DOWN: last slat_compression_time_down seconds = slat compression (end of stroke)
        # UP:   first slat_compression_time_up seconds = slat decompression (start of stroke)
        pure_travel_time_down = max(
            self._travel_time_down - self._slat_compression_time_down, 1
        )
        pure_travel_time_up = max(
            self._travel_time_up - self._slat_compression_time_up, 1
        )
        self._travel_calculator = TravelCalculator(
            pure_travel_time_down, pure_travel_time_up
        )

    async def async_added_to_hass(self) -> None:
        """Restore last known position."""
        old_state = await self.async_get_last_state()
        _LOGGER.debug("async_added_to_hass :: oldState %s", old_state)
        if (
            old_state is not None
            and self._travel_calculator is not None
            and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            self._travel_calculator.set_position(
                int(old_state.attributes.get(ATTR_CURRENT_POSITION))
            )
            was_moving = old_state.state in ("opening", "closing")
            self._position_uncertain = was_moving
            # Restore fully-closed state so slat decompression works after restart
            if old_state.attributes.get("is_fully_closed"):
                self._is_fully_closed = True
            if was_moving:
                _LOGGER.warning(
                    "%s: HA restarted while cover was moving. "
                    "Restored position %d%% may be inaccurate.",
                    self._name,
                    self._travel_calculator.current_position(),
                )

        # ---- Subscribe to physical switch state changes ----
        # Allows HA to track movements triggered directly on the relay/button,
        # without going through HA commands (bypass detection).
        if self._control_type == CONTROL_TYPE_SWITCH:
            entities_to_watch = [
                e for e in (
                    self._open_switch_entity_id,
                    self._close_switch_entity_id,
                    self._stop_switch_entity_id,
                )
                if e
            ]
            if entities_to_watch:
                self.async_on_remove(
                    async_track_state_change_event(
                        self.hass,
                        entities_to_watch,
                        self._async_switch_state_changed,
                    )
                )
                _LOGGER.debug(
                    "%s: subscribed to physical switch changes: %s",
                    self._name, entities_to_watch,
                )

        # ---- Subscribe to delegated cover state changes ----
        # In cover delegation mode, if the underlying cover is moved externally
        # (e.g. via its own remote or app), sync our position tracking.
        if self._control_type == CONTROL_TYPE_COVER and self._cover_entity_id:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._cover_entity_id],
                    self._async_delegated_cover_state_changed,
                )
            )
            _LOGGER.debug(
                "%s: subscribed to delegated cover state changes: %s",
                self._name, self._cover_entity_id,
            )

    @callback
    def _async_switch_state_changed(self, event) -> None:
        """React to a physical switch ON/OFF triggered directly on the relay.

        Called when the open or close switch changes state WITHOUT having been
        triggered by an HA command (e.g. user presses the wall button or the
        physical relay button directly).

        Strategy:
        - Switch → ON  : start travel in the matching direction, unless HA is
                         already tracking that exact direction (would be a
                         double-trigger from our own command).
        - Switch → OFF : in sustained (non-impulse) mode only, the motor has
                         physically stopped; freeze the tracked position.
                         Ignored in impulse mode (the brief ON→OFF is normal).
        """
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        new_val = new_state.state
        is_close_switch = entity_id == self._close_switch_entity_id
        is_open_switch  = entity_id == self._open_switch_entity_id
        is_stop_switch  = entity_id == self._stop_switch_entity_id

        already_going_down = (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_DOWN
        )
        already_going_up = (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_UP
        )

        if new_val == "on":
            # ---- Stop switch pressed physically ----
            if is_stop_switch:
                if self._travel_calculator.is_traveling():
                    _LOGGER.debug(
                        "%s: physical stop detected (stop switch %s ON) — freezing position",
                        self._name, entity_id,
                    )
                    self._last_physical_action = "stop"
                    self._last_physical_action_at = dt_util.utcnow().isoformat()
                    self._travel_calculator.stop()
                    self.stop_auto_updater()
                    self._going_to_fully_closed = False
                    self._slat_phase_cancelled = True
                    self._slat_phase_running = False
                    self.async_write_ha_state()
                return

            # Only react if HA is not already tracking this direction
            # (avoids double-trigger when HA itself turns on the switch)
            if is_close_switch and not already_going_down:
                _LOGGER.debug(
                    "%s: physical close detected (switch %s ON) — tracking travel down",
                    self._name, entity_id,
                )
                self._last_physical_action = "close"
                self._last_physical_action_at = dt_util.utcnow().isoformat()
                if self._travel_calculator.is_traveling():
                    self._travel_calculator.stop()
                    self.stop_auto_updater()
                self._position_uncertain = False
                self._going_to_fully_closed = self._slat_compression_time_down > 0
                self._is_fully_closed = False
                self._travel_calculator.start_travel_down()
                self.start_auto_updater()
                self.async_write_ha_state()

            elif is_open_switch and not already_going_up:
                _LOGGER.debug(
                    "%s: physical open detected (switch %s ON) — tracking travel up",
                    self._name, entity_id,
                )
                self._last_physical_action = "open"
                self._last_physical_action_at = dt_util.utcnow().isoformat()
                if self._travel_calculator.is_traveling():
                    self._travel_calculator.stop()
                    self.stop_auto_updater()
                self._position_uncertain = False
                self._going_to_fully_closed = False
                self._is_fully_closed = False
                self._travel_calculator.start_travel_up()
                self.start_auto_updater()
                self.async_write_ha_state()

        elif new_val == "off" and not self._impulse_mode:
            # Sustained mode only: switch OFF = motor physically stopped
            if self._travel_calculator.is_traveling() and (is_close_switch or is_open_switch):
                _LOGGER.debug(
                    "%s: physical stop detected (switch %s OFF) — freezing position",
                    self._name, entity_id,
                )
                self._last_physical_action = "stop"
                self._last_physical_action_at = dt_util.utcnow().isoformat()
                self._travel_calculator.stop()
                self.stop_auto_updater()
                self._going_to_fully_closed = False
                self._slat_phase_cancelled = True
                self._slat_phase_running = False
                self.async_write_ha_state()

    @callback
    def _async_delegated_cover_state_changed(self, event) -> None:
        """React to state changes of the delegated cover entity.

        Tracks external movements (wall button, remote, native app) when
        the underlying cover entity changes state without going through HA.

        Double-trigger prevention: if we are already tracking the same direction
        (our own command caused the state change), we skip.
        """
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None:
            return

        new_val = new_state.state
        old_val = old_state.state if old_state else None

        already_going_up = (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_UP
        )
        already_going_down = (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_DOWN
        )

        if new_val == "opening" and old_val != "opening":
            if already_going_up:
                return  # Our own command — skip
            _LOGGER.debug(
                "%s: delegated cover %s started opening externally — tracking up",
                self._name, self._cover_entity_id,
            )
            self._last_physical_action = "open"
            self._last_physical_action_at = dt_util.utcnow().isoformat()
            if self._travel_calculator.is_traveling():
                self._travel_calculator.stop()
                self.stop_auto_updater()
            self._position_uncertain = False
            self._going_to_fully_closed = False
            self._is_fully_closed = False
            self._travel_calculator.start_travel_up()
            self.start_auto_updater()
            self.async_write_ha_state()

        elif new_val == "closing" and old_val != "closing":
            if already_going_down:
                return  # Our own command — skip
            _LOGGER.debug(
                "%s: delegated cover %s started closing externally — tracking down",
                self._name, self._cover_entity_id,
            )
            self._last_physical_action = "close"
            self._last_physical_action_at = dt_util.utcnow().isoformat()
            if self._travel_calculator.is_traveling():
                self._travel_calculator.stop()
                self.stop_auto_updater()
            self._position_uncertain = False
            self._going_to_fully_closed = self._slat_compression_time_down > 0
            self._is_fully_closed = False
            self._travel_calculator.start_travel_down()
            self.start_auto_updater()
            self.async_write_ha_state()

        elif new_val not in ("opening", "closing") and old_val in ("opening", "closing"):
            # External stop: cover was moving but is no longer (idle, closed, open, unavailable…)
            if self._travel_calculator.is_traveling():
                _LOGGER.debug(
                    "%s: delegated cover %s stopped externally — freezing position",
                    self._name, self._cover_entity_id,
                )
                self._last_physical_action = "stop"
                self._last_physical_action_at = dt_util.utcnow().isoformat()
                self._travel_calculator.stop()
                self.stop_auto_updater()
                self._going_to_fully_closed = False
                self._slat_phase_cancelled = True
                self._slat_phase_running = False
                self.async_write_ha_state()

    def _handle_my_button(self) -> None:
        if self._travel_calculator.is_traveling():
            _LOGGER.debug("_handle_my_button :: button stops cover")
            self._travel_calculator.stop()
            self.stop_auto_updater()

    # ---- HA properties ----

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def device_class(self) -> str | None:
        return self._device_class_value

    @property
    def available(self) -> bool:
        """Return availability based on optional template."""
        if self._availability_template is None:
            return True
        try:
            self._availability_template.hass = self.hass
            result = self._availability_template.async_render(parse_result=False)
            available = str(result).lower() in ("true", "1", "yes", "on")
            self._availability_error_count = 0
            return available
        except Exception as err:  # noqa: BLE001
            self._availability_error_count += 1
            if self._availability_error_count <= 3:
                _LOGGER.warning(
                    "%s: availability_template error (#%d): %s",
                    self._name,
                    self._availability_error_count,
                    err,
                )
            else:
                _LOGGER.debug(
                    "%s: availability_template recurring error: %s", self._name, err
                )
            return False

    @property
    def extra_state_attributes(self) -> dict:
        pure_time_down = max(self._travel_time_down - self._slat_compression_time_down, 1)
        pure_time_up   = max(self._travel_time_up   - self._slat_compression_time_up,   1)
        return {
            CONF_TRAVELLING_TIME_DOWN: self._travel_time_down,
            CONF_TRAVELLING_TIME_UP: self._travel_time_up,
            CONF_SWITCH_SUSTAINED_TIME: self._switch_sustained_time,
            CONF_SEND_STOP_AT_END: self._send_stop_at_end,
            CONF_IMPULSE_MODE: self._impulse_mode,
            ATTR_CONTROL_TYPE: self._control_type,
            ATTR_POSITION_UNCERTAIN: self._position_uncertain,
            CONF_COMMAND_DELAY: self._command_delay,
            CONF_SLAT_COMPRESSION_TIME_DOWN: self._slat_compression_time_down,
            CONF_SLAT_COMPRESSION_TIME_UP: self._slat_compression_time_up,
            ATTR_AJOURE_POSITION: self.ajoure_position,
            "is_fully_closed": self._is_fully_closed,
            # --- Diagnostic / calibration attributes ---
            "pure_travel_time_down": pure_time_down,
            "pure_travel_time_up": pure_time_up,
            "slat_phase_running": self._slat_phase_running,
            "going_to_fully_closed": self._going_to_fully_closed,
            "tc_position": self._travel_calculator.current_position(),
            "tc_is_traveling": self._travel_calculator.is_traveling(),
            "tc_direction": self._travel_calculator.travel_direction,
            # --- Physical bypass audit ---
            "last_physical_action": self._last_physical_action,
            "last_physical_action_at": self._last_physical_action_at,
        }

    @property
    def current_cover_position(self) -> int:
        if self._is_fully_closed or self._slat_phase_running:
            return 0
        return self._travel_calculator.current_position()

    @property
    def is_opening(self) -> bool:
        # During slat decompression phase (opening from fully-closed)
        if self._slat_phase_running and not self._going_to_fully_closed:
            return True
        return (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_UP
        )

    @property
    def is_closing(self) -> bool:
        # During slat compression phase (going to fully-closed)
        if self._slat_phase_running and self._going_to_fully_closed:
            return True
        return (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_DOWN
        )

    @property
    def is_closed(self) -> bool:
        if self._is_fully_closed:
            return True
        # Without slat feature, TC position 0 % == fully closed
        if self._slat_compression_time_down <= 0:
            return self._travel_calculator.is_closed()
        # With slat feature: TC 0 % == ajouré (≠ fully closed)
        return False

    @property
    def assumed_state(self) -> bool:
        return True

    @property
    def ajoure_position(self) -> int | None:
        """Position (0-100 %) at which the ajouré state is reached.

        With slat_compression_time_down > 0, TravelCalculator is initialised with
        the *pure* travel time (travelling_time_down − slat_compression_time_down).
        Therefore TC position 0 % = ajouré physically.
        Returns None when slat_compression_time_down == 0 (feature disabled).
        Use the set_ajoure service to move to this position.
        """
        if self._slat_compression_time_down <= 0:
            return None
        return 0  # TC 0 % = ajouré (slats not compressed yet)

    # ---- Cover commands ----

    async def async_set_cover_position(self, **kwargs) -> None:
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug("async_set_cover_position: %d", position)
            await self._async_set_position(position)

    async def async_close_cover(self, **kwargs) -> None:
        _LOGGER.debug("async_close_cover")
        self._position_uncertain = False
        # close_cover always goes fully closed (slat compression phase included)
        self._going_to_fully_closed = self._slat_compression_time_down > 0
        await self._async_apply_command_delay("async_close_cover")
        self._travel_calculator.start_travel_down()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs) -> None:
        _LOGGER.debug("async_open_cover")
        self._position_uncertain = False
        self._going_to_fully_closed = False
        await self._async_apply_command_delay("async_open_cover")

        if self._is_fully_closed and self._slat_compression_time_up > 0:
            # --- Slat decompression phase ---
            self._is_fully_closed = False
            self._slat_phase_running = True
            self.async_write_ha_state()
            await self._async_handle_command(SERVICE_OPEN_COVER)
            await asyncio.sleep(self._slat_compression_time_up)
            if self._slat_phase_cancelled:
                self._slat_phase_running = False
                self._slat_phase_cancelled = False
                self.async_write_ha_state()
                return
            self._slat_phase_running = False
            # Motor already running — just start tracking upward travel
            self._travel_calculator.start_travel_up()
            self.start_auto_updater()
            self.async_write_ha_state()
        else:
            self._is_fully_closed = False
            self._travel_calculator.start_travel_up()
            self.start_auto_updater()
            await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_stop_cover(self, **kwargs) -> None:
        _LOGGER.debug("async_stop_cover")
        self._position_uncertain = False
        # Cancel any in-progress slat phase
        self._slat_phase_cancelled = True
        self._slat_phase_running = False
        self._going_to_fully_closed = False
        await self._async_apply_command_delay("async_stop_cover")
        self._handle_my_button()
        await self._async_handle_command(SERVICE_STOP_COVER)

    async def async_set_known_position(self, position: int) -> None:
        """Force the internal position without sending any command to the motor.

        Useful after RF desync, HA restart during movement, or manual calibration.
        Resets position_uncertain flag and updates is_fully_closed consistently.
        """
        _LOGGER.debug("async_set_known_position: %d", position)
        # Cancel any in-progress travel
        if self._travel_calculator.is_traveling():
            self._travel_calculator.stop()
        self.stop_auto_updater()
        self._slat_phase_cancelled = True
        self._slat_phase_running = False
        self._going_to_fully_closed = False
        # Force position
        self._travel_calculator.set_position(position)
        self._position_uncertain = False
        # Sync is_fully_closed: True only when pos==0 AND slat feature is active
        self._is_fully_closed = (position == 0 and self._slat_compression_time_down > 0)
        self.async_write_ha_state()

    async def async_set_ajoure(self) -> None:
        """Move the cover to the ajouré position.

        Ajouré = TC position 0 % (last slat on ground, slats NOT yet compressed).
        Requires slat_compression_time_down > 0 in the configuration.
        """
        if self._slat_compression_time_down <= 0:
            _LOGGER.warning(
                "%s: slat_compression_time_down not configured — "
                "cannot move to ajouré position. "
                "Set slat_compression_time_down > 0 in the integration options.",
                self._name,
            )
            return
        _LOGGER.debug("async_set_ajoure :: moving to ajouré (TC position 0%%)")
        # Do NOT set _going_to_fully_closed: stop exactly at ajouré
        self._going_to_fully_closed = False
        self._position_uncertain = False
        current_position = self._travel_calculator.current_position()
        if current_position == 0 and not self._is_fully_closed:
            return  # Already at ajouré
        await self._async_apply_command_delay("async_set_ajoure")
        self._is_fully_closed = False
        self.start_auto_updater()
        self._travel_calculator.start_travel(0)
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def _async_set_position(self, position: int) -> None:
        """Move the cover to the given position (0–100)."""
        _LOGGER.debug("_async_set_position")
        current_position = self._travel_calculator.current_position()
        _LOGGER.debug(
            "_async_set_position :: current: %d, target: %d", current_position, position
        )

        going_up = position > current_position or self._is_fully_closed
        going_down = position < current_position and not self._is_fully_closed

        if not going_up and not going_down:
            return

        self._position_uncertain = False

        if going_up:
            self._going_to_fully_closed = False
            if self._is_fully_closed and self._slat_compression_time_up > 0:
                # --- Slat decompression phase (opening from fully-closed) ---
                _LOGGER.debug(
                    "_async_set_position :: fully closed → decompressing slats (%ds) "
                    "before targeting %d%%",
                    self._slat_compression_time_up,
                    position,
                )
                self._is_fully_closed = False
                self._slat_phase_running = True
                self.async_write_ha_state()
                await self._async_apply_command_delay("_async_set_position")
                await self._async_handle_command(SERVICE_OPEN_COVER)
                await asyncio.sleep(self._slat_compression_time_up)
                if self._slat_phase_cancelled:
                    self._slat_phase_running = False
                    self._slat_phase_cancelled = False
                    self.async_write_ha_state()
                    return
                self._slat_phase_running = False
                # Motor already running — start tracking from position 0 % toward target
                self._travel_calculator.start_travel(position)
                self.start_auto_updater()
                self.async_write_ha_state()
            else:
                self._is_fully_closed = False
                await self._async_apply_command_delay("_async_set_position")
                self.start_auto_updater()
                self._travel_calculator.start_travel(position)
                _LOGGER.debug("_async_set_position :: command %s", SERVICE_OPEN_COVER)
                await self._async_handle_command(SERVICE_OPEN_COVER)
        else:
            # Going down
            # position == 0 with slat feature → go fully closed (slat compression phase)
            self._going_to_fully_closed = (position == 0 and self._slat_compression_time_down > 0)
            await self._async_apply_command_delay("_async_set_position")
            self.start_auto_updater()
            self._travel_calculator.start_travel(position)
            _LOGGER.debug("_async_set_position :: command %s", SERVICE_CLOSE_COVER)
            await self._async_handle_command(SERVICE_CLOSE_COVER)

    # ---- Command delay helper ----

    async def _async_apply_command_delay(self, caller: str = "") -> None:
        """Wait for the configured command delay (ms) before issuing a command."""
        if self._command_delay > 0:
            _LOGGER.debug(
                "%s :: waiting %d ms before sending command", caller, self._command_delay
            )
            await asyncio.sleep(self._command_delay / 1000)

    # ---- Auto updater ----

    def start_auto_updater(self) -> None:
        _LOGGER.debug("start_auto_updater")
        if self._unsubscribe_auto_updater is None:
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval
            )

    @callback
    def auto_updater_hook(self, now) -> None:
        self.async_schedule_update_ha_state()
        if self.position_reached():
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self) -> None:
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def position_reached(self) -> bool:
        return self._travel_calculator.position_reached()

    async def auto_stop_if_necessary(self) -> None:
        """Send stop command when target position is reached.

        - Intermediate positions (1–99 %): ALWAYS send stop (motor must halt).
        - End positions (0 % or 100 %):    send stop only if send_stop_at_end is True.
        - Position 0 % + going_to_fully_closed: run slat compression phase first.
        """
        if self.position_reached():
            self._travel_calculator.stop()
            current_position = self._travel_calculator.current_position()

            if (
                current_position == 0
                and self._going_to_fully_closed
                and self._slat_compression_time_down > 0
            ):
                # --- Slat compression phase ---
                _LOGGER.debug(
                    "auto_stop_if_necessary :: ajouré reached, compressing slats (%ds)",
                    self._slat_compression_time_down,
                )
                self._slat_phase_running = True
                self.async_write_ha_state()
                await asyncio.sleep(self._slat_compression_time_down)
                if not self._slat_phase_cancelled:
                    await self._async_handle_command(SERVICE_STOP_COVER)
                    self._is_fully_closed = True
                self._slat_phase_running = False
                self._slat_phase_cancelled = False
                self._going_to_fully_closed = False
                self.async_write_ha_state()

            elif 0 < current_position < 100:
                _LOGGER.debug(
                    "auto_stop_if_necessary :: intermediate position %d%%, sending stop",
                    current_position,
                )
                await self._async_handle_command(SERVICE_STOP_COVER)
            elif self._send_stop_at_end:
                _LOGGER.debug(
                    "auto_stop_if_necessary :: end position, send_stop_at_end=True, sending stop"
                )
                await self._async_handle_command(SERVICE_STOP_COVER)
            else:
                _LOGGER.debug(
                    "auto_stop_if_necessary :: end position, send_stop_at_end=False, skipping"
                )
                self.async_write_ha_state()

    # ---- Low-level switch helpers ----

    async def _async_turn_on_with_auto_return(self, entity_id: str) -> None:
        await self.hass.services.async_call(
            "homeassistant",
            "turn_on",
            service_data={"entity_id": entity_id},
            blocking=True,
        )
        if not self._impulse_mode and self._switch_sustained_time > 0:

            async def _turn_off_later() -> None:
                await asyncio.sleep(self._switch_sustained_time)
                await self.hass.services.async_call(
                    "homeassistant",
                    "turn_off",
                    service_data={"entity_id": entity_id},
                    blocking=True,
                )

            self.hass.async_create_task(_turn_off_later())

    async def _async_turn_off_switch(self, entity_id: str | None) -> None:
        if not entity_id:
            return
        if self._impulse_mode:
            _LOGGER.debug("impulse_mode: skipping turn_off on %s", entity_id)
            return
        await self.hass.services.async_call(
            "homeassistant",
            "turn_off",
            service_data={"entity_id": entity_id},
            blocking=True,
        )

    # ---- Command dispatcher ----

    async def _async_handle_command(self, command: str, *args) -> None:
        """Dispatch command to the appropriate backend (switch / script / cover)."""
        _LOGGER.debug("_async_handle_command :: %s via %s", command, self._control_type)

        if self._control_type == CONTROL_TYPE_COVER:
            await self._handle_command_cover(command)
        elif self._control_type == CONTROL_TYPE_SCRIPT:
            await self._handle_command_script(command)
        else:  # switch (default)
            await self._handle_command_switch(command)

        self.async_write_ha_state()

    async def _handle_command_switch(self, command: str) -> None:
        """Handle command using open/close/stop switches."""
        if command == SERVICE_CLOSE_COVER:
            await self._async_turn_off_switch(self._open_switch_entity_id)
            await self._async_turn_on_with_auto_return(self._close_switch_entity_id)
        elif command == SERVICE_OPEN_COVER:
            await self._async_turn_off_switch(self._close_switch_entity_id)
            await self._async_turn_on_with_auto_return(self._open_switch_entity_id)
        elif command == SERVICE_STOP_COVER:
            await self._async_turn_off_switch(self._close_switch_entity_id)
            await self._async_turn_off_switch(self._open_switch_entity_id)
            if self._stop_switch_entity_id:
                await self._async_turn_on_with_auto_return(self._stop_switch_entity_id)

    async def _handle_command_script(self, command: str) -> None:
        """Handle command by triggering a one-shot script (turn_on)."""
        script_map: dict[str, str | None] = {
            SERVICE_OPEN_COVER: self._open_script_entity_id,
            SERVICE_CLOSE_COVER: self._close_script_entity_id,
            SERVICE_STOP_COVER: self._stop_script_entity_id,
        }
        entity_id = script_map.get(command)
        if entity_id:
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                service_data={"entity_id": entity_id},
                blocking=True,
            )
        else:
            _LOGGER.debug(
                "_handle_command_script :: no script configured for %s", command
            )

    async def _handle_command_cover(self, command: str) -> None:
        """Delegate command to an existing cover entity."""
        if not self._cover_entity_id:
            _LOGGER.warning(
                "%s: cover_entity_id not configured for cover delegation mode",
                self._name,
            )
            return
        if command in (SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER, SERVICE_STOP_COVER):
            await self.hass.services.async_call(
                "cover",
                command,
                service_data={"entity_id": self._cover_entity_id},
                blocking=True,
            )
