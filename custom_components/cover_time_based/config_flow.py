"""Config flow for Cover Time Based."""
from __future__ import annotations

import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_AVAILABILITY_TEMPLATE,
    CONF_SWITCH_SUSTAINED_TIME,
    CONF_CLOSE_SCRIPT_ENTITY_ID,
    CONF_CLOSE_SWITCH_ENTITY_ID,
    CONF_COMMAND_DELAY,
    CONF_CONTROL_TYPE,
    CONF_COVER_ENTITY_ID,
    CONF_DEVICE_CLASS,
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
    CONTROL_TYPE_SWITCH_IMPULSE,
    CONTROL_TYPE_SWITCH_SUSTAINED,
    COVER_DEVICE_CLASSES,
    DEFAULT_SWITCH_SUSTAINED_TIME,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_IMPULSE_MODE,
    DEFAULT_SEND_STOP_AT_END,
    DEFAULT_TRAVEL_TIME,
    DOMAIN,
)

# Timing + common schema (shared between all control types)
def _build_common_schema(data: dict) -> dict:
    return {
        vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=600, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_TRAVELLING_TIME_UP, default=data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=600, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_SEND_STOP_AT_END, default=data.get(CONF_SEND_STOP_AT_END, DEFAULT_SEND_STOP_AT_END)):
            selector.BooleanSelector(),
        vol.Optional(CONF_COMMAND_DELAY, default=data.get(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10000, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_DEVICE_CLASS, default=data.get(CONF_DEVICE_CLASS, "")):
            selector.SelectSelector(selector.SelectSelectorConfig(
                options=[""] + COVER_DEVICE_CLASSES,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )),
        vol.Optional(CONF_AVAILABILITY_TEMPLATE, default=data.get(CONF_AVAILABILITY_TEMPLATE, "")):
            selector.TemplateSelector(),
    }


def _build_switch_impulse_schema(data: dict) -> vol.Schema:
    """Schema for switch_impulse: relay manages its own return to OFF (no impulse_mode field)."""
    return vol.Schema({
        vol.Required(CONF_OPEN_SWITCH_ENTITY_ID, default=data.get(CONF_OPEN_SWITCH_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Required(CONF_CLOSE_SWITCH_ENTITY_ID, default=data.get(CONF_CLOSE_SWITCH_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Optional(CONF_STOP_SWITCH_ENTITY_ID, default=data.get(CONF_STOP_SWITCH_ENTITY_ID, "")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        **_build_common_schema(data),
    })


def _build_switch_sustained_schema(data: dict) -> vol.Schema:
    """Schema for switch_sustained: HA manages the return to OFF (with auto-return time)."""
    return vol.Schema({
        vol.Required(CONF_OPEN_SWITCH_ENTITY_ID, default=data.get(CONF_OPEN_SWITCH_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Required(CONF_CLOSE_SWITCH_ENTITY_ID, default=data.get(CONF_CLOSE_SWITCH_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Optional(CONF_STOP_SWITCH_ENTITY_ID, default=data.get(CONF_STOP_SWITCH_ENTITY_ID, "")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Optional(CONF_SWITCH_SUSTAINED_TIME, default=data.get(CONF_SWITCH_SUSTAINED_TIME, DEFAULT_SWITCH_SUSTAINED_TIME)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX)),
        **_build_common_schema(data),
    })


def _build_switch_schema(data: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_OPEN_SWITCH_ENTITY_ID, default=data.get(CONF_OPEN_SWITCH_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Required(CONF_CLOSE_SWITCH_ENTITY_ID, default=data.get(CONF_CLOSE_SWITCH_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Optional(CONF_STOP_SWITCH_ENTITY_ID, default=data.get(CONF_STOP_SWITCH_ENTITY_ID, "")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Optional(CONF_IMPULSE_MODE, default=data.get(CONF_IMPULSE_MODE, DEFAULT_IMPULSE_MODE)):
            selector.BooleanSelector(),
        vol.Optional(CONF_SWITCH_SUSTAINED_TIME, default=data.get(CONF_SWITCH_SUSTAINED_TIME, DEFAULT_SWITCH_SUSTAINED_TIME)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX)),
        **_build_common_schema(data),
    })


def _build_script_schema(data: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_OPEN_SCRIPT_ENTITY_ID, default=data.get(CONF_OPEN_SCRIPT_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),
        vol.Required(CONF_CLOSE_SCRIPT_ENTITY_ID, default=data.get(CONF_CLOSE_SCRIPT_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),
        vol.Optional(CONF_STOP_SCRIPT_ENTITY_ID, default=data.get(CONF_STOP_SCRIPT_ENTITY_ID, "")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="script")),
        **_build_common_schema(data),
    })


def _build_cover_schema(data: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_COVER_ENTITY_ID, default=data.get(CONF_COVER_ENTITY_ID)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="cover")),
        **_build_common_schema(data),
    })


def _build_control_type_schema(current: str) -> vol.Schema:
    """Return a schema with a control_type selector pre-filled with *current*."""
    return vol.Schema({
        vol.Required(CONF_CONTROL_TYPE, default=current):
            selector.SelectSelector(selector.SelectSelectorConfig(
                options=[
                    {"value": CONTROL_TYPE_SWITCH_IMPULSE,   "label": "Switch — impulsion (relay gère son retour à OFF)"},
                    {"value": CONTROL_TYPE_SWITCH_SUSTAINED, "label": "Switch — maintenu (HA gère le retour à OFF)"},
                    {"value": CONTROL_TYPE_SCRIPT,           "label": "Script (impulsion RF / one-shot)"},
                    {"value": CONTROL_TYPE_COVER,            "label": "Cover (délégation vers un cover existant)"},
                ],
                mode=selector.SelectSelectorMode.LIST,
                translation_key="control_type",
            )),
    })


def _get_control_schema(control_type: str, data: dict) -> vol.Schema:
    """Return the schema matching *control_type*."""
    if control_type == CONTROL_TYPE_SWITCH_IMPULSE:
        return _build_switch_impulse_schema(data)
    if control_type == CONTROL_TYPE_SWITCH_SUSTAINED:
        return _build_switch_sustained_schema(data)
    if control_type == CONTROL_TYPE_SCRIPT:
        return _build_script_schema(data)
    if control_type == CONTROL_TYPE_COVER:
        return _build_cover_schema(data)
    # Fallback: legacy switch (YAML entries with control_type=switch)
    return _build_switch_schema(data)


def _normalize(user_input: dict) -> dict:
    """Normalize user_input: empty strings → None, float → int for time fields."""
    for key in (CONF_STOP_SWITCH_ENTITY_ID, CONF_STOP_SCRIPT_ENTITY_ID,
                CONF_DEVICE_CLASS, CONF_AVAILABILITY_TEMPLATE):
        if not user_input.get(key):
            user_input[key] = None
    for key in (CONF_TRAVELLING_TIME_DOWN, CONF_TRAVELLING_TIME_UP,
                CONF_SWITCH_SUSTAINED_TIME, CONF_COMMAND_DELAY):
        if key in user_input:
            user_input[key] = int(user_input[key])
    return user_input


class CoverTimeBasedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cover Time Based (2-step)."""

    VERSION = 3

    def __init__(self):
        self._name: str = ""
        self._control_type: str = CONTROL_TYPE_SWITCH_IMPULSE

    async def async_step_user(self, user_input=None):
        """Step 1: name + control type."""
        errors = {}
        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._control_type = user_input[CONF_CONTROL_TYPE]
            return await self.async_step_control()

        schema = vol.Schema({
            vol.Required(CONF_NAME): selector.TextSelector(),
            **_build_control_type_schema(CONTROL_TYPE_SWITCH),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_control(self, user_input=None):
        """Step 2: fields specific to the chosen control type."""
        errors = {}

        if user_input is not None:
            user_input = _normalize(user_input)
            user_input[CONF_CONTROL_TYPE] = self._control_type

            unique_id = str(uuid.uuid4())
            await self.async_set_unique_id(unique_id)
            return self.async_create_entry(
                title=self._name,
                data={CONF_NAME: self._name},
                options=user_input,
            )

        schema = _get_control_schema(self._control_type, {})
        return self.async_show_form(step_id="control", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return CoverTimeBasedOptionsFlow(config_entry)


class CoverTimeBasedOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Cover Time Based."""

    def __init__(self, config_entry) -> None:
        self._pending_control_type: str | None = None
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Step 1 of options: allow changing the control type."""
        data = {**self._config_entry.data, **self._config_entry.options}
        current_control_type = data.get(CONF_CONTROL_TYPE, CONTROL_TYPE_SWITCH)

        if user_input is not None:
            self._pending_control_type = user_input[CONF_CONTROL_TYPE]
            return await self.async_step_options()

        return self.async_show_form(
            step_id="init",
            data_schema=_build_control_type_schema(current_control_type),
        )

    async def async_step_options(self, user_input=None):
        """Step 2 of options: fields specific to the chosen control type."""
        errors = {}
        data = {**self._config_entry.data, **self._config_entry.options}
        control_type = self._pending_control_type or data.get(CONF_CONTROL_TYPE, CONTROL_TYPE_SWITCH)

        if user_input is not None:
            user_input = _normalize(user_input)
            user_input[CONF_CONTROL_TYPE] = control_type
            return self.async_create_entry(title="", data=user_input)

        schema = _get_control_schema(control_type, data)
        return self.async_show_form(step_id="options", data_schema=schema, errors=errors)
