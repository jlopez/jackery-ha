"""Tests for Jackery sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator
from custom_components.jackery.sensor import (
    BATTERY_STATE_MAP,
    SENSOR_DESCRIPTIONS,
    JackerySensorEntity,
    JackerySensorEntityDescription,
    async_setup_entry,
)

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000 Plus", "modelCode": 5},
]

FULL_DEVICE_DATA: dict[str, object] = {
    "rb": 85,
    "bt": 250,
    "bs": 1,
    "ip": 100,
    "op": 50,
    "it": 35,
    "ot": 120,
    "acip": 200,
    "cip": 0,
    "acov": 1200,
    "acohz": 60,
    "acps": 150,
    "acpss": 75,
    "acpsp": 100,
    "ec": 0,
    "pmb": 1,
    "tt": 35,
    "ss": 2,
}

FAKE_DATA: dict[str, dict[str, object]] = {
    "SN001": dict(FULL_DEVICE_DATA),
    "SN002": {"rb": 42, "bt": 300, "ip": 0, "op": 200},
}


def _make_coordinator(
    data: dict[str, dict[str, object]] | None = None,
    devices: list[dict[str, object]] | None = None,
) -> JackeryCoordinator:
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    coordinator = JackeryCoordinator(hass, entry)
    coordinator.data = data if data is not None else dict(FAKE_DATA)
    coordinator.devices = devices if devices is not None else list(FAKE_DEVICES)
    return coordinator


def _find_description(key: str) -> JackerySensorEntityDescription:
    for desc in SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise ValueError(f"No sensor description with key '{key}'")


def _make_sensor(
    key: str,
    device_sn: str = "SN001",
    coordinator: JackeryCoordinator | None = None,
) -> JackerySensorEntity:
    if coordinator is None:
        coordinator = _make_coordinator()
    description = _find_description(key)
    return JackerySensorEntity(coordinator, device_sn, description)


# --- Description tests ---


def test_sensor_descriptions_count():
    assert len(SENSOR_DESCRIPTIONS) == 18


def test_all_descriptions_have_property_key():
    for desc in SENSOR_DESCRIPTIONS:
        assert hasattr(desc, "property_key"), f"Missing property_key on {desc.key}"
        assert isinstance(desc.property_key, str)


# --- Battery sensor (rb) ---


def test_battery_value():
    sensor = _make_sensor("rb")
    assert sensor.native_value == 85.0


def test_battery_value_device_2():
    sensor = _make_sensor("rb", device_sn="SN002")
    assert sensor.native_value == 42.0


# --- Battery temperature (bt) with scale=10 ---


def test_battery_temperature_scaled():
    sensor = _make_sensor("bt")
    # raw 250 / scale 10 = 25.0
    assert sensor.native_value == 25.0


def test_battery_temperature_scaled_device_2():
    sensor = _make_sensor("bt", device_sn="SN002")
    # raw 300 / scale 10 = 30.0
    assert sensor.native_value == 30.0


# --- Battery state (bs) enum ---


def test_battery_state_charging():
    sensor = _make_sensor("bs")
    # raw=1 -> "charging"
    assert sensor.native_value == "charging"


def test_battery_state_idle():
    coordinator = _make_coordinator(data={"SN001": {"bs": 0}})
    sensor = _make_sensor("bs", coordinator=coordinator)
    assert sensor.native_value == "idle"


def test_battery_state_discharging():
    coordinator = _make_coordinator(data={"SN001": {"bs": 2}})
    sensor = _make_sensor("bs", coordinator=coordinator)
    assert sensor.native_value == "discharging"


def test_battery_state_unknown_value():
    coordinator = _make_coordinator(data={"SN001": {"bs": 99}})
    sensor = _make_sensor("bs", coordinator=coordinator)
    assert sensor.native_value is None


def test_battery_state_map():
    assert BATTERY_STATE_MAP == {0: "idle", 1: "charging", 2: "discharging"}


# --- Input/output power (ip, op) ---


def test_input_power():
    sensor = _make_sensor("ip")
    assert sensor.native_value == 100.0


def test_output_power():
    sensor = _make_sensor("op")
    assert sensor.native_value == 50.0


# --- Duration sensors (it, ot) with value_fn ---


def test_time_to_full_nonzero():
    sensor = _make_sensor("it")
    # raw 35 / 10 = 3.5
    assert sensor.native_value == 3.5


def test_time_to_full_zero_returns_none():
    coordinator = _make_coordinator(data={"SN001": {"it": 0}})
    sensor = _make_sensor("it", coordinator=coordinator)
    assert sensor.native_value is None


def test_time_remaining_nonzero():
    sensor = _make_sensor("ot")
    # raw 120 / 10 = 12.0
    assert sensor.native_value == 12.0


def test_time_remaining_zero_returns_none():
    coordinator = _make_coordinator(data={"SN001": {"ot": 0}})
    sensor = _make_sensor("ot", coordinator=coordinator)
    assert sensor.native_value is None


# --- AC sensors ---


def test_ac_input_power():
    sensor = _make_sensor("acip")
    assert sensor.native_value == 200.0


def test_ac_voltage_scaled():
    sensor = _make_sensor("acov")
    # raw 1200 / 10 = 120.0
    assert sensor.native_value == 120.0


def test_ac_frequency():
    sensor = _make_sensor("acohz")
    assert sensor.native_value == 60.0


def test_ac_power():
    sensor = _make_sensor("acps")
    assert sensor.native_value == 150.0


def test_ac_power_secondary():
    sensor = _make_sensor("acpss")
    assert sensor.native_value == 75.0


def test_ac_socket_power():
    sensor = _make_sensor("acpsp")
    assert sensor.native_value == 100.0


# --- Car input power ---


def test_car_input_power():
    sensor = _make_sensor("cip")
    assert sensor.native_value == 0.0


# --- Diagnostic sensors ---


def test_error_code():
    sensor = _make_sensor("ec")
    assert sensor.native_value == 0.0


def test_power_mode_battery():
    sensor = _make_sensor("pmb")
    assert sensor.native_value == 1.0


def test_total_temperature():
    sensor = _make_sensor("tt")
    # raw 35, scale=1, so 35.0
    assert sensor.native_value == 35.0


def test_system_status():
    sensor = _make_sensor("ss")
    assert sensor.native_value == 2.0


# --- Edge cases ---


def test_native_value_none_when_property_missing():
    coordinator = _make_coordinator(data={"SN001": {}})
    sensor = _make_sensor("rb", coordinator=coordinator)
    assert sensor.native_value is None


def test_native_value_none_when_device_not_in_data():
    coordinator = _make_coordinator(data={})
    sensor = _make_sensor("rb", coordinator=coordinator)
    assert sensor.native_value is None


def test_unique_id():
    sensor = _make_sensor("rb", device_sn="SN001")
    assert sensor._attr_unique_id == "SN001_rb"


# --- async_setup_entry ---


async def test_async_setup_entry_creates_sensors_per_device():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySensorEntity] = []

    def add_entities(new_entities: list[JackerySensorEntity]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(MagicMock(), entry, add_entities)
    # SN001 has all 18 properties, SN002 has 4 properties (rb, bt, ip, op)
    sn001_entities = [e for e in entities if e._device_sn == "SN001"]
    sn002_entities = [e for e in entities if e._device_sn == "SN002"]

    assert len(sn001_entities) == 18
    assert len(sn002_entities) == 4


async def test_async_setup_entry_skips_devices_without_sn():
    devices: list[dict[str, object]] = [
        {"devId": "ID_NOSN", "devName": "NoSN"},
        {"devSn": "SN001", "devId": "ID001", "devName": "Test", "modelCode": 12},
    ]
    data = {"SN001": dict(FULL_DEVICE_DATA)}
    coordinator = _make_coordinator(data=data, devices=devices)
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySensorEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    # Only SN001 should produce entities
    device_sns = {e._device_sn for e in entities}
    assert device_sns == {"SN001"}


def test_battery_state_fn_with_non_numeric_raw():
    coordinator = _make_coordinator(data={"SN001": {"bs": "abc"}})
    sensor = _make_sensor("bs", coordinator=coordinator)
    assert sensor.native_value is None


def test_duration_fn_with_non_numeric_raw():
    coordinator = _make_coordinator(data={"SN001": {"it": "abc"}})
    sensor = _make_sensor("it", coordinator=coordinator)
    assert sensor.native_value is None


def test_scale_with_non_numeric_raw():
    coordinator = _make_coordinator(data={"SN001": {"bt": "abc"}})
    sensor = _make_sensor("bt", coordinator=coordinator)
    assert sensor.native_value is None


def test_native_value_string_raw_returned_as_string():
    coordinator = _make_coordinator(data={"SN001": {"ec": "E42"}})
    sensor = _make_sensor("ec", coordinator=coordinator)
    assert sensor.native_value == "E42"


def test_native_value_non_primitive_raw_returns_none():
    coordinator = _make_coordinator(data={"SN001": {"ec": [1, 2, 3]}})
    sensor = _make_sensor("ec", coordinator=coordinator)
    assert sensor.native_value is None


async def test_async_setup_entry_only_creates_sensors_for_available_properties():
    data: dict[str, dict[str, object]] = {"SN001": {"rb": 50, "ip": 100}}
    coordinator = _make_coordinator(
        data=data,
        devices=[FAKE_DEVICES[0]],
    )
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySensorEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    keys = {e.entity_description.key for e in entities}
    assert keys == {"rb", "ip"}
