"""Config flow for Cover Time Based."""
from __future__ import annotations

import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_AVAILABILITY_TEMPLATE,
    CONF_SWITCH_SUSTAINED_TIME,
    CONF_CLOSE_SCRIPT_ENTITY_ID,
    CONF_CLOSE_SWITCH_ENTITY_ID,
    CONF_COMMAND_DELAY,
    CONF_CONTROL_TYPE,
    CONF_COVER_ENTITY_ID,
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
    COVER_DEVICE_CLASSES,
    DEFAULT_SWITCH_SUSTAINED_TIME,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_IMPULSE_MODE,
    DEFAULT_SEND_STOP_AT_END,
    DEFAULT_SLAT_COMPRESSION_TIME_DOWN,
    DEFAULT_SLAT_COMPRESSION_TIME_UP,
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
        vol.Optional(CONF_SLAT_COMPRESSION_TIME_DOWN, default=data.get(CONF_SLAT_COMPRESSION_TIME_DOWN, DEFAULT_SLAT_COMPRESSION_TIME_DOWN)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_SLAT_COMPRESSION_TIME_UP, default=data.get(CONF_SLAT_COMPRESSION_TIME_UP, DEFAULT_SLAT_COMPRESSION_TIME_UP)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX)),
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


def _build_control_type_schema(current: str) -> dict:
    """Return schema FIELDS (dict) for the control_type selector pre-filled with *current*.

    Returns a plain dict so callers can merge it with other fields using **unpacking,
    or wrap it directly in vol.Schema().
    """
    return {
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
    }


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


def _validate_timing(user_input: dict) -> dict:
    """Validate timing coherence: slat times must be < travel times.

    Returns a dict of field → error key (empty dict = no errors).
    """
    errors: dict[str, str] = {}
    time_down = int(user_input.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME))
    time_up   = int(user_input.get(CONF_TRAVELLING_TIME_UP,   DEFAULT_TRAVEL_TIME))
    slat_down = int(user_input.get(CONF_SLAT_COMPRESSION_TIME_DOWN, 0))
    slat_up   = int(user_input.get(CONF_SLAT_COMPRESSION_TIME_UP,   0))

    if time_down < 1:
        errors[CONF_TRAVELLING_TIME_DOWN] = "travel_time_too_low"
    if time_up < 1:
        errors[CONF_TRAVELLING_TIME_UP] = "travel_time_too_low"
    if slat_down > 0 and slat_down >= time_down:
        errors[CONF_SLAT_COMPRESSION_TIME_DOWN] = "slat_time_too_high"
    if slat_up > 0 and slat_up >= time_up:
        errors[CONF_SLAT_COMPRESSION_TIME_UP] = "slat_time_too_high"
    return errors


def _normalize(user_input: dict) -> dict:
    """Normalize user_input: empty strings → None, float → int for time fields."""
    for key in (CONF_STOP_SWITCH_ENTITY_ID, CONF_STOP_SCRIPT_ENTITY_ID,
                CONF_DEVICE_CLASS, CONF_AVAILABILITY_TEMPLATE):
        if not user_input.get(key):
            user_input[key] = None
    for key in (CONF_TRAVELLING_TIME_DOWN, CONF_TRAVELLING_TIME_UP,
                CONF_SWITCH_SUSTAINED_TIME, CONF_COMMAND_DELAY,
                CONF_SLAT_COMPRESSION_TIME_DOWN, CONF_SLAT_COMPRESSION_TIME_UP):
        if key in user_input:
            user_input[key] = int(user_input[key])
    return user_input


class CoverTimeBasedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cover Time Based (2-step)."""

    VERSION = 3

    def __init__(self):
        self._name: str = ""
        self._control_type: str = CONTROL_TYPE_SWITCH_IMPULSE

    async def async_step_import(self, import_data: dict):
        """Handle import from YAML configuration (idempotent).

        Called automatically by async_setup_platform for each YAML device.
        Aborts if a config entry with the same device_id (unique_id) already exists.
        """
        device_id = import_data.get("device_id", "")
        # Idempotency check: abort if already imported
        for entry in self._async_current_entries():
            if entry.unique_id == device_id:
                return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(device_id)

        name = import_data.get(CONF_NAME, device_id)
        # Build options from import_data (exclude internal keys)
        options = {
            k: v for k, v in import_data.items()
            if k not in ("device_id", CONF_NAME)
        }
        # Normalize legacy control_type=switch → switch_impulse / switch_sustained
        control_type = options.get(CONF_CONTROL_TYPE, CONTROL_TYPE_SWITCH_IMPULSE)
        if control_type == CONTROL_TYPE_SWITCH:
            impulse = options.get(CONF_IMPULSE_MODE, True)
            options[CONF_CONTROL_TYPE] = (
                CONTROL_TYPE_SWITCH_IMPULSE if impulse else CONTROL_TYPE_SWITCH_SUSTAINED
            )

        import logging as _log  # noqa: PLC0415
        _log.getLogger(__name__).info(
            "cover_time_based: importing YAML device '%s' as UI config entry", device_id
        )
        return self.async_create_entry(
            title=name,
            data={CONF_NAME: name},
            options=options,
        )

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._control_type = user_input[CONF_CONTROL_TYPE]
            return await self.async_step_control()

        schema = vol.Schema({
            vol.Required(CONF_NAME): selector.TextSelector(),
            **_build_control_type_schema(CONTROL_TYPE_SWITCH_IMPULSE),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_control(self, user_input=None):
        """Step 2: fields specific to the chosen control type."""
        errors = {}

        if user_input is not None:
            user_input = _normalize(user_input)
            errors = _validate_timing(user_input)
            if not errors:
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
            data_schema=vol.Schema(_build_control_type_schema(current_control_type)),
        )

    async def async_step_options(self, user_input=None):
        """Step 2 of options: fields specific to the chosen control type."""
        errors = {}
        data = {**self._config_entry.data, **self._config_entry.options}
        control_type = self._pending_control_type or data.get(CONF_CONTROL_TYPE, CONTROL_TYPE_SWITCH)

        if user_input is not None:
            user_input = _normalize(user_input)
            errors = _validate_timing(user_input)
            if not errors:
                user_input[CONF_CONTROL_TYPE] = control_type
                return self.async_create_entry(title="", data=user_input)

        schema = _get_control_schema(control_type, data)
        return self.async_show_form(step_id="options", data_schema=schema, errors=errors)
