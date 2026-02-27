# jackery-ha: Home Assistant Integration for Jackery Power Stations

## Context

Build a HACS-compatible Home Assistant custom integration for Jackery power stations using the `socketry` PyPI package as the backend. The integration should provide real-time monitoring (sensors) and control (switches, selects, numbers) via MQTT push with HTTP poll fallback. This is a brand-new integration in the `jlopez/jackery-ha` repository.

The scaffolded repo currently uses a `src/jackery_ha/` Python package layout. HA custom integrations require a `custom_components/<domain>/` layout. Phase 0 restructures accordingly.

### Socketry API surface (PyPI dependency)

```python
client = await Client.login(email, password)          # async auth
devices = await client.fetch_devices()                 # device discovery
device = client.device(0)                              # Device by index or SN
props = await device.get_all_properties()              # HTTP property read
await device.set_property("ac", "on", wait=True)       # MQTT command
sub = await client.subscribe(callback)                 # real-time MQTT updates
await sub.stop()                                       # cancel subscription
```

Key types: `Client`, `Device`, `Subscription`, `Setting`, `TokenExpiredError`
Key module: `socketry.properties` — `PROPERTIES` list, `MODEL_NAMES` dict, `resolve()` function

---

## Phase 0: Restructure repo for HA custom integration + HACS [COMPLETE]

**Why**: HA requires `custom_components/jackery/` layout. HACS requires `hacs.json` at root.

### Changes

1. **Move** `src/jackery_ha/__init__.py` → `custom_components/jackery/__init__.py` (will be replaced in Phase 2)
2. **Delete** `src/jackery_ha/py.typed` and `src/` directory
3. **Create** `hacs.json` at repo root:
   ```json
   {
     "name": "Jackery Power Stations",
     "render_readme": true
   }
   ```
4. **Update** `pyproject.toml`:
   - Remove `[build-system]` (not a distributable package — HACS copies files directly)
   - Change `dependencies = []` → add `socketry>=0.1.1` as a runtime dep (HA installs requirements from `manifest.json`, not pyproject — but keep for dev/test)
   - Add `homeassistant` as a dev dependency for type stubs
   - Update coverage source from `src/jackery_ha` to `custom_components/jackery`
   - Update pytest cov target from `jackery_ha` to `custom_components.jackery`
   - Update CI paths to include `custom_components/**/*.py`
5. **Update** `tests/` — keep `tests/__init__.py` and `tests/test_init.py` (will be replaced in later phases)
6. **Update** `.github/workflows/ci.yml` paths to match new layout

### Acceptance criteria
- `uv run ruff check .` passes
- `uv run mypy .` passes
- `uv run pytest` passes
- Directory structure: `custom_components/jackery/` exists, `src/` is gone

---

## Phase 1: Constants, manifest, and strings [COMPLETE]

**Why**: Foundation files every HA integration needs. All subsequent phases import from these.

### Files to create

**`custom_components/jackery/const.py`**
```python
DOMAIN = "jackery"
DEFAULT_POLL_INTERVAL = 300  # seconds — HTTP fallback when MQTT is connected
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
```

**`custom_components/jackery/manifest.json`**
```json
{
  "domain": "jackery",
  "name": "Jackery Power Stations",
  "codeowners": ["@jlopez"],
  "config_flow": true,
  "documentation": "https://github.com/jlopez/jackery-ha",
  "integration_type": "hub",
  "iot_class": "cloud_push",
  "issue_tracker": "https://github.com/jlopez/jackery-ha/issues",
  "requirements": ["socketry>=0.1.1"],
  "version": "0.1.0"
}
```

**`custom_components/jackery/strings.json`**
```json
{
  "config": {
    "step": {
      "user": {
        "title": "Jackery Account",
        "description": "Enter your Jackery app credentials.",
        "data": {
          "email": "Email",
          "password": "Password"
        }
      }
    },
    "error": {
      "invalid_auth": "Invalid email or password.",
      "cannot_connect": "Unable to connect to Jackery servers.",
      "no_devices": "No devices found on this account.",
      "unknown": "An unexpected error occurred."
    },
    "abort": {
      "already_configured": "This account is already configured."
    }
  }
}
```

### Acceptance criteria
- `DOMAIN` importable from `const.py`
- `manifest.json` is valid JSON with all required HA fields
- `strings.json` covers the config flow steps and errors

---

## Phase 2: Config flow [COMPLETE]

**Why**: Entry point for users to add the integration. Validates credentials, discovers devices.

### File: `custom_components/jackery/config_flow.py`

**Behavior**:
1. Single step: prompt for email + password
2. Call `await Client.login(email, password)` to validate credentials
3. Call `await client.fetch_devices()` to verify at least one device exists
4. Use `userId` from client credentials as unique ID (`async_set_unique_id` + `_abort_if_unique_id_configured`)
5. Store `email` and `password` in `config_entry.data`
6. Error mapping:
   - `RuntimeError` from login → `invalid_auth`
   - `aiohttp.ClientError` / `TimeoutError` → `cannot_connect`
   - Empty device list → `no_devices`
   - Other exceptions → `unknown`

### File: `custom_components/jackery/__init__.py` (stub)

Minimal `async_setup_entry` / `async_unload_entry` that just returns True. Will be fully implemented in Phase 3.

### Tests: `tests/test_config_flow.py`
- Test successful login + device discovery → creates entry
- Test invalid credentials → shows `invalid_auth` error
- Test network error → shows `cannot_connect` error
- Test no devices → shows `no_devices` error
- Test duplicate account → aborts with `already_configured`

### Acceptance criteria
- Config flow class registered in `__init__.py`
- All error paths tested
- `uv run pytest` and `uv run mypy .` pass

---

## Phase 3: Coordinator [COMPLETE]

**Why**: Central data manager. Hybrid MQTT push + HTTP poll. All entities read from coordinator data.

### File: `custom_components/jackery/coordinator.py`

**Class**: `JackeryCoordinator(DataUpdateCoordinator[dict[str, dict[str, object]]])`

**Data shape**: `{device_sn: {property_key: raw_value, ...}, ...}` — one entry per device, property values are raw integers from the API.

**Lifecycle**:
1. `_async_setup()` (called once before first update):
   - Create `socketry.Client` from stored email/password via `Client.login()`
   - Call `client.fetch_devices()` to populate device list
   - Start MQTT subscription via `client.subscribe(callback)` with `on_disconnect` handler
   - Store `Client`, device list, and `Subscription` on the coordinator
2. `_async_update_data()` (called on `update_interval`, HTTP poll fallback):
   - For each device, call `device.get_all_properties()`
   - Return merged `{sn: properties, ...}` dict
   - Raises `ConfigEntryAuthFailed` if `TokenExpiredError` is not recoverable
   - Raises `UpdateFailed` on transient errors
3. MQTT callback `_handle_mqtt_update(device_sn, properties)`:
   - Merge pushed properties into existing data: `self.data[sn].update(properties)`
   - Call `self.async_set_updated_data(self.data)` to notify entities and reset poll timer
4. `_handle_disconnect()`:
   - Log warning that MQTT disconnected, poll-only mode active
5. Unload: `subscription.stop()` in `async_unload_entry`

**update_interval**: `DEFAULT_POLL_INTERVAL` (300s) — long because MQTT push is the primary path.

### File: `custom_components/jackery/__init__.py` (full implementation)

**`async_setup_entry`**:
1. Create coordinator, call `await coordinator.async_config_entry_first_refresh()`
   - This automatically raises `ConfigEntryNotReady` on failure with exponential backoff
2. Store coordinator on `entry.runtime_data`
3. Forward setup to platforms: `sensor`, `binary_sensor`, `switch`, `select`, `number`

**`async_unload_entry`**:
1. Stop MQTT subscription
2. Unload platforms via `hass.config_entries.async_unload_platforms()`

**Platforms constant**: `PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.SELECT, Platform.NUMBER]`

### Tests: `tests/test_coordinator.py`
- Test first refresh populates data for all devices
- Test MQTT callback merges properties and notifies entities
- Test HTTP fallback polls all devices
- Test auth failure raises ConfigEntryAuthFailed
- Test transient error raises UpdateFailed

### Acceptance criteria
- Coordinator data is populated on first refresh
- MQTT updates merge into existing data correctly
- HTTP poll serves as fallback
- All tests pass, mypy passes

---

## Phase 4: Base entity + entity descriptors [COMPLETE]

**Why**: Shared base class for all platforms. Provides DeviceInfo, availability, and coordinator data access.

### File: `custom_components/jackery/entity.py`

**Class**: `JackeryEntity(CoordinatorEntity[JackeryCoordinator])`

- `_attr_has_entity_name = True`
- Constructor takes `coordinator`, `device_sn`, and entity description
- `device_info` property returns `DeviceInfo`:
  - `identifiers={(DOMAIN, device_sn)}`
  - `manufacturer="Jackery"`
  - `name=device.name`
  - `model=MODEL_NAMES.get(device.model_code, f"Unknown ({model_code})")`
  - `serial_number=device_sn`
- `available` property: `super().available and device_sn in coordinator.data`
- Helper `_prop(key)`: returns `coordinator.data[device_sn].get(key)` — used by all entities to read a raw property value
- `unique_id`: `f"{device_sn}_{description.key}"`

### Entity description dataclasses

Define custom description subclasses for each platform in their respective files (not here). Each adds a `property_key: str` field for the raw Jackery property key.

### Acceptance criteria
- Base entity provides DeviceInfo with correct manufacturer, model, serial
- `_prop()` reads from coordinator data
- Availability correctly reflects device presence in coordinator data

---

## Phase 5: Sensor entities [COMPLETE]

**Why**: Read-only monitoring — battery, power, temperature, voltage, etc.

### File: `custom_components/jackery/sensor.py`

**Entity description**: `JackerySensorEntityDescription(SensorEntityDescription)` with added fields:
- `property_key: str` — raw Jackery key (e.g., `"rb"`, `"bt"`)
- `scale: float = 1.0` — divide raw value by this
- `value_fn: Callable[[object], float | str | None] | None = None` — optional custom transform

**Sensor descriptions** (18 total):

| Key | Name | Device Class | Unit | State Class | Scale | Category | Notes |
|-----|------|-------------|------|-------------|-------|----------|-------|
| `rb` | Battery | BATTERY | % | MEASUREMENT | 1 | — | |
| `bt` | Battery temperature | TEMPERATURE | °C | MEASUREMENT | 10 | — | |
| `bs` | Battery state | — (enum) | — | — | 1 | — | options: idle/charging/discharging |
| `ip` | Input power | POWER | W | MEASUREMENT | 1 | — | |
| `op` | Output power | POWER | W | MEASUREMENT | 1 | — | |
| `it` | Time to full | DURATION | h | MEASUREMENT | 10 | — | None when 0 |
| `ot` | Time remaining | DURATION | h | MEASUREMENT | 10 | — | None when 0 |
| `acip` | AC input power | POWER | W | MEASUREMENT | 1 | — | |
| `cip` | Car input power | POWER | W | MEASUREMENT | 1 | — | |
| `acov` | AC voltage | VOLTAGE | V | MEASUREMENT | 10 | — | |
| `acohz` | AC frequency | FREQUENCY | Hz | MEASUREMENT | 1 | — | |
| `acps` | AC power | POWER | W | MEASUREMENT | 1 | — | |
| `acpss` | AC power (secondary) | POWER | W | MEASUREMENT | 1 | — | |
| `acpsp` | AC socket power | POWER | W | MEASUREMENT | 1 | — | |
| `ec` | Error code | — | — | — | 1 | DIAGNOSTIC | |
| `pmb` | Power mode battery | — | — | — | 1 | DIAGNOSTIC | |
| `tt` | Total temperature | TEMPERATURE | °C | MEASUREMENT | 1 | DIAGNOSTIC | |
| `ss` | System status | — | — | — | 1 | DIAGNOSTIC | |

**`native_value`** property:
- Read raw value via `self._prop(description.property_key)`
- If `value_fn` is set, use it
- If `scale != 1`, return `raw / scale`
- For duration sensors (`it`, `ot`): return `None` when raw == 0
- For `bs` (battery state): map 0→"idle", 1→"charging", 2→"discharging"

**`async_setup_entry`**: iterate over coordinator devices, create sensors for each device where the property key exists in the device's data.

### Tests: `tests/test_sensor.py`
- Test each sensor type returns correct value with scaling
- Test duration sensors return None when raw is 0
- Test battery state maps integers to strings
- Test sensors are created per-device
- Test unavailable when property missing

### Acceptance criteria
- All 18 sensor descriptions defined
- Values correctly scaled
- Battery state renders as enum
- Duration shows "unknown" for zero
- Tests pass, mypy passes

---

## Phase 6: Binary sensor entities [COMPLETE]

**Why**: Read-only boolean indicators — wireless charging, alarms.

### File: `custom_components/jackery/binary_sensor.py`

**Descriptions** (3 total):

| Key | Name | Device Class | Category | is_on logic |
|-----|------|-------------|----------|-------------|
| `wss` | Wireless charging | BATTERY_CHARGING | — | `value == 1` |
| `ta` | Temperature alarm | PROBLEM | DIAGNOSTIC | `value != 0` |
| `pal` | Power alarm | PROBLEM | DIAGNOSTIC | `value != 0` |

**`is_on`** property: read raw value via `_prop()`, apply `is_on_fn`.

### Tests: `tests/test_binary_sensor.py`

### Acceptance criteria
- 3 binary sensor descriptions
- Alarm sensors use PROBLEM device class
- Tests pass

---

## Phase 7: Switch entities [COMPLETE]

**Why**: Binary on/off controls — AC, DC, USB, car outputs, inputs, SFC, UPS.

### File: `custom_components/jackery/switch.py`

**Descriptions** (8 total):

| Key | Slug | Name | Device Class | Category |
|-----|------|------|-------------|----------|
| `oac` | `ac` | AC output | OUTLET | — |
| `odc` | `dc` | DC output | OUTLET | — |
| `odcu` | `usb` | USB output | OUTLET | — |
| `odcc` | `car` | Car output | OUTLET | — |
| `iac` | `ac-in` | AC input | OUTLET | — |
| `idc` | `dc-in` | DC input | OUTLET | — |
| `sfc` | `sfc` | Super fast charge | — | CONFIG |
| `ups` | `ups` | UPS mode | — | CONFIG |

**Entity description** adds: `slug: str` — the socketry setting slug for `device.set_property()`.

**`is_on`**: `self._prop(key) == 1`

**`async_turn_on`**: `await device.set_property(slug, "on")`
**`async_turn_off`**: `await device.set_property(slug, "off")`

After sending a command, call `self.coordinator.async_request_refresh()` to trigger an HTTP poll for immediate state confirmation (the MQTT push should also arrive and update state).

**Optimistic update**: After calling `set_property`, immediately update coordinator data with the expected value so the UI is responsive. The MQTT push or HTTP poll will confirm or correct.

### Tests: `tests/test_switch.py`
- Test is_on reads from coordinator data
- Test turn_on calls device.set_property with correct slug and "on"
- Test turn_off calls device.set_property with correct slug and "off"

### Acceptance criteria
- All 8 switches defined
- Commands use socketry slugs (not raw keys)
- Tests pass, mypy passes

---

## Phase 8: Select entities [COMPLETE]

**Why**: Enum-based settings with more than on/off or non-binary options.

### File: `custom_components/jackery/select.py`

**Descriptions** (3 total):

| Key | Slug | Name | Options | Category |
|-----|------|------|---------|----------|
| `lm` | `light` | Light mode | off, low, high, sos | — |
| `cs` | `charge-speed` | Charge speed | fast, mute | CONFIG |
| `lps` | `battery-protection` | Battery protection | full, eco | CONFIG |

**`current_option`**: map raw int → options list index
**`async_select_option`**: `await device.set_property(slug, option_string)`

### Tests: `tests/test_select.py`

### Acceptance criteria
- All 3 selects defined with correct option lists
- Select dispatches to socketry set_property with the string value
- Tests pass

---

## Phase 9: Number entities [COMPLETE]

**Why**: Numeric settings — timeouts/timers.

### File: `custom_components/jackery/number.py`

**Descriptions** (3 total):

| Key | Slug | Name | Unit | Min | Max | Step | Category |
|-----|------|------|------|-----|-----|------|----------|
| `ast` | `auto-shutdown` | Auto shutdown | hours | 0 | 24 | 1 | CONFIG |
| `pm` | `energy-saving` | Energy saving | hours | 0 | 24 | 1 | CONFIG |
| `sltb` | `screen-timeout` | Screen timeout | seconds | 0 | 300 | 10 | CONFIG |

Note: `sltb` reads from key `sltb`, but socketry's `Setting.prop_key` handles the write key (`slt`) automatically.

**`native_value`**: raw int from coordinator data
**`async_set_native_value`**: `await device.set_property(slug, int(value))`

### Tests: `tests/test_number.py`

### Acceptance criteria
- All 3 numbers defined with min/max/step
- Correctly reads from coordinator data
- Writes via socketry set_property
- Tests pass

---

## Phase 10: Diagnostics [COMPLETE]

**Why**: Debug data for troubleshooting HACS issues.

### File: `custom_components/jackery/diagnostics.py`

**`async_get_config_entry_diagnostics`**:
- Return coordinator data (all device properties)
- Redact sensitive fields: `email`, `password`, `token`, `mqttPassWord`, `userId`
- Include device list metadata (SN, name, model — not credentials)
- Include MQTT connection status (`coordinator.client._active_mqtt is not None`)

### Tests: `tests/test_diagnostics.py`
- Test that sensitive fields are redacted
- Test that device properties are included

### Acceptance criteria
- Diagnostics returns useful debug info
- No sensitive data exposed
- Tests pass

---

## Verification

After all phases:
1. `uv run ruff check .` — no lint errors
2. `uv run ruff format --check .` — no format issues
3. `uv run mypy .` — no type errors
4. `uv run pytest` — all tests pass
5. Verify `custom_components/jackery/` contains: `__init__.py`, `config_flow.py`, `coordinator.py`, `const.py`, `entity.py`, `sensor.py`, `binary_sensor.py`, `switch.py`, `select.py`, `number.py`, `diagnostics.py`, `manifest.json`, `strings.json`
6. Verify `hacs.json` exists at repo root
7. Manual test: copy `custom_components/jackery/` to a HA instance's `custom_components/` directory, restart, add integration via UI, verify devices and entities appear
