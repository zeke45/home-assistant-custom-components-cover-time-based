"""Config flow for Cover Time Based."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

DOMAIN = "cover_time_based"

CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"
CONF_OPEN_SWITCH_ENTITY_ID = "open_switch_entity_id"
CONF_CLOSE_SWITCH_ENTITY_ID = "close_switch_entity_id"
DEFAULT_TRAVEL_TIME = 25


class CoverTimeBasedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cover Time Based."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Avoid duplicate entries with the same name
            await self.async_set_unique_id(user_input[CONF_NAME].lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_OPEN_SWITCH_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Required(CONF_CLOSE_SWITCH_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME): int,
                vol.Optional(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return CoverTimeBasedOptionsFlow(config_entry)


class CoverTimeBasedOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Cover Time Based."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        data = self._config_entry.data

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_OPEN_SWITCH_ENTITY_ID,
                    default=data.get(CONF_OPEN_SWITCH_ENTITY_ID),
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
                vol.Required(
                    CONF_CLOSE_SWITCH_ENTITY_ID,
                    default=data.get(CONF_CLOSE_SWITCH_ENTITY_ID),
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
                vol.Optional(
                    CONF_TRAVELLING_TIME_DOWN,
                    default=data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
                ): int,
                vol.Optional(
                    CONF_TRAVELLING_TIME_UP,
                    default=data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

