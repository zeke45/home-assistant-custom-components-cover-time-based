"""Constants for Cover Time Based."""

DOMAIN = "cover_time_based"

# Configuration keys
CONF_DEVICES = "devices"
CONF_ALIASES = "aliases"
CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"

# Control type
CONF_CONTROL_TYPE = "control_type"
CONTROL_TYPE_SWITCH = "switch"            # legacy YAML (switch + impulse_mode flag)
CONTROL_TYPE_SWITCH_IMPULSE = "switch_impulse"    # switch, relay gère son retour à OFF
CONTROL_TYPE_SWITCH_SUSTAINED = "switch_sustained"  # switch, HA gère le retour à OFF
CONTROL_TYPE_SCRIPT = "script"
CONTROL_TYPE_COVER = "cover"
DEFAULT_CONTROL_TYPE = CONTROL_TYPE_SWITCH_IMPULSE

# Switch mode
CONF_OPEN_SWITCH_ENTITY_ID = "open_switch_entity_id"
CONF_CLOSE_SWITCH_ENTITY_ID = "close_switch_entity_id"
CONF_STOP_SWITCH_ENTITY_ID = "stop_switch_entity_id"
CONF_SWITCH_SUSTAINED_TIME = "switch_sustained_time"
CONF_IMPULSE_MODE = "impulse_mode"

# Script mode
CONF_OPEN_SCRIPT_ENTITY_ID = "open_script_entity_id"
CONF_CLOSE_SCRIPT_ENTITY_ID = "close_script_entity_id"
CONF_STOP_SCRIPT_ENTITY_ID = "stop_script_entity_id"

# Cover delegation mode
CONF_COVER_ENTITY_ID = "cover_entity_id"

# Common options
CONF_SEND_STOP_AT_END = "send_stop_at_end"
CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_COMMAND_DELAY = "command_delay"

# Attributes exposed in extra_state_attributes
ATTR_POSITION_UNCERTAIN = "position_uncertain"
ATTR_CONTROL_TYPE = "control_type"

# Default values
DEFAULT_TRAVEL_TIME = 25
DEFAULT_SWITCH_SUSTAINED_TIME = 0
DEFAULT_SEND_STOP_AT_END = False
DEFAULT_IMPULSE_MODE = True
DEFAULT_DEVICE_CLASS = None
DEFAULT_COMMAND_DELAY = 0  # ms

# Cover device classes available in the UI
COVER_DEVICE_CLASSES = [
    "awning", "blind", "curtain", "damper", "door",
    "garage", "gate", "shade", "shutter", "window",
]

