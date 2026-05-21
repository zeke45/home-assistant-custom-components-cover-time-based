"""Cover Time Based integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "cover_time_based"
PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Cover Time Based component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cover Time Based from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the entry so new values take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries between versions."""
    _LOGGER.debug(
        "Migrating config entry %s from version %s", entry.entry_id, entry.version
    )

    current_version = entry.version

    if current_version == 1:
        # V1 → V2 : données stockées dans data{} ; on les déplace dans options{}
        new_options = dict(entry.options)
        for key, value in entry.data.items():
            if key not in new_options:
                new_options[key] = value
        hass.config_entries.async_update_entry(
            entry, data={k: v for k, v in entry.data.items() if k == "name"},
            options=new_options, version=2
        )
        _LOGGER.info("Migrated config entry %s to version 2", entry.entry_id)

    return True
