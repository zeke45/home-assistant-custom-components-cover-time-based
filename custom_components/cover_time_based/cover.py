"""Cover Time Based."""
import logging
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    PLATFORM_SCHEMA,
    CoverEntity,
)
from homeassistant.const import (
    CONF_NAME,
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

CONF_OPEN_SWITCH_ENTITY_ID = 'open_switch_entity_id'
CONF_CLOSE_SWITCH_ENTITY_ID = 'close_switch_entity_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): vol.Schema(
            {
                cv.string: {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_OPEN_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_CLOSE_SWITCH_ENTITY_ID): cv.string,
                    vol.Optional(CONF_ALIASES, default=[]):
                        vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME):
                        cv.positive_int,
                    vol.Optional(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME):
                        cv.positive_int,
                }
            }
        ),
    }
)


# ---------------------------------------------------------------------------
# Minimal TravelCalculator – replaces xknx dependency
# ---------------------------------------------------------------------------

class TravelStatus:
    DIRECTION_UP = "up"
    DIRECTION_DOWN = "down"
    DIRECTION_NONE = "none"


class TravelCalculator:
    """Time-based travel position calculator (no external dependency)."""

    def __init__(self, travel_time_down: int, travel_time_up: int) -> None:
        self._travel_time_down = travel_time_down
        self._travel_time_up = travel_time_up
        self._position: int = 100  # 0=closed, 100=open (HA convention)
        self._target_position: int = 100
        self._travel_started_at: datetime | None = None
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
        elapsed = (datetime.utcnow() - self._travel_started_at).total_seconds()
        if self._travel_direction == TravelStatus.DIRECTION_UP:
            diff = 100.0 * elapsed / self._travel_time_up
            pos = min(self._position + diff, 100.0)
        else:
            diff = 100.0 * elapsed / self._travel_time_down
            pos = max(self._position - diff, 0.0)
        return int(round(pos))

    def start_travel(self, target_position: int) -> None:
        self._position = self.current_position()
        self._target_position = target_position
        self._travel_started_at = datetime.utcnow()
        if target_position > self._position:
            self._travel_direction = TravelStatus.DIRECTION_UP
        else:
            self._travel_direction = TravelStatus.DIRECTION_DOWN

    def start_travel_up(self) -> None:
        self.start_travel(100)

    def start_travel_down(self) -> None:
        self.start_travel(0)

    def stop(self) -> None:
        self._position = self.current_position()
        self._target_position = self._position
        self._travel_started_at = None
        self._travel_direction = TravelStatus.DIRECTION_NONE

    def is_traveling(self) -> bool:
        return self._travel_started_at is not None and not self.position_reached()

    def position_reached(self) -> bool:
        if self._travel_started_at is None:
            return True
        current = self.current_position()
        if self._travel_direction == TravelStatus.DIRECTION_UP:
            return current >= self._target_position
        return current <= self._target_position

    def is_closed(self) -> bool:
        return self.current_position() == 0


# ---------------------------------------------------------------------------

def devices_from_config(domain_config):
    """Parse configuration and add cover devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        name = config.pop(CONF_NAME, device_id)
        travel_time_down = config.pop(CONF_TRAVELLING_TIME_DOWN)
        travel_time_up = config.pop(CONF_TRAVELLING_TIME_UP)
        open_switch_entity_id = config.pop(CONF_OPEN_SWITCH_ENTITY_ID)
        close_switch_entity_id = config.pop(CONF_CLOSE_SWITCH_ENTITY_ID)
        device = CoverTimeBased(
            device_id=device_id,
            name=name,
            travel_time_down=travel_time_down,
            travel_time_up=travel_time_up,
            open_switch_entity_id=open_switch_entity_id,
            close_switch_entity_id=close_switch_entity_id,
            unique_id=device_id,
        )
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the cover platform (legacy YAML)."""
    async_add_entities(devices_from_config(config))


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Cover Time Based from a config entry (UI)."""
    data = {**config_entry.data, **config_entry.options}
    device = CoverTimeBased(
        device_id=config_entry.unique_id or config_entry.entry_id,
        name=data[CONF_NAME],
        travel_time_down=data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
        travel_time_up=data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
        open_switch_entity_id=data[CONF_OPEN_SWITCH_ENTITY_ID],
        close_switch_entity_id=data[CONF_CLOSE_SWITCH_ENTITY_ID],
        unique_id=config_entry.unique_id or config_entry.entry_id,
    )
    async_add_entities([device])


class CoverTimeBased(CoverEntity, RestoreEntity):

    def __init__(self, device_id, name, travel_time_down, travel_time_up,
                 open_switch_entity_id, close_switch_entity_id, unique_id=None):
        """Initialize the cover."""
        self._travel_time_down = travel_time_down
        self._travel_time_up = travel_time_up
        self._open_switch_entity_id = open_switch_entity_id
        self._close_switch_entity_id = close_switch_entity_id
        self._name = name if name else device_id
        self._unique_id = unique_id or device_id
        self._unsubscribe_auto_updater = None
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

    def _handle_my_button(self):
        """Handle the MY button press."""
        if self.tc.is_traveling():
            _LOGGER.debug('_handle_my_button :: button stops cover')
            self.tc.stop()
            self.stop_auto_updater()

    @property
    def unique_id(self):
        """Return a unique ID for this cover."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        if self._travel_time_down is not None:
            attr[CONF_TRAVELLING_TIME_DOWN] = self._travel_time_down
        if self._travel_time_up is not None:
            attr[CONF_TRAVELLING_TIME_UP] = self._travel_time_up
        return attr

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.tc.current_position()

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self.tc.is_traveling() and \
               self.tc.travel_direction == TravelStatus.DIRECTION_UP

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self.tc.is_traveling() and \
               self.tc.travel_direction == TravelStatus.DIRECTION_DOWN

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.tc.is_closed()

    @property
    def assumed_state(self):
        """Return True because covers can be stopped midway."""
        return True

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug('async_set_cover_position: %d', position)
            await self.set_position(position)

    async def async_close_cover(self, **kwargs):
        """Turn the device close."""
        _LOGGER.debug('async_close_cover')
        self.tc.start_travel_down()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs):
        """Turn the device open."""
        _LOGGER.debug('async_open_cover')
        self.tc.start_travel_up()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_stop_cover(self, **kwargs):
        """Turn the device stop."""
        _LOGGER.debug('async_stop_cover')
        self._handle_my_button()
        await self._async_handle_command(SERVICE_STOP_COVER)

    async def set_position(self, position):
        """Move cover to a designated position."""
        _LOGGER.debug('set_position')
        current_position = self.tc.current_position()
        _LOGGER.debug('set_position :: current_position: %d, new_position: %d',
                      current_position, position)
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        if command is not None:
            self.start_auto_updater()
            self.tc.start_travel(position)
            _LOGGER.debug('set_position :: command %s', command)
            await self._async_handle_command(command)

    def start_auto_updater(self):
        """Start the autoupdater to update HASS while cover is moving."""
        _LOGGER.debug('start_auto_updater')
        if self._unsubscribe_auto_updater is None:
            _LOGGER.debug('init _unsubscribe_auto_updater')
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval)

    @callback
    def auto_updater_hook(self, now):
        """Call for the autoupdater."""
        _LOGGER.debug('auto_updater_hook')
        self.async_schedule_update_ha_state()
        if self.position_reached():
            _LOGGER.debug('auto_updater_hook :: position_reached')
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self):
        """Stop the autoupdater."""
        _LOGGER.debug('stop_auto_updater')
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def position_reached(self):
        """Return if cover has reached its final position."""
        return self.tc.position_reached()

    async def auto_stop_if_necessary(self):
        """Do auto stop if necessary."""
        if self.position_reached():
            _LOGGER.debug('auto_stop_if_necessary :: calling stop command')
            await self._async_handle_command(SERVICE_STOP_COVER)
            self.tc.stop()

    async def _async_handle_command(self, command, *args):
        if command == SERVICE_CLOSE_COVER:
            cmd = "DOWN"
            self._state = False
            await self.hass.services.async_call(
                "homeassistant", "turn_off",
                service_data={"entity_id": self._open_switch_entity_id},
                blocking=True,
            )
            await self.hass.services.async_call(
                "homeassistant", "turn_on",
                service_data={"entity_id": self._close_switch_entity_id},
                blocking=True,
            )
        elif command == SERVICE_OPEN_COVER:
            cmd = "UP"
            self._state = True
            await self.hass.services.async_call(
                "homeassistant", "turn_off",
                service_data={"entity_id": self._close_switch_entity_id},
                blocking=True,
            )
            await self.hass.services.async_call(
                "homeassistant", "turn_on",
                service_data={"entity_id": self._open_switch_entity_id},
                blocking=True,
            )
        elif command == SERVICE_STOP_COVER:
            cmd = "STOP"
            self._state = True
            await self.hass.services.async_call(
                "homeassistant", "turn_off",
                service_data={"entity_id": self._close_switch_entity_id},
                blocking=True,
            )
            await self.hass.services.async_call(
                "homeassistant", "turn_off",
                service_data={"entity_id": self._open_switch_entity_id},
                blocking=True,
            )
        else:
            cmd = "UNKNOWN"

        _LOGGER.debug('_async_handle_command :: %s', cmd)

        # Update state of entity
        self.async_write_ha_state()
