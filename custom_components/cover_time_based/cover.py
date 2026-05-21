"""Cover Time Based."""
import logging
import asyncio
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import template as template_helper
from homeassistant.util import dt as dt_util
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    PLATFORM_SCHEMA,
    CoverEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE_CLASS,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

CONF_DEVICES = 'devices'
CONF_NAME = 'name'
CONF_ALIASES = 'aliases'
CONF_TRAVELLING_TIME_DOWN = 'travelling_time_down'
CONF_TRAVELLING_TIME_UP = 'travelling_time_up'
DEFAULT_TRAVEL_TIME = 25

# Control type
CONF_CONTROL_TYPE = 'control_type'
CONTROL_TYPE_SWITCH = 'switch'
CONTROL_TYPE_SCRIPT = 'script'
CONTROL_TYPE_COVER  = 'cover'
DEFAULT_CONTROL_TYPE = CONTROL_TYPE_SWITCH

# Switch mode
CONF_OPEN_SWITCH_ENTITY_ID  = 'open_switch_entity_id'
CONF_CLOSE_SWITCH_ENTITY_ID = 'close_switch_entity_id'
CONF_STOP_SWITCH_ENTITY_ID  = 'stop_switch_entity_id'
CONF_BUTTON_AUTO_RETURN_TIME = 'button_auto_return_time'
CONF_IMPULSE_MODE            = 'impulse_mode'

# Script mode
CONF_OPEN_SCRIPT_ENTITY_ID  = 'open_script_entity_id'
CONF_CLOSE_SCRIPT_ENTITY_ID = 'close_script_entity_id'
CONF_STOP_SCRIPT_ENTITY_ID  = 'stop_script_entity_id'

# Cover delegation mode
CONF_COVER_ENTITY_ID = 'cover_entity_id'

# Common options
CONF_SEND_STOP_AT_END      = 'send_stop_at_end'
CONF_AVAILABILITY_TEMPLATE = 'availability_template'

# Attributes
ATTR_POSITION_UNCERTAIN = 'position_uncertain'
ATTR_CONTROL_TYPE       = 'control_type'

DEFAULT_BUTTON_AUTO_RETURN_TIME = 0
DEFAULT_SEND_STOP_AT_END = False
DEFAULT_IMPULSE_MODE = True
DEFAULT_DEVICE_CLASS = None

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): vol.Schema(
            {
                cv.string: {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_CONTROL_TYPE, default=DEFAULT_CONTROL_TYPE): vol.In([CONTROL_TYPE_SWITCH, CONTROL_TYPE_SCRIPT, CONTROL_TYPE_COVER]),
                    # switch
                    vol.Optional(CONF_OPEN_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_CLOSE_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_STOP_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_BUTTON_AUTO_RETURN_TIME, default=DEFAULT_BUTTON_AUTO_RETURN_TIME):
                        vol.All(vol.Coerce(int), vol.Range(min=0)),
                    vol.Optional(CONF_IMPULSE_MODE, default=DEFAULT_IMPULSE_MODE): cv.boolean,
                    # script
                    vol.Optional(CONF_OPEN_SCRIPT_ENTITY_ID): cv.string,
                    vol.Optional(CONF_CLOSE_SCRIPT_ENTITY_ID): cv.string,
                    vol.Optional(CONF_STOP_SCRIPT_ENTITY_ID): cv.string,
                    # cover delegation
                    vol.Optional(CONF_COVER_ENTITY_ID): cv.string,
                    # common
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
                    vol.Optional(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
                    vol.Optional(CONF_SEND_STOP_AT_END, default=DEFAULT_SEND_STOP_AT_END): cv.boolean,
                    vol.Optional(CONF_DEVICE_CLASS): cv.string,
                    vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
                }
            }
        ),
    }
)


# ---------------------------------------------------------------------------
# TravelCalculator
# ---------------------------------------------------------------------------

class TravelStatus:
    DIRECTION_UP   = "up"
    DIRECTION_DOWN = "down"
    DIRECTION_NONE = "none"


class TravelCalculator:
    """Time-based travel position calculator (no external dependency)."""

    def __init__(self, travel_time_down: int, travel_time_up: int) -> None:
        self._travel_time_down = max(travel_time_down, 1)
        self._travel_time_up   = max(travel_time_up, 1)
        self._position: int = 100
        self._target_position: int = 100
        self._travel_started_at = None
        self._travel_direction: str = TravelStatus.DIRECTION_NONE

    @property
    def travel_direction(self) -> str:
        return self._travel_direction

    def set_position(self, position: int) -> None:
        self._position = position
        self._target_position = position

    def current_position(self) -> int:
        if self._travel_started_at is None:
            return self._position
        elapsed = (dt_util.utcnow() - self._travel_started_at).total_seconds()
        if self._travel_direction == TravelStatus.DIRECTION_UP:
            diff = 100.0 * elapsed / self._travel_time_up
            pos  = min(self._position + diff, 100.0)
        else:
            diff = 100.0 * elapsed / self._travel_time_down
            pos  = max(self._position - diff, 0.0)
        return int(round(pos))

    def start_travel(self, target_position: int) -> None:
        self._position = self.current_position()
        self._target_position = target_position
        self._travel_started_at = dt_util.utcnow()
        if target_position > self._position:
            self._travel_direction = TravelStatus.DIRECTION_UP
        else:
            self._travel_direction = TravelStatus.DIRECTION_DOWN

    def start_travel_up(self)   -> None: self.start_travel(100)
    def start_travel_down(self) -> None: self.start_travel(0)

    def stop(self) -> None:
        self._position = self.current_position()
        self._target_position = self._position
        self._travel_started_at = None
        self._travel_direction = TravelStatus.DIRECTION_NONE

    def position_reached(self) -> bool:
        if self._travel_started_at is None:
            return True
        current = self.current_position()
        if self._travel_direction == TravelStatus.DIRECTION_UP:
            return current >= self._target_position
        return current <= self._target_position

    def is_traveling(self) -> bool:
        return self._travel_started_at is not None and not self.position_reached()

    def is_closed(self) -> bool:
        return self.current_position() == 0


# ---------------------------------------------------------------------------

def devices_from_config(domain_config):
    """Parse configuration and add cover devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        name         = config.pop(CONF_NAME, device_id)
        control_type = config.pop(CONF_CONTROL_TYPE, DEFAULT_CONTROL_TYPE)
        travel_time_down = config.pop(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)
        travel_time_up   = config.pop(CONF_TRAVELLING_TIME_UP,   DEFAULT_TRAVEL_TIME)
        send_stop_at_end = config.pop(CONF_SEND_STOP_AT_END, DEFAULT_SEND_STOP_AT_END)
        device_class          = config.pop(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS)
        availability_template = config.pop(CONF_AVAILABILITY_TEMPLATE, None)

        device = CoverTimeBased(
            device_id=device_id,
            name=name,
            control_type=control_type,
            travel_time_down=travel_time_down,
            travel_time_up=travel_time_up,
            open_switch_entity_id=config.pop(CONF_OPEN_SWITCH_ENTITY_ID, None),
            close_switch_entity_id=config.pop(CONF_CLOSE_SWITCH_ENTITY_ID, None),
            stop_switch_entity_id=config.pop(CONF_STOP_SWITCH_ENTITY_ID, None),
            button_auto_return_time=config.pop(CONF_BUTTON_AUTO_RETURN_TIME, DEFAULT_BUTTON_AUTO_RETURN_TIME),
            impulse_mode=config.pop(CONF_IMPULSE_MODE, DEFAULT_IMPULSE_MODE),
            open_script_entity_id=config.pop(CONF_OPEN_SCRIPT_ENTITY_ID, None),
            close_script_entity_id=config.pop(CONF_CLOSE_SCRIPT_ENTITY_ID, None),
            stop_script_entity_id=config.pop(CONF_STOP_SCRIPT_ENTITY_ID, None),
            cover_entity_id=config.pop(CONF_COVER_ENTITY_ID, None),
            send_stop_at_end=send_stop_at_end,
            device_class=device_class,
            availability_template=availability_template,
            unique_id=device_id,
        )
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the cover platform (legacy YAML)."""
    async_add_entities(devices_from_config(config))


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Cover Time Based from a config entry (UI)."""
    data = dict(config_entry.data)
    data.update(config_entry.options)

    name = config_entry.title or data.get(CONF_NAME, config_entry.entry_id)

    # Parse availability template string → HA template object
    avail_tpl_str = data.get(CONF_AVAILABILITY_TEMPLATE)
    avail_tpl = None
    if avail_tpl_str:
        avail_tpl = template_helper.Template(avail_tpl_str, hass)

    device = CoverTimeBased(
        device_id=config_entry.entry_id,
        name=name,
        control_type=data.get(CONF_CONTROL_TYPE, DEFAULT_CONTROL_TYPE),
        travel_time_down=data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
        travel_time_up=data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
        open_switch_entity_id=data.get(CONF_OPEN_SWITCH_ENTITY_ID, ""),
        close_switch_entity_id=data.get(CONF_CLOSE_SWITCH_ENTITY_ID, ""),
        stop_switch_entity_id=data.get(CONF_STOP_SWITCH_ENTITY_ID),
        button_auto_return_time=data.get(CONF_BUTTON_AUTO_RETURN_TIME, DEFAULT_BUTTON_AUTO_RETURN_TIME),
        impulse_mode=data.get(CONF_IMPULSE_MODE, DEFAULT_IMPULSE_MODE),
        open_script_entity_id=data.get(CONF_OPEN_SCRIPT_ENTITY_ID),
        close_script_entity_id=data.get(CONF_CLOSE_SCRIPT_ENTITY_ID),
        stop_script_entity_id=data.get(CONF_STOP_SCRIPT_ENTITY_ID),
        cover_entity_id=data.get(CONF_COVER_ENTITY_ID),
        send_stop_at_end=data.get(CONF_SEND_STOP_AT_END, DEFAULT_SEND_STOP_AT_END),
        device_class=data.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
        availability_template=avail_tpl,
        unique_id=config_entry.entry_id,
    )
    async_add_entities([device])


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class CoverTimeBased(CoverEntity, RestoreEntity):

    def __init__(self,
                 device_id,
                 name,
                 travel_time_down,
                 travel_time_up,
                 # switch mode
                 open_switch_entity_id=None,
                 close_switch_entity_id=None,
                 stop_switch_entity_id=None,
                 button_auto_return_time=DEFAULT_BUTTON_AUTO_RETURN_TIME,
                 impulse_mode=DEFAULT_IMPULSE_MODE,
                 # script mode
                 open_script_entity_id=None,
                 close_script_entity_id=None,
                 stop_script_entity_id=None,
                 # cover delegation
                 cover_entity_id=None,
                 # common
                 control_type=DEFAULT_CONTROL_TYPE,
                 send_stop_at_end=DEFAULT_SEND_STOP_AT_END,
                 device_class=DEFAULT_DEVICE_CLASS,
                 availability_template=None,
                 unique_id=None):
        """Initialize the cover."""
        self._travel_time_down = max(int(travel_time_down), 1)
        self._travel_time_up   = max(int(travel_time_up), 1)
        self._control_type     = control_type

        # Switch mode
        self._open_switch_entity_id  = open_switch_entity_id
        self._close_switch_entity_id = close_switch_entity_id
        self._stop_switch_entity_id  = stop_switch_entity_id
        self._button_auto_return_time = button_auto_return_time
        self._impulse_mode            = impulse_mode

        # Script mode
        self._open_script_entity_id  = open_script_entity_id
        self._close_script_entity_id = close_script_entity_id
        self._stop_script_entity_id  = stop_script_entity_id

        # Cover delegation
        self._cover_entity_id = cover_entity_id

        # Common
        self._send_stop_at_end      = send_stop_at_end
        self._device_class_value    = device_class
        self._availability_template = availability_template

        self._name      = name if name else device_id
        self._unique_id = unique_id or device_id
        self._unsubscribe_auto_updater = None
        self._position_uncertain = False

        self.tc = TravelCalculator(self._travel_time_down, self._travel_time_up)

    async def async_added_to_hass(self):
        """Restore last known position."""
        old_state = await self.async_get_last_state()
        _LOGGER.debug('async_added_to_hass :: oldState %s', old_state)
        if (
            old_state is not None
            and self.tc is not None
            and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            self.tc.set_position(int(old_state.attributes.get(ATTR_CURRENT_POSITION)))
            was_moving = old_state.state in ("opening", "closing")
            self._position_uncertain = was_moving
            if was_moving:
                _LOGGER.warning(
                    "%s: HA restarted while cover was moving. "
                    "Restored position %d%% may be inaccurate.",
                    self._name, self.tc.current_position(),
                )

    def _handle_my_button(self):
        if self.tc.is_traveling():
            _LOGGER.debug('_handle_my_button :: button stops cover')
            self.tc.stop()
            self.stop_auto_updater()

    # ---- HA properties ----

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        return self._name

    @property
    def device_class(self):
        """Return the device class of the cover (configurable)."""
        return self._device_class_value

    @property
    def available(self) -> bool:
        """Return availability based on optional template."""
        if self._availability_template is None:
            return True
        try:
            self._availability_template.hass = self.hass
            result = self._availability_template.async_render(parse_result=False)
            return str(result).lower() in ("true", "1", "yes", "on")
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("%s: availability_template error: %s", self._name, err)
            return True

    @property
    def extra_state_attributes(self):
        attr = {
            CONF_TRAVELLING_TIME_DOWN: self._travel_time_down,
            CONF_TRAVELLING_TIME_UP:   self._travel_time_up,
            CONF_BUTTON_AUTO_RETURN_TIME: self._button_auto_return_time,
            CONF_SEND_STOP_AT_END:  self._send_stop_at_end,
            CONF_IMPULSE_MODE:      self._impulse_mode,
            ATTR_CONTROL_TYPE:      self._control_type,
            ATTR_POSITION_UNCERTAIN: self._position_uncertain,
        }
        return attr

    @property
    def current_cover_position(self):
        return self.tc.current_position()

    @property
    def is_opening(self):
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_UP

    @property
    def is_closing(self):
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_DOWN

    @property
    def is_closed(self):
        return self.tc.is_closed()

    @property
    def assumed_state(self):
        return True

    # ---- Cover commands ----

    async def async_set_cover_position(self, **kwargs):
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug('async_set_cover_position: %d', position)
            await self.set_position(position)

    async def async_close_cover(self, **kwargs):
        _LOGGER.debug('async_close_cover')
        self._position_uncertain = False
        self.tc.start_travel_down()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs):
        _LOGGER.debug('async_open_cover')
        self._position_uncertain = False
        self.tc.start_travel_up()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_stop_cover(self, **kwargs):
        _LOGGER.debug('async_stop_cover')
        self._position_uncertain = False
        self._handle_my_button()
        await self._async_handle_command(SERVICE_STOP_COVER)

    async def set_position(self, position):
        _LOGGER.debug('set_position')
        current_position = self.tc.current_position()
        _LOGGER.debug('set_position :: current: %d, target: %d', current_position, position)
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        if command is not None:
            self._position_uncertain = False
            self.start_auto_updater()
            self.tc.start_travel(position)
            _LOGGER.debug('set_position :: command %s', command)
            await self._async_handle_command(command)

    # ---- Auto updater ----

    def start_auto_updater(self):
        _LOGGER.debug('start_auto_updater')
        if self._unsubscribe_auto_updater is None:
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval)

    @callback
    def auto_updater_hook(self, now):
        self.async_schedule_update_ha_state()
        if self.position_reached():
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self):
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def position_reached(self):
        return self.tc.position_reached()

    async def auto_stop_if_necessary(self):
        """Send stop when target position reached.

        - Intermediate positions (1–99 %): ALWAYS send stop (motor must be stopped).
        - End positions (0 % or 100 %):    send stop only if send_stop_at_end is True.
        """
        if self.position_reached():
            self.tc.stop()
            current_position = self.tc.current_position()
            if 0 < current_position < 100:
                # Intermediate: unconditional stop so the motor halts
                _LOGGER.debug('auto_stop_if_necessary :: intermediate position %d%%, sending stop', current_position)
                await self._async_handle_command(SERVICE_STOP_COVER)
            elif self._send_stop_at_end:
                _LOGGER.debug('auto_stop_if_necessary :: end position, send_stop_at_end=True, sending stop')
                await self._async_handle_command(SERVICE_STOP_COVER)
            else:
                _LOGGER.debug('auto_stop_if_necessary :: end position, send_stop_at_end=False, skipping')
                self.async_write_ha_state()

    # ---- Low-level switch helpers ----

    async def _async_turn_on_with_auto_return(self, entity_id: str) -> None:
        await self.hass.services.async_call(
            "homeassistant", "turn_on",
            service_data={"entity_id": entity_id},
            blocking=True,
        )
        if not self._impulse_mode and self._button_auto_return_time > 0:
            async def _turn_off_later():
                await asyncio.sleep(self._button_auto_return_time)
                await self.hass.services.async_call(
                    "homeassistant", "turn_off",
                    service_data={"entity_id": entity_id},
                    blocking=True,
                )
            self.hass.async_create_task(_turn_off_later())

    async def _async_turn_off_switch(self, entity_id: str) -> None:
        if not entity_id:
            return
        if self._impulse_mode:
            _LOGGER.debug('impulse_mode: skipping turn_off on %s', entity_id)
            return
        await self.hass.services.async_call(
            "homeassistant", "turn_off",
            service_data={"entity_id": entity_id},
            blocking=True,
        )

    # ---- Command dispatcher ----

    async def _async_handle_command(self, command, *args):
        """Dispatch command to the appropriate backend (switch / script / cover)."""
        _LOGGER.debug('_async_handle_command :: %s via %s', command, self._control_type)

        if self._control_type == CONTROL_TYPE_COVER:
            await self._handle_command_cover(command)

        elif self._control_type == CONTROL_TYPE_SCRIPT:
            await self._handle_command_script(command)

        else:  # switch (default)
            await self._handle_command_switch(command)

        self.async_write_ha_state()

    async def _handle_command_switch(self, command):
        """Handle command using open/close/stop switches."""
        if command == SERVICE_CLOSE_COVER:
            self._state = False
            await self._async_turn_off_switch(self._open_switch_entity_id)
            await self._async_turn_on_with_auto_return(self._close_switch_entity_id)

        elif command == SERVICE_OPEN_COVER:
            self._state = True
            await self._async_turn_off_switch(self._close_switch_entity_id)
            await self._async_turn_on_with_auto_return(self._open_switch_entity_id)

        elif command == SERVICE_STOP_COVER:
            self._state = True
            await self._async_turn_off_switch(self._close_switch_entity_id)
            await self._async_turn_off_switch(self._open_switch_entity_id)
            if self._stop_switch_entity_id:
                await self._async_turn_on_with_auto_return(self._stop_switch_entity_id)

    async def _handle_command_script(self, command):
        """Handle command by triggering a one-shot script (turn_on)."""
        script_map = {
            SERVICE_OPEN_COVER:  self._open_script_entity_id,
            SERVICE_CLOSE_COVER: self._close_script_entity_id,
            SERVICE_STOP_COVER:  self._stop_script_entity_id,
        }
        entity_id = script_map.get(command)
        if entity_id:
            await self.hass.services.async_call(
                "homeassistant", "turn_on",
                service_data={"entity_id": entity_id},
                blocking=True,
            )
        else:
            _LOGGER.debug('_handle_command_script :: no script configured for %s', command)

    async def _handle_command_cover(self, command):
        """Delegate command to an existing cover entity."""
        if not self._cover_entity_id:
            _LOGGER.warning('%s: cover_entity_id not configured for cover delegation mode', self._name)
            return
        service_map = {
            SERVICE_OPEN_COVER:  SERVICE_OPEN_COVER,
            SERVICE_CLOSE_COVER: SERVICE_CLOSE_COVER,
            SERVICE_STOP_COVER:  SERVICE_STOP_COVER,
        }
        service = service_map.get(command)
        if service:
            await self.hass.services.async_call(
                "cover", service,
                service_data={"entity_id": self._cover_entity_id},
                blocking=True,
            )
