"""Config flow for Cover Time Based."""
from __future__ import annotations

import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

DOMAIN = "cover_time_based"

CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"
CONF_OPEN_SWITCH_ENTITY_ID = "open_switch_entity_id"
CONF_CLOSE_SWITCH_ENTITY_ID = "close_switch_entity_id"
CONF_STOP_SWITCH_ENTITY_ID = "stop_switch_entity_id"
CONF_BUTTON_AUTO_RETURN_TIME = "button_auto_return_time"
CONF_SEND_STOP_AT_END = "send_stop_at_end"
CONF_IMPULSE_MODE = "impulse_mode"

DEFAULT_TRAVEL_TIME = 25
DEFAULT_BUTTON_AUTO_RETURN_TIME = 0
DEFAULT_SEND_STOP_AT_END = False
DEFAULT_IMPULSE_MODE = True


def _build_schema(data: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_OPEN_SWITCH_ENTITY_ID, default=data.get(CONF_OPEN_SWITCH_ENTITY_ID)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(CONF_CLOSE_SWITCH_ENTITY_ID, default=data.get(CONF_CLOSE_SWITCH_ENTITY_ID)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Optional(CONF_STOP_SWITCH_ENTITY_ID, default=data.get(CONF_STOP_SWITCH_ENTITY_ID, "")): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=600, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_TRAVELLING_TIME_UP, default=data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=600, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_BUTTON_AUTO_RETURN_TIME, default=data.get(CONF_BUTTON_AUTO_RETURN_TIME, DEFAULT_BUTTON_AUTO_RETURN_TIME)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_SEND_STOP_AT_END, default=data.get(CONF_SEND_STOP_AT_END, DEFAULT_SEND_STOP_AT_END)): selector.BooleanSelector(),
            vol.Optional(CONF_IMPULSE_MODE, default=data.get(CONF_IMPULSE_MODE, DEFAULT_IMPULSE_MODE)): selector.BooleanSelector(),
        }
    )


class CoverTimeBasedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cover Time Based."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate: travelling times must be >= 1
            if int(user_input.get(CONF_TRAVELLING_TIME_DOWN, 1)) < 1:
                errors[CONF_TRAVELLING_TIME_DOWN] = "travel_time_too_low"
            if int(user_input.get(CONF_TRAVELLING_TIME_UP, 1)) < 1:
                errors[CONF_TRAVELLING_TIME_UP] = "travel_time_too_low"

            if not errors:
                # Normalize: empty stop switch → None
                if not user_input.get(CONF_STOP_SWITCH_ENTITY_ID):
                    user_input[CONF_STOP_SWITCH_ENTITY_ID] = None
                # Coerce NumberSelector float → int
                for key in (CONF_TRAVELLING_TIME_DOWN, CONF_TRAVELLING_TIME_UP, CONF_BUTTON_AUTO_RETURN_TIME):
                    if key in user_input:
                        user_input[key] = int(user_input[key])

                # Use a UUID as unique_id to avoid collisions between covers with similar names
                unique_id = str(uuid.uuid4())
                await self.async_set_unique_id(unique_id)
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_NAME: user_input.pop(CONF_NAME)},
                    options=user_input,
                )

        schema = vol.Schema({vol.Required(CONF_NAME): selector.TextSelector()}).extend(
            _build_schema({}).schema
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return CoverTimeBasedOptionsFlow(config_entry)


class CoverTimeBasedOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Cover Time Based."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        # Use self.config_entry (HA >= 2024.x, no longer need __init__ storage)
        data = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            if int(user_input.get(CONF_TRAVELLING_TIME_DOWN, 1)) < 1:
                errors[CONF_TRAVELLING_TIME_DOWN] = "travel_time_too_low"
            if int(user_input.get(CONF_TRAVELLING_TIME_UP, 1)) < 1:
                errors[CONF_TRAVELLING_TIME_UP] = "travel_time_too_low"

            if not errors:
                if not user_input.get(CONF_STOP_SWITCH_ENTITY_ID):
                    user_input[CONF_STOP_SWITCH_ENTITY_ID] = None
                for key in (CONF_TRAVELLING_TIME_DOWN, CONF_TRAVELLING_TIME_UP, CONF_BUTTON_AUTO_RETURN_TIME):
                    if key in user_input:
                        user_input[key] = int(user_input[key])
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(data),
            errors=errors,
        )
