"""Config flow for Cover Time Based."""
from __future__ import annotations

import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

DOMAIN = "cover_time_based"

# Keys
CONF_CONTROL_TYPE            = "control_type"
CONF_TRAVELLING_TIME_DOWN    = "travelling_time_down"
CONF_TRAVELLING_TIME_UP      = "travelling_time_up"
CONF_OPEN_SWITCH_ENTITY_ID   = "open_switch_entity_id"
CONF_CLOSE_SWITCH_ENTITY_ID  = "close_switch_entity_id"
CONF_STOP_SWITCH_ENTITY_ID   = "stop_switch_entity_id"
CONF_BUTTON_AUTO_RETURN_TIME = "button_auto_return_time"
CONF_SEND_STOP_AT_END        = "send_stop_at_end"
CONF_IMPULSE_MODE            = "impulse_mode"
CONF_OPEN_SCRIPT_ENTITY_ID   = "open_script_entity_id"
CONF_CLOSE_SCRIPT_ENTITY_ID  = "close_script_entity_id"
CONF_STOP_SCRIPT_ENTITY_ID   = "stop_script_entity_id"
CONF_COVER_ENTITY_ID         = "cover_entity_id"
CONF_DEVICE_CLASS            = "device_class"
CONF_AVAILABILITY_TEMPLATE   = "availability_template"

CONTROL_TYPE_SWITCH = "switch"
CONTROL_TYPE_SCRIPT = "script"
CONTROL_TYPE_COVER  = "cover"

DEFAULT_TRAVEL_TIME          = 25
DEFAULT_BUTTON_AUTO_RETURN_TIME = 0
DEFAULT_SEND_STOP_AT_END     = False
DEFAULT_IMPULSE_MODE         = True

COVER_DEVICE_CLASSES = [
    "awning", "blind", "curtain", "damper", "door",
    "garage", "gate", "shade", "shutter", "window",
]

# Timing + common schema (shared between all control types)
def _build_common_schema(data: dict) -> dict:
    return {
        vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=600, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_TRAVELLING_TIME_UP, default=data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=600, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_SEND_STOP_AT_END, default=data.get(CONF_SEND_STOP_AT_END, DEFAULT_SEND_STOP_AT_END)):
            selector.BooleanSelector(),
        vol.Optional(CONF_DEVICE_CLASS, default=data.get(CONF_DEVICE_CLASS, "")):
            selector.SelectSelector(selector.SelectSelectorConfig(
                options=[""] + COVER_DEVICE_CLASSES,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )),
        vol.Optional(CONF_AVAILABILITY_TEMPLATE, default=data.get(CONF_AVAILABILITY_TEMPLATE, "")):
            selector.TemplateSelector(),
    }


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
        vol.Optional(CONF_BUTTON_AUTO_RETURN_TIME, default=data.get(CONF_BUTTON_AUTO_RETURN_TIME, DEFAULT_BUTTON_AUTO_RETURN_TIME)):
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


def _normalize(user_input: dict) -> dict:
    """Normalize user_input: empty strings → None, float → int for time fields."""
    for key in (CONF_STOP_SWITCH_ENTITY_ID, CONF_STOP_SCRIPT_ENTITY_ID,
                CONF_DEVICE_CLASS, CONF_AVAILABILITY_TEMPLATE):
        if not user_input.get(key):
            user_input[key] = None
    for key in (CONF_TRAVELLING_TIME_DOWN, CONF_TRAVELLING_TIME_UP, CONF_BUTTON_AUTO_RETURN_TIME):
        if key in user_input:
            user_input[key] = int(user_input[key])
    return user_input


class CoverTimeBasedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cover Time Based (2-step)."""

    VERSION = 2

    def __init__(self):
        self._name: str = ""
        self._control_type: str = CONTROL_TYPE_SWITCH

    async def async_step_user(self, user_input=None):
        """Step 1: name + control type."""
        errors = {}
        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._control_type = user_input[CONF_CONTROL_TYPE]
            return await self.async_step_control()

        schema = vol.Schema({
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_CONTROL_TYPE, default=CONTROL_TYPE_SWITCH):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=[
                        {"value": CONTROL_TYPE_SWITCH, "label": "Switch (relais ON/OFF)"},
                        {"value": CONTROL_TYPE_SCRIPT, "label": "Script (impulsion RF / one-shot)"},
                        {"value": CONTROL_TYPE_COVER,  "label": "Cover (délégation vers un cover existant)"},
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="control_type",
                )),
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

        schema = self._get_control_schema({})
        return self.async_show_form(step_id="control", data_schema=schema, errors=errors)

    def _get_control_schema(self, data: dict) -> vol.Schema:
        if self._control_type == CONTROL_TYPE_SCRIPT:
            return _build_script_schema(data)
        if self._control_type == CONTROL_TYPE_COVER:
            return _build_cover_schema(data)
        return _build_switch_schema(data)

    @staticmethod
    def async_get_options_flow(config_entry):
        return CoverTimeBasedOptionsFlow(config_entry)


class CoverTimeBasedOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Cover Time Based."""

    async def async_step_init(self, user_input=None):
        """Manage the options (single step, all fields visible)."""
        errors = {}
        data = {**self.config_entry.data, **self.config_entry.options}
        control_type = data.get(CONF_CONTROL_TYPE, CONTROL_TYPE_SWITCH)

        if user_input is not None:
            user_input = _normalize(user_input)
            user_input[CONF_CONTROL_TYPE] = control_type
            return self.async_create_entry(title="", data=user_input)

        # Build schema based on current control type
        if control_type == CONTROL_TYPE_SCRIPT:
            schema = _build_script_schema(data)
        elif control_type == CONTROL_TYPE_COVER:
            schema = _build_cover_schema(data)
        else:
            schema = _build_switch_schema(data)

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
