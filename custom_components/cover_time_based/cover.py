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
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_CONTROL_TYPE,
    ATTR_POSITION_UNCERTAIN,
    CONF_ALIASES,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_BUTTON_AUTO_RETURN_TIME,
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
    CONF_STOP_SCRIPT_ENTITY_ID,
    CONF_STOP_SWITCH_ENTITY_ID,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    CONTROL_TYPE_COVER,
    CONTROL_TYPE_SCRIPT,
    CONTROL_TYPE_SWITCH,
    DEFAULT_BUTTON_AUTO_RETURN_TIME,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_CONTROL_TYPE,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_IMPULSE_MODE,
    DEFAULT_SEND_STOP_AT_END,
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
                        [CONTROL_TYPE_SWITCH, CONTROL_TYPE_SCRIPT, CONTROL_TYPE_COVER]
                    ),
                    # switch
                    vol.Optional(CONF_OPEN_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_CLOSE_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_STOP_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(
                        CONF_BUTTON_AUTO_RETURN_TIME,
                        default=DEFAULT_BUTTON_AUTO_RETURN_TIME,
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

        device = CoverTimeBased(
            device_id=device_id,
            name=name,
            control_type=control_type,
            travel_time_down=travel_time_down,
            travel_time_up=travel_time_up,
            open_switch_entity_id=config.pop(CONF_OPEN_SWITCH_ENTITY_ID, None),
            close_switch_entity_id=config.pop(CONF_CLOSE_SWITCH_ENTITY_ID, None),
            stop_switch_entity_id=config.pop(CONF_STOP_SWITCH_ENTITY_ID, None),
            button_auto_return_time=config.pop(
                CONF_BUTTON_AUTO_RETURN_TIME, DEFAULT_BUTTON_AUTO_RETURN_TIME
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
        button_auto_return_time=data.get(
            CONF_BUTTON_AUTO_RETURN_TIME, DEFAULT_BUTTON_AUTO_RETURN_TIME
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
        unique_id=config_entry.entry_id,
    )
    async_add_entities([device])


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
        button_auto_return_time: int = DEFAULT_BUTTON_AUTO_RETURN_TIME,
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
        unique_id: str | None = None,
    ) -> None:
        """Initialize the cover."""
        self._travel_time_down: int = max(int(travel_time_down), 1)
        self._travel_time_up: int = max(int(travel_time_up), 1)
        self._control_type: str = control_type

        # Switch mode
        self._open_switch_entity_id: str | None = open_switch_entity_id
        self._close_switch_entity_id: str | None = close_switch_entity_id
        self._stop_switch_entity_id: str | None = stop_switch_entity_id
        self._button_auto_return_time: int = button_auto_return_time
        self._impulse_mode: bool = impulse_mode

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
        self._availability_error_count: int = 0

        self._name: str = name if name else device_id
        self._unique_id: str = unique_id or device_id
        self._unsubscribe_auto_updater = None
        self._position_uncertain: bool = False

        self._travel_calculator = TravelCalculator(
            self._travel_time_down, self._travel_time_up
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
            if was_moving:
                _LOGGER.warning(
                    "%s: HA restarted while cover was moving. "
                    "Restored position %d%% may be inaccurate.",
                    self._name,
                    self._travel_calculator.current_position(),
                )

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
        return {
            CONF_TRAVELLING_TIME_DOWN: self._travel_time_down,
            CONF_TRAVELLING_TIME_UP: self._travel_time_up,
            CONF_BUTTON_AUTO_RETURN_TIME: self._button_auto_return_time,
            CONF_SEND_STOP_AT_END: self._send_stop_at_end,
            CONF_IMPULSE_MODE: self._impulse_mode,
            ATTR_CONTROL_TYPE: self._control_type,
            ATTR_POSITION_UNCERTAIN: self._position_uncertain,
            CONF_COMMAND_DELAY: self._command_delay,
        }

    @property
    def current_cover_position(self) -> int:
        return self._travel_calculator.current_position()

    @property
    def is_opening(self) -> bool:
        return (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_UP
        )

    @property
    def is_closing(self) -> bool:
        return (
            self._travel_calculator.is_traveling()
            and self._travel_calculator.travel_direction == TravelStatus.DIRECTION_DOWN
        )

    @property
    def is_closed(self) -> bool:
        return self._travel_calculator.is_closed()

    @property
    def assumed_state(self) -> bool:
        return True

    # ---- Cover commands ----

    async def async_set_cover_position(self, **kwargs) -> None:
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug("async_set_cover_position: %d", position)
            await self._async_set_position(position)

    async def async_close_cover(self, **kwargs) -> None:
        _LOGGER.debug("async_close_cover")
        self._position_uncertain = False
        await self._async_apply_command_delay("async_close_cover")
        self._travel_calculator.start_travel_down()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs) -> None:
        _LOGGER.debug("async_open_cover")
        self._position_uncertain = False
        await self._async_apply_command_delay("async_open_cover")
        self._travel_calculator.start_travel_up()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_stop_cover(self, **kwargs) -> None:
        _LOGGER.debug("async_stop_cover")
        self._position_uncertain = False
        await self._async_apply_command_delay("async_stop_cover")
        self._handle_my_button()
        await self._async_handle_command(SERVICE_STOP_COVER)

    async def _async_set_position(self, position: int) -> None:
        """Move the cover to the given position (0–100)."""
        _LOGGER.debug("_async_set_position")
        current_position = self._travel_calculator.current_position()
        _LOGGER.debug(
            "_async_set_position :: current: %d, target: %d", current_position, position
        )
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        else:
            return
        self._position_uncertain = False
        await self._async_apply_command_delay("_async_set_position")
        self.start_auto_updater()
        self._travel_calculator.start_travel(position)
        _LOGGER.debug("_async_set_position :: command %s", command)
        await self._async_handle_command(command)

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
        """
        if self.position_reached():
            self._travel_calculator.stop()
            current_position = self._travel_calculator.current_position()
            if 0 < current_position < 100:
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
        if not self._impulse_mode and self._button_auto_return_time > 0:

            async def _turn_off_later() -> None:
                await asyncio.sleep(self._button_auto_return_time)
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
