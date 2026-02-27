## Phase 0: Restructure repo for HA custom integration + HACS (65138bb)

**Files Reviewed:**
- `custom_components/__init__.py`
- `custom_components/jackery/__init__.py`
- `hacs.json`
- `pyproject.toml`
- `tests/test_init.py`
- `.github/workflows/ci.yml`

### Critical

*None identified*

### Moderate

**Issue 0.1: Missing `homeassistant` dev dependency** ([pyproject.toml:13](pyproject.toml#L13))

The plan explicitly states: "Add `homeassistant` as a dev dependency for type stubs." This was not done. While mypy passes now because no HA modules are imported yet, this dependency is needed starting Phase 1/2 when importing from `homeassistant.core`, `homeassistant.config_entries`, etc. Without it, mypy will fail on HA imports and dev environments won't have HA type information.

**Options:**
1. Add `homeassistant` to the dev dependency group now (recommended)
2. Defer to Phase 1 when it becomes strictly necessary

**Recommendation:** Fix now -- this is explicitly called for in Phase 0's plan and ensures the dev environment is ready for subsequent phases.

**Resolution:** Backed out. Adding `homeassistant` as a dev dependency causes a build failure in the current environment because its transitive dependency `lru-dict` requires C compilation and the Xcode license has not been accepted on this machine. Deferring to Phase 1 where it will be required regardless, and the environment issue should be resolved by then.

---

### Minor

*None identified*

---

## Phase 1: Constants, manifest, and strings (8a607f8)

**Files Reviewed:**
- `custom_components/jackery/const.py`
- `custom_components/jackery/manifest.json`
- `custom_components/jackery/strings.json`
- `tests/test_init.py`
- `tests/test_manifest.py`

### Critical

*None identified*

### Moderate

*None identified*

### Minor

*None identified*

### AC Verification

1. **DOMAIN importable from const.py** -- Verified. `from custom_components.jackery.const import DOMAIN` works, value is `"jackery"`.
2. **manifest.json is valid JSON with all required HA fields** -- Verified. Contains all required fields: `domain`, `name`, `codeowners`, `config_flow`, `documentation`, `integration_type`, `iot_class`, `issue_tracker`, `requirements`, `version`.
3. **strings.json covers the config flow steps and errors** -- Verified. Contains `config.step.user` (with title, description, data), `config.error` (4 keys: `invalid_auth`, `cannot_connect`, `no_devices`, `unknown`), and `config.abort` (`already_configured`).

### Checks

- ruff: pass
- ruff format: pass
- mypy: pass
- pytest: pass (8/8, 100% coverage)

### Notes

Clean review. This phase consists entirely of static configuration files (two JSON files and a Python constants module) that match the plan specification exactly. No logic, no edge cases, no security surface. The test coverage is appropriate for the deliverables.

---

## Phase 2: Config flow (d0992d4)

**Files Reviewed:**
- `custom_components/jackery/__init__.py`
- `custom_components/jackery/config_flow.py`
- `tests/conftest.py`
- `tests/test_config_flow.py`
- `pyproject.toml`

### Critical

*None identified*

### Moderate

**Issue 2.1: Redundant device fetch doubles API calls during setup** ([config_flow.py:36](custom_components/jackery/config_flow.py#L36))

`Client.login()` internally calls `_fetch_all_devices()` and stores the result in `client._creds["devices"]`. The config flow then calls `client.fetch_devices()` again on line 36, which makes a second identical HTTP request to fetch the device list. This doubles the network round-trips during setup (2-4 extra HTTP calls depending on shared devices) and adds unnecessary latency to the user-facing config flow.

**Options:**
1. Read devices from `client._creds["devices"]` directly, avoiding the redundant fetch (recommended)
2. Keep the redundant fetch for "freshness" -- but the data is already seconds old at most

**Recommendation:** Use `client._creds["devices"]` since the code already accesses `_creds` for `userId` on line 48. This eliminates redundant API calls without introducing new coupling.

---

### Minor

**Issue 2.2: `requests.exceptions.RequestException` is redundant with `OSError` in except clause** ([config_flow.py:39](custom_components/jackery/config_flow.py#L39))

`requests.exceptions.RequestException` inherits from `OSError`, so catching both in the same `except` clause is redundant -- `OSError` alone would catch all `requests` exceptions. However, having `RequestException` listed explicitly improves readability by documenting the intent that requests-specific errors are expected. Not a bug, just a minor redundancy.

**Recommendation:** Keep as-is for readability. No fix needed.

---

## Phase 3: Coordinator (d6d9010)

**Files Reviewed:**
- `custom_components/jackery/__init__.py`
- `custom_components/jackery/coordinator.py`
- `tests/conftest.py`
- `tests/test_coordinator.py`
- `tests/test_init.py`

### Critical

*None identified*

### Moderate

**Issue 3.1: Single device failure aborts the entire update cycle** ([coordinator.py:84](custom_components/jackery/coordinator.py#L84))

If a `RuntimeError` or network error occurs while fetching properties for the first device in a multi-device setup, the entire `_async_update_data` call raises immediately. Any devices after the failing one never get polled. One temporarily unreachable device blocks data updates for all devices.

Auth errors (`RuntimeError`) should still abort immediately since they affect the entire account. But transient network errors for a single device should not prevent polling the remaining devices.

**Options:**
1. Catch transient errors per-device, log a warning, skip the failing device, and continue. Only raise if ALL devices fail or on auth errors. (recommended)
2. Collect errors and raise only after attempting all devices.

**Recommendation:** Option 1. Log a warning per failed device. Continue polling remaining devices. Auth errors (`RuntimeError` -> `ConfigEntryAuthFailed`) still abort immediately. If zero devices returned data successfully, raise `UpdateFailed`.

---

**Issue 3.2: Test stub `_StubDataUpdateCoordinator.async_config_entry_first_refresh` does not call `_async_setup`** ([conftest.py:96](tests/conftest.py#L96))

The real HA `DataUpdateCoordinator` calls `_async_setup()` before `_async_update_data()` during the first refresh. The stub skips this and goes straight to `_async_update_data`. The code works because `_async_update_data` has a lazy `if self.client is None` guard that calls `_async_setup` manually. But this means the tests never validate the `_async_setup` lifecycle hook in isolation, and if someone removes the lazy guard (expecting the HA-standard hook to work), tests would still pass while the real integration would break.

**Options:**
1. Update the stub to call `_async_setup()` before `_async_update_data()` to match real HA behavior (recommended)
2. Leave as-is since the lazy guard provides defense-in-depth

**Recommendation:** Option 1. The stub should match the real coordinator's contract so tests are trustworthy.

---

### Minor

**Issue 3.3: No cleanup of the socketry `Client` on config entry unload** ([__init__.py:33](custom_components/jackery/__init__.py#L33))

`async_unload_entry` unloads platforms but does not clean up the coordinator's `Client` reference. While the socketry `Client` currently holds no persistent connections (HTTP-only), explicitly clearing the reference makes teardown explicit and prevents future issues if socketry adds persistent connections or MQTT subscriptions.

**Options:**
1. Set `coordinator.client = None` in unload (recommended)
2. Leave as-is since garbage collection handles it

**Recommendation:** Option 1 -- minimal change, makes intent clear.

---

## Phase 4: Base entity + entity descriptors (9f4fb42)

**Files Reviewed:**
- `custom_components/jackery/entity.py`
- `tests/conftest.py`
- `tests/test_entity.py`

### Critical

*None identified*

### Moderate

**Issue 4.1: `int(str(raw_code))` crashes on non-integer modelCode values** ([entity.py:37](custom_components/jackery/entity.py#L37))

The `device_info` property converts `raw_code` via `int(str(raw_code))`. If the API returns `None`, an empty string, a float, or any non-integer-coercible value for `modelCode`, this raises an unhandled `ValueError`. Since `raw_code` comes from external API data (via the device dict), defensive handling is required.

Crash scenarios:
- `modelCode` is `None` -> `int("None")` -> ValueError
- `modelCode` is `""` -> `int("")` -> ValueError
- `modelCode` is `3.14` -> `int("3.14")` -> ValueError

**Options:**
1. Wrap in try/except and fall back to `0` (recommended)
2. Use `isinstance` check before conversion

**Recommendation:** Option 1 -- wrap with try/except to gracefully fall back to `0`, which will render as "Unknown (0)" in the model name. This is the simplest and most robust approach.

---

**Issue 4.2: `available` property crashes with TypeError if `coordinator.data` is None** ([entity.py:50](custom_components/jackery/entity.py#L50))

The `available` property uses `self._device_sn in self.coordinator.data`, which raises `TypeError: argument of type 'NoneType' is not iterable` if `coordinator.data` is `None`. While HA's `DataUpdateCoordinator` normally populates `data` after first refresh, edge cases during initialization or error recovery could leave `data` as `None`.

**Options:**
1. Add a None guard: `self.coordinator.data is not None and self._device_sn in self.coordinator.data` (recommended)
2. Ensure coordinator always initializes data to `{}`

**Recommendation:** Option 1 -- defensive None check is cheap and prevents crashes in edge cases.

---

### Minor

**Issue 4.3: `_prop` does not guard against `coordinator.data` being None** ([entity.py:54](custom_components/jackery/entity.py#L54))

`_prop` calls `self.coordinator.data.get(self._device_sn)` which will raise `AttributeError` if `coordinator.data` is `None`. This is the same root cause as Issue 4.2.

**Options:**
1. Add None guard at the start of the method (recommended)

**Recommendation:** Return `None` early if `coordinator.data` is `None`.

---

**Issue 4.4: Missing test for `_prop` returning falsy values** ([test_entity.py](tests/test_entity.py))

The test suite verifies `_prop` with truthy values, missing keys, and missing device. However, it does not test that `_prop` correctly returns falsy values like `0` (as opposed to `None`). This matters because downstream consumers need to distinguish "property is 0" from "property is missing."

**Recommendation:** Add a test that verifies `_prop` returns `0` when the value is `0`.

---

## Phase 5: Sensor entities (33420a7)

**Files Reviewed:**
- `custom_components/jackery/sensor.py`
- `tests/conftest.py`
- `tests/test_sensor.py`

### Critical

*None identified*

### Moderate

**Issue 5.1: `native_value` returns `None` for string raw values on non-enum sensors** ([sensor.py:242](custom_components/jackery/sensor.py#L242))

For sensors without a `value_fn` and with `scale == 1.0` (e.g., `ec`, `pmb`, `ss`), the `native_value` property's final branch only returns a value if `raw` is an `int` or `float`. If the API ever returns a string value for these diagnostic sensors, the property silently returns `None` instead of the actual value. While the API currently sends integers for these fields, the defensive fallback is overly restrictive.

More importantly, this creates an asymmetry: sensors with `value_fn` can return strings (like the battery state enum), but the default branch cannot. If a future diagnostic sensor needs to report a string value (e.g., an error message for `ec`), it would require adding a `value_fn` when the default branch should handle it.

**Options:**
1. Also return `str(raw)` for string values in the default branch (recommended)
2. Leave as-is since the API currently sends integers for all affected sensors

**Recommendation:** Option 1. Add a string fallback so the default branch handles both numeric and string raw values. This future-proofs the code without breaking existing behavior.

---

### Minor

**Issue 5.2: `PERCENTAGE` constant not used for battery unit** ([sensor.py:70](custom_components/jackery/sensor.py#L70))

The battery sensor description uses the raw string `"%"` for `native_unit_of_measurement` instead of importing and using `homeassistant.const.PERCENTAGE`. While functionally identical (the constant equals `"%"`), using the constant is the idiomatic HA pattern and would be caught if HA ever changed the representation.

**Recommendation:** Import and use `PERCENTAGE` from `homeassistant.const`. Low priority since the values are identical.

---

### AC Verification

1. **All 18 sensor descriptions defined** -- Verified. `len(SENSOR_DESCRIPTIONS) == 18` and all keys from the plan are present: `rb`, `bt`, `bs`, `ip`, `op`, `it`, `ot`, `acip`, `cip`, `acov`, `acohz`, `acps`, `acpss`, `acpsp`, `ec`, `pmb`, `tt`, `ss`.
2. **Values correctly scaled** -- Verified. `bt` and `acov` use `scale=10.0`. Duration sensors `it` and `ot` use `_duration_fn` which divides by 10. All others use default `scale=1.0`.
3. **Battery state renders as enum** -- Verified. Uses `SensorDeviceClass.ENUM` with `options=["idle", "charging", "discharging"]` and a `_battery_state_fn` that maps 0/1/2 to the option strings.
4. **Duration shows "unknown" for zero** -- Verified. `_duration_fn` returns `None` when `val == 0`, which HA renders as "unknown".
5. **Tests pass, mypy passes** -- Verified. 89 tests pass, mypy reports no issues, 99% coverage.

### Checks

- ruff: pass
- ruff format: pass
- mypy: pass
- pytest: pass (89 tests, 99% coverage)

---

## Phase 6: Binary sensor entities (fae9e53)

**Files Reviewed:**
- `custom_components/jackery/binary_sensor.py`
- `tests/conftest.py`
- `tests/test_binary_sensor.py`

### Critical

*None identified*

### Moderate

*None identified*

### Minor

**Issue 6.1: Dead `None` guard in `_eq_one` and `_neq_zero` helper functions** ([binary_sensor.py:32-33](custom_components/jackery/binary_sensor.py#L32), [binary_sensor.py:42-43](custom_components/jackery/binary_sensor.py#L42))

Both `_eq_one` and `_neq_zero` contain `if raw is None: return None` guards. However, the `is_on` property in `JackeryBinarySensorEntity` already returns `None` before calling `is_on_fn` when `raw is None` (lines 94-96). This means the `None` guards inside the helper functions are unreachable dead code when called from `is_on`.

While defense-in-depth is reasonable for standalone helper functions (they could be called directly in tests or other contexts), this does result in 2 uncovered lines per function in the coverage report.

**Recommendation:** Keep the guards for defensive programming -- they protect against direct calls to the helpers outside of `is_on`. No fix needed for this.

---

**Issue 6.2: Missing test coverage for `_neq_zero` error handling path** ([binary_sensor.py:46-47](custom_components/jackery/binary_sensor.py#L46))

The `except (TypeError, ValueError)` path in `_neq_zero` is never exercised by tests. The test `test_is_on_none_with_non_numeric_raw` only tests the `wss` sensor (which uses `_eq_one`). The `ta` and `pal` sensors (which use `_neq_zero`) are never tested with non-numeric input, leaving lines 46-47 uncovered.

**Recommendation:** Add a test that verifies `_neq_zero` returns `None` for non-numeric input by testing a `ta` or `pal` sensor with a string value like `"abc"`.

---

### AC Verification

1. **3 binary sensor descriptions** -- Verified. `len(BINARY_SENSOR_DESCRIPTIONS) == 3` with keys `wss`, `ta`, `pal`.
2. **Alarm sensors use PROBLEM device class** -- Verified. Both `ta` and `pal` use `BinarySensorDeviceClass.PROBLEM`.
3. **Tests pass** -- Verified. All 20 binary sensor tests pass. Overall suite: 110 tests, 98% coverage.

### Checks

- ruff: pass
- ruff format: pass
- mypy: pass
- pytest: pass (110 tests, 98% coverage)

---

## Phase 7: Switch entities (c7c4132)

**Files Reviewed:**
- `custom_components/jackery/switch.py`
- `tests/conftest.py`
- `tests/test_switch.py`

### Critical

*None identified*

### Moderate

**Issue 7.1: Race condition between `select_device` and `set_property`** ([switch.py:135-136](custom_components/jackery/switch.py#L135))

The `_async_set_state` method makes two separate `async_add_executor_job` calls: one for `select_device` and one for `set_property`. Between these two awaits, the event loop can schedule another coroutine (e.g., another switch entity turning on/off, or a coordinator refresh). Since `select_device` mutates shared state on the client (`self._creds`), a concurrent call could change the active device between `select_device` and `set_property`, causing the command to be sent to the wrong device.

Example interleaving:
1. Coroutine A: `select_device(0)` -- sets active device to SN001
2. Coroutine B: `select_device(1)` -- overwrites active device to SN002
3. Coroutine A: `set_property("ac", "on")` -- sends AC on to SN002 instead of SN001

**Options:**
1. Combine `select_device` and `set_property` into a single executor job so they cannot be interleaved (recommended)
2. Add an asyncio.Lock to serialize all device commands

**Recommendation:** Option 1. Create a helper function that calls both `select_device` and `set_property` atomically in a single executor thread, eliminating the yield point between them.

---

**Issue 7.2: No error handling for `set_property` failures** ([switch.py:135-136](custom_components/jackery/switch.py#L135))

The `set_property` call can raise `KeyError` (unknown setting), `ValueError` (read-only setting), or network-related exceptions from the underlying MQTT publish. None of these are caught, so any failure propagates as an unhandled exception through HA's entity framework. While HA handles this gracefully (logs the error and marks the action as failed), catching and logging at the entity level provides better diagnostics and prevents the optimistic update from being applied on the wrong device (related to Issue 7.1).

Additionally, `select_device` can raise `IndexError` if the device list is stale (e.g., a device was removed from the account between coordinator refreshes).

**Options:**
1. Wrap the executor calls in try/except, log the error, and skip the optimistic update on failure (recommended)
2. Leave unhandled and rely on HA's generic error handling

**Recommendation:** Option 1. Log a meaningful error message and return early so the optimistic update is not applied when the command fails.

---

### Minor

*None identified*

---

### AC Verification

1. **All 8 switches defined** -- Verified. `len(SWITCH_DESCRIPTIONS) == 8` with keys `oac`, `odc`, `odcu`, `odcc`, `iac`, `idc`, `sfc`, `ups`.
2. **Commands use socketry slugs (not raw keys)** -- Verified. Each description has the correct slug: `ac`, `dc`, `usb`, `car`, `ac-in`, `dc-in`, `sfc`, `ups`.
3. **Tests pass, mypy passes** -- Verified. All 25 switch tests pass. Full suite: 136 tests, 99% coverage.

---

## Phase 8: Select entities (adbdf92)

**Files Reviewed:**
- `custom_components/jackery/select.py`
- `tests/conftest.py`
- `tests/test_select.py`

### Critical

*None identified*

### Moderate

*None identified*

### Minor

**Issue 8.1: `_device_index` duplicated between switch and select** ([select.py:119](custom_components/jackery/select.py#L119), [switch.py:157](custom_components/jackery/switch.py#L157))

The `_device_index` method is identical in both `JackerySwitchEntity` and `JackerySelectEntity`. It iterates `self.coordinator.devices` to find the device index by serial number. This method belongs in the base `JackeryEntity` class (which already has `_find_device` for the dict lookup). The number platform (Phase 9) will likely need the same method, compounding the duplication.

**Options:**
1. Move `_device_index` to `JackeryEntity` base class (recommended)
2. Leave as-is since each platform file is self-contained

**Recommendation:** Move to the base class after Phase 9 is implemented, as a refactoring pass. Not fixing now to avoid touching switch.py (a prior phase) in this review scope. The duplication is not a bug, just a maintenance concern.

---

### AC Verification

1. **All 3 selects defined with correct option lists** -- Verified. `len(SELECT_DESCRIPTIONS) == 3` with keys `lm`, `cs`, `lps`. Options match plan: `["off", "low", "high", "sos"]`, `["fast", "mute"]`, `["full", "eco"]`.
2. **Select dispatches to socketry set_property with the string value** -- Verified. `async_select_option` calls `client.set_property(slug, option)` where `slug` is `"light"`, `"charge-speed"`, or `"battery-protection"` and `option` is the human-readable string.
3. **Tests pass** -- Verified. All 22 select tests pass. Full suite: 165 tests, 99% coverage. The select module itself has 100% coverage.

### Checks

- ruff: pass
- ruff format: pass
- mypy: pass
- pytest: pass (165 tests, 99% coverage)

### Notes

Clean implementation. The select entity follows the same well-established patterns from the switch phase (Phase 7), including the `select_device` + `set_property` atomic executor pattern, optimistic updates with rollback on failure, and property-key-based entity creation. The `current_option` implementation correctly handles all edge cases: None values, non-numeric values, negative indices, and out-of-range indices. Test coverage is thorough with 22 tests covering descriptions, current_option edge cases, async_select_option with various scenarios, and setup_entry filtering.

---

## Phase 9: Number entities (9b2b5d4)

**Files Reviewed:**
- `custom_components/jackery/number.py`
- `tests/conftest.py`
- `tests/test_number.py`

### Critical

*None identified*

### Moderate

**Issue 9.1: `_device_index` duplicated across switch.py, select.py, and number.py** ([number.py:122](custom_components/jackery/number.py#L122), [switch.py:157](custom_components/jackery/switch.py#L157), [select.py:119](custom_components/jackery/select.py#L119))

The `_device_index` method is now copy-pasted in three separate entity classes: `JackerySwitchEntity`, `JackerySelectEntity`, and `JackeryNumberEntity`. All three implementations are identical -- they iterate `self.coordinator.devices` to find the index of the device matching `self._device_sn`. This was deferred in the Phase 8 review (Issue 8.1) with the recommendation to consolidate after Phase 9. Now that Phase 9 is complete and all three consumers exist, this should be moved to the `JackeryEntity` base class in `entity.py`, which already has the related `_find_device` method that performs the same iteration to return the device dict.

**Options:**
1. Move `_device_index` to `JackeryEntity` base class and remove the three duplicates (recommended)
2. Leave as-is

**Recommendation:** Option 1. The base class already has `_find_device` which iterates the same list. Adding `_device_index` beside it is the natural location. This eliminates three copies of identical logic and prevents future platforms from needing yet another copy.

---

### Minor

*None identified*

---

### AC Verification

1. **All 3 numbers defined with min/max/step** -- Verified. `len(NUMBER_DESCRIPTIONS) == 3` with keys `ast`, `pm`, `sltb`. Ranges: auto_shutdown 0-24 step 1, energy_saving 0-24 step 1, screen_timeout 0-300 step 10.
2. **Correctly reads from coordinator data** -- Verified. `native_value` reads via `self._prop(description.property_key)` and converts to float. Handles None, non-numeric, and zero values correctly.
3. **Writes via socketry set_property** -- Verified. `async_set_native_value` calls `client.set_property(slug, int(value))` with the correct slug for each description. Device selection is atomic with the command in a single executor job.
4. **Tests pass** -- Verified. All 30 number tests pass. Full suite: 195 tests, 99% coverage. The number module itself has 100% coverage.

### Checks

- ruff: pass
- ruff format: pass
- mypy: pass
- pytest: pass (195 tests, 99% coverage)

---

## Phase 10: Diagnostics (2afd56b)

**Files Reviewed:**
- `custom_components/jackery/diagnostics.py`
- `tests/test_diagnostics.py`

### Critical

*None identified*

### Moderate

**Issue 10.1: Missing MQTT connection status** ([diagnostics.py:44](custom_components/jackery/diagnostics.py#L44))

The plan explicitly requires: "Include MQTT connection status (`coordinator.client._active_mqtt is not None`)". The implementation omits this entirely. While `_active_mqtt` is a private attribute of the socketry `Client`, the plan specifies it for diagnostics purposes, and diagnostics data is inherently implementation-detail-heavy. The absence means users cannot tell from diagnostics whether MQTT push is active or only HTTP polling is running, which is the primary troubleshooting use case.

**Options:**
1. Add MQTT status with `getattr()` fallback so it doesn't break if socketry changes the private attribute (recommended)
2. Skip it and document why

**Recommendation:** Option 1. Use `getattr(coordinator.client, '_active_mqtt', None) is not None` with a try/except for safety. Also include whether the client itself is connected.

---

**Issue 10.2: `_redact_dict` does not redact sensitive fields inside lists** ([diagnostics.py:15](custom_components/jackery/diagnostics.py#L15))

The recursive redaction handles nested dicts but not lists containing dicts. If any data structure contains `[{"token": "secret"}]`, the sensitive value would leak through unredacted. While current coordinator data is `{sn: {prop: val}}` (no lists), this is a security-relevant gap -- any future change to the data shape or config entry data could silently expose secrets.

**Options:**
1. Extend `_redact_dict` to recurse into lists (recommended)
2. Accept the risk since current data shapes don't contain lists

**Recommendation:** Option 1. Simple addition to handle `isinstance(value, list)` with recursive redaction. Defense-in-depth for security-sensitive code.

---

### Minor

*None identified*

---
