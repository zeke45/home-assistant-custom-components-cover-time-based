# Cover Time Based Component

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-2.6.4-blue)
![maintained](https://img.shields.io/badge/maintained-yes-green)
![license](https://img.shields.io/badge/license-MIT-green)

Home Assistant custom component to manage motorized covers using **time-based position calculation**.
Supports ON/OFF relays (switch), RF impulse scripts, and delegation to an existing HA cover entity.

> 🇫🇷 French documentation available in [README.md](README.md)

---

## ✨ Features

- 🎛️ **4 control modes**: switch impulse, switch sustained, script (RF one-shot), cover (delegation)
- ⚡ **Switch impulse**: relay manages its own return to OFF — no `impulse_mode` needed in UI
- ⏱️ **Switch sustained**: HA manages return to OFF with configurable software pulse duration
- 🛑 **Dedicated stop switch** (optional)
- 📍 **Precise positioning** (1–100%) by time-based calculation
- ⛔ **Unconditional stop** at intermediate positions (1–99%)
- 🏷️ **Configurable device class** (shutter, blind, curtain, garage…)
- 🔌 **Availability template** (e.g. Zigbee gateway online) with robust error handling
- 💾 **Position restore** on HA restart
- ⚠️ **Uncertain position detection** if HA restarts during movement
- 🖥️ **Full UI configuration** (no YAML required)
- 🔄 **Automatic reload** on every options change
- ⏳ **Command delay** (ms) to stagger simultaneous commands
- 🔀 **Control type change** from UI options without recreating the integration
- 🪟 **Ajouré position** for fixed-slat shutters: `cover_time_based.set_ajoure` service + automatic `ajoure_position` attribute
- 🔁 **Physical bypass detection** (switch mode): if the relay is triggered directly (wall button, remote), HA automatically tracks position

---

## 📦 Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zeke45&repository=home-assistant-custom-components-cover-time-based&category=integration)

1. Click the badge above **or** go to HACS → Integrations → ⋮ → Custom repositories
2. Add URL: `https://github.com/zeke45/home-assistant-custom-components-cover-time-based`
3. Category: **Integration**
4. Install **Cover Time Based**
5. Restart Home Assistant

### Manually

1. Copy `custom_components/cover_time_based/` into `<config>/custom_components/`
2. Restart Home Assistant

---

## 🖥️ UI Configuration (recommended)

[![Open your Home Assistant instance and add an integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cover_time_based)

1. **Settings → Devices & Services → Add Integration** → search **Cover Time Based**
2. **Step 1**: Name + control type (`switch`, `script` or `cover`)
3. **Step 2**: Entities and options (travel times, delay, device class, availability template…)

### Edit an existing integration

From **Settings → Devices & Services → Cover Time Based → Configure**:

1. **Step 1**: Choose the control type (can be changed on the fly)
2. **Step 2**: Update entities and options

---

## 📝 YAML Configuration (legacy)

### Switch mode (ON/OFF relay)

```yaml
cover:
  - platform: cover_time_based
    devices:
      living_room_cover:
        name: Living Room Cover
        control_type: switch
        open_switch_entity_id: switch.cover_open
        close_switch_entity_id: switch.cover_close
        stop_switch_entity_id: switch.cover_stop
        travelling_time_down: 27
        travelling_time_up: 31
        impulse_mode: true
        send_stop_at_end: false
        device_class: shutter
        availability_template: >-
          {% set t = states('sensor.my_device_last_seen') %}
          {{ t not in ['unavailable','unknown',''] and
             (now() - t | as_datetime).total_seconds() < 300 }}
```

### Script mode (RF / one-shot impulse)

```yaml
cover:
  - platform: cover_time_based
    devices:
      rf_cover:
        name: RF Cover
        control_type: script
        open_script_entity_id: script.cover_open
        close_script_entity_id: script.cover_close
        stop_script_entity_id: script.cover_stop
        travelling_time_down: 25
        travelling_time_up: 25
        send_stop_at_end: false
```

### Cover delegation mode

```yaml
cover:
  - platform: cover_time_based
    devices:
      delegated_cover:
        name: Delegated Cover
        control_type: cover
        cover_entity_id: cover.existing_cover
        travelling_time_down: 25
        travelling_time_up: 25
```

### Simultaneous commands — staggering with `command_delay`

When multiple covers are triggered simultaneously (e.g. "Open all" scene), the radio bus (Zigbee, Z-Wave, RF…) may be overloaded and drop some commands. `command_delay` staggers each cover's start **without affecting position calculation** (TravelCalculator starts exactly when the physical command is sent).

```yaml
cover:
  - platform: cover_time_based
    devices:
      cover_living:
        command_delay: 0       # starts immediately
        travelling_time_down: 25
        travelling_time_up: 25
      cover_kitchen:
        command_delay: 300     # starts 300 ms later
        travelling_time_down: 25
        travelling_time_up: 25
      cover_bedroom:
        command_delay: 600     # starts 600 ms later
        travelling_time_down: 25
        travelling_time_up: 25
```

> ℹ️ Delay applies to **open**, **close**, **stop** and **set_position** commands.  
> Value is in **milliseconds** (0–10 000). Default: `0`.

---

## ⚙️ Available options

| Option | Type | Default | Description |
|---|---|---|---|
| `control_type` | `switch_impulse`\|`switch_sustained`\|`script`\|`cover` | `switch_impulse` | Control mode |
| `open_switch_entity_id` | entity | — | Open switch |
| `close_switch_entity_id` | entity | — | Close switch |
| `stop_switch_entity_id` | entity | `null` | Dedicated stop switch (optional) |
| `open_script_entity_id` | entity | — | Open script (script mode) |
| `close_script_entity_id` | entity | — | Close script (script mode) |
| `stop_script_entity_id` | entity | `null` | Stop script (optional) |
| `cover_entity_id` | entity | — | Cover to delegate to (cover mode) |
| `travelling_time_down` | int | `25` | Travel time down (seconds) |
| `travelling_time_up` | int | `25` | Travel time up (seconds) |
| `switch_sustained_time` | int | `0` | Activation duration in seconds (`switch_sustained` mode, 0 = full travel) |
| `send_stop_at_end` | bool | `false` | Send stop at end positions 0% and 100% |
| `device_class` | string | `null` | shutter, blind, curtain, garage… |
| `availability_template` | template | `null` | Availability template |
| `command_delay` | int | `0` | Delay before sending command (ms, 0–10000) |
| `slat_compression_time_down` | int | `0` | Slat compression duration at bottom of downward stroke (seconds). Enables ajouré position. |
| `slat_compression_time_up` | int | `0` | Slat decompression duration at start of upward stroke (seconds). Usually ≥ `slat_compression_time_down`. |

---

## 🔁 Physical bypass detection

In **switch** mode (impulse or sustained), the component monitors the state of open and close relays. If you trigger the relay directly without going through HA (wall button, RF remote, physical test), HA detects the change and **tracks position automatically**.

| Physical event | Impulse mode | Sustained mode |
|---|---|---|
| Close relay → ON | Downward travel tracking started ↓ | Downward travel tracking started ↓ |
| Open relay → ON | Upward travel tracking started ↑ | Upward travel tracking started ↑ |
| Stop relay → ON | Position frozen immediately | Position frozen immediately |
| Relay → OFF | Ignored (brief pulse) | Position frozen (motor stopped) |

> ℹ️ **Script and cover modes**: automatic detection is not possible as these modes have no observable "motor running" state in HA. You can manually resync the position via `cover.set_cover_position`.

---

## 🔧 Available services

| Service | Description |
|---|---|
| `cover.open_cover` | Opens the cover |
| `cover.close_cover` | Closes the cover |
| `cover.stop_cover` | Stops the cover |
| `cover.set_cover_position` | Sets cover to X% (e.g. 50%) |
| `cover_time_based.set_known_position` | Forces internal position without moving the cover (re-sync). Field: `position` (0–100%). |
| `cover_time_based.set_ajoure` | Moves cover to ajouré position (last slat on ground, light passes through). Requires `slat_compression_time_down > 0`. |

---

## 🪟 Fixed-slat shutters (ajouré)

Some roller shutters with fixed slats allow two states at the bottom of travel:

- **Ajouré**: last slat rests on the ground, slats not yet compressed → light still passes through
- **Fully closed**: motor continues for a few seconds, slats overlap and block light

### Position calculation

The component automatically excludes slat phases from position calculation so that **50% truly means 50%** of physical shutter travel:

| Direction | Slat phase | Moment | Duration excluded |
|---|---|---|---|
| ⬇️ Down | Compression | **End** of stroke | `slat_compression_time_down` |
| ⬆️ Up | Decompression | **Start** of stroke | `slat_compression_time_up` |

> **Example**: `travelling_time_down = 25s`, `slat_compression_time_down = 3s`  
> → Effective time = 22s  
> → `set_cover_position(50%)` = 11s actual travel → **exactly 50% physical** ✓

### Configuration

```yaml
cover:
  - platform: cover_time_based
    devices:
      living_room_cover:
        travelling_time_down: 25   # TOTAL time (includes slat compression)
        travelling_time_up: 26     # TOTAL time (includes slat decompression)
        slat_compression_time_down: 3   # 3s compression at end of downward stroke
        slat_compression_time_up: 4     # 4s decompression at start of upward stroke
```

### Calibration

1. **`slat_compression_time_down`**: close fully (`close_cover`), then open slightly (`set_cover_position: 1`). Measure the time between the last slat touching the ground and the motor stopping.
2. **`slat_compression_time_up`**: from closed state, trigger opening and measure the time before the shutter physically starts rising.

### Usage

**Via service:**
```yaml
service: cover_time_based.set_ajoure
target:
  entity_id: cover.living_room_cover
```

**Via automation using the attribute:**
```yaml
service: cover.set_cover_position
target:
  entity_id: cover.living_room_cover
data:
  position: "{{ state_attr('cover.living_room_cover', 'ajoure_position') }}"
```

**Via dashboard button:**
```yaml
type: button
name: Ajouré
tap_action:
  action: perform-action
  perform_action: cover_time_based.set_ajoure
  target:
    entity_id: cover.living_room_cover
```

---

## 🗂️ Code architecture

| File | Role |
|---|---|
| `const.py` | All shared constants (single source of truth) |
| `travel_calculator.py` | Time-based position calculation (`TravelCalculator`) — no HA dependency |
| `cover.py` | `CoverTimeBased` entity — HA logic |
| `config_flow.py` | UI configuration and options flow |
| `__init__.py` | Setup, unload, version migration |
| `tests/` | Pytest unit tests (`TravelCalculator` + config flow validation) |

---

## 📊 State attributes

In addition to standard HA attributes (`current_position`, `is_opening`, etc.), the entity exposes:

### Main attributes

| Attribute | Type | Description |
|---|---|---|
| `current_position` | int | Current position (0–100%) |
| `is_fully_closed` | bool | `true` when the cover is fully closed (slats compressed) |
| `ajoure_position` | int | HA position value corresponding to the ajouré state (auto-calculated) |

### Diagnostic / calibration attributes

| Attribute | Type | Description |
|---|---|---|
| `pure_travel_time_down` | int | Effective downward travel time (excluding slat phase), in seconds |
| `pure_travel_time_up` | int | Effective upward travel time (excluding slat phase), in seconds |
| `slat_phase_running` | bool | `true` if the slat compression/decompression phase is running |
| `going_to_fully_closed` | bool | `true` if a full close command (including slats) is in progress |
| `tc_position` | int | Internal `TravelCalculator` position (0–100, before ajouré correction) |
| `tc_is_traveling` | bool | `true` if the `TravelCalculator` considers the cover as moving |
| `tc_direction` | str | Internal direction: `"up"`, `"down"` or `None` |

### Physical action audit attributes

| Attribute | Type | Description |
|---|---|---|
| `last_physical_action` | str | Last detected physical action: `"open"`, `"close"` or `"stop"` |
| `last_physical_action_at` | str | ISO timestamp of the last physical action (e.g. `2024-01-15T14:32:05.123456+00:00`) |

> ℹ️ `last_physical_action` / `last_physical_action_at` are only populated in **switch** mode (impulse or sustained), when the relay is triggered directly without going through HA.

---

## ✅ Unit tests

The project includes a pytest test suite runnable without a Home Assistant installation:

```bash
pip install -r requirements-test.txt
pytest
```

| Test file | Coverage |
|---|---|
| `tests/test_travel_calculator.py` | ~30 tests — position logic, direction, end-of-stroke |
| `tests/test_config_flow_validation.py` | ~13 tests — timing validation (`_validate_timing`) |

---

## 📜 Credits

Based on the original project by [@davidramosweb](https://github.com/davidramosweb/home-assistant-custom-components-cover-time-based).  
Improvements inspired by [@barmazu](https://github.com/barmazu/home-assistant-custom-components-cover-rf-time-based).

