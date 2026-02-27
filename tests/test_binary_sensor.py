"""Tests for Jackery binary sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.jackery.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    JackeryBinarySensorEntity,
    JackeryBinarySensorEntityDescription,
    async_setup_entry,
)
from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000 Plus", "modelCode": 5},
]

FULL_DEVICE_DATA: dict[str, object] = {
    "wss": 1,
    "ta": 0,
    "pal": 0,
}

FAKE_DATA: dict[str, dict[str, object]] = {
    "SN001": dict(FULL_DEVICE_DATA),
    "SN002": {"wss": 0, "ta": 2},
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


def _find_description(key: str) -> JackeryBinarySensorEntityDescription:
    for desc in BINARY_SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise ValueError(f"No binary sensor description with key '{key}'")


def _make_binary_sensor(
    key: str,
    device_sn: str = "SN001",
    coordinator: JackeryCoordinator | None = None,
) -> JackeryBinarySensorEntity:
    if coordinator is None:
        coordinator = _make_coordinator()
    description = _find_description(key)
    return JackeryBinarySensorEntity(coordinator, device_sn, description)


# --- Description tests ---


def test_binary_sensor_descriptions_count():
    assert len(BINARY_SENSOR_DESCRIPTIONS) == 3


def test_all_descriptions_have_property_key():
    for desc in BINARY_SENSOR_DESCRIPTIONS:
        assert hasattr(desc, "property_key"), f"Missing property_key on {desc.key}"
        assert isinstance(desc.property_key, str)


def test_alarm_sensors_use_problem_device_class():
    ta = _find_description("ta")
    pal = _find_description("pal")
    assert ta.device_class == "problem"
    assert pal.device_class == "problem"


def test_alarm_sensors_are_diagnostic():
    ta = _find_description("ta")
    pal = _find_description("pal")
    assert ta.entity_category == "diagnostic"
    assert pal.entity_category == "diagnostic"


def test_wireless_charging_uses_battery_charging_device_class():
    wss = _find_description("wss")
    assert wss.device_class == "battery_charging"


# --- Wireless charging (wss) ---


def test_wireless_charging_on():
    sensor = _make_binary_sensor("wss")
    # raw=1 -> True
    assert sensor.is_on is True


def test_wireless_charging_off():
    sensor = _make_binary_sensor("wss", device_sn="SN002")
    # raw=0 -> False
    assert sensor.is_on is False


def test_wireless_charging_off_with_value_2():
    coordinator = _make_coordinator(data={"SN001": {"wss": 2}})
    sensor = _make_binary_sensor("wss", coordinator=coordinator)
    # value == 1 is False for 2
    assert sensor.is_on is False


# --- Temperature alarm (ta) ---


def test_temperature_alarm_off():
    sensor = _make_binary_sensor("ta")
    # raw=0 -> False (no alarm)
    assert sensor.is_on is False


def test_temperature_alarm_on():
    sensor = _make_binary_sensor("ta", device_sn="SN002")
    # raw=2 -> True (alarm active)
    assert sensor.is_on is True


def test_temperature_alarm_on_with_value_1():
    coordinator = _make_coordinator(data={"SN001": {"ta": 1}})
    sensor = _make_binary_sensor("ta", coordinator=coordinator)
    assert sensor.is_on is True


# --- Power alarm (pal) ---


def test_power_alarm_off():
    sensor = _make_binary_sensor("pal")
    # raw=0 -> False
    assert sensor.is_on is False


def test_power_alarm_on():
    coordinator = _make_coordinator(data={"SN001": {"pal": 3}})
    sensor = _make_binary_sensor("pal", coordinator=coordinator)
    assert sensor.is_on is True


# --- Edge cases ---


def test_is_on_none_when_property_missing():
    coordinator = _make_coordinator(data={"SN001": {}})
    sensor = _make_binary_sensor("wss", coordinator=coordinator)
    assert sensor.is_on is None


def test_is_on_none_when_device_not_in_data():
    coordinator = _make_coordinator(data={})
    sensor = _make_binary_sensor("wss", coordinator=coordinator)
    assert sensor.is_on is None


def test_is_on_none_with_non_numeric_raw():
    coordinator = _make_coordinator(data={"SN001": {"wss": "abc"}})
    sensor = _make_binary_sensor("wss", coordinator=coordinator)
    assert sensor.is_on is None


def test_is_on_none_with_non_numeric_raw_neq_zero():
    coordinator = _make_coordinator(data={"SN001": {"ta": "xyz"}})
    sensor = _make_binary_sensor("ta", coordinator=coordinator)
    assert sensor.is_on is None


def test_unique_id():
    sensor = _make_binary_sensor("wss", device_sn="SN001")
    assert sensor._attr_unique_id == "SN001_wss"


# --- async_setup_entry ---


async def test_async_setup_entry_creates_sensors_per_device():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackeryBinarySensorEntity] = []

    def add_entities(new_entities: list[JackeryBinarySensorEntity]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(MagicMock(), entry, add_entities)
    # SN001 has all 3 properties (wss, ta, pal); SN002 has 2 (wss, ta)
    sn001_entities = [e for e in entities if e._device_sn == "SN001"]
    sn002_entities = [e for e in entities if e._device_sn == "SN002"]

    assert len(sn001_entities) == 3
    assert len(sn002_entities) == 2


async def test_async_setup_entry_skips_devices_without_sn():
    devices: list[dict[str, object]] = [
        {"devId": "ID_NOSN", "devName": "NoSN"},
        {"devSn": "SN001", "devId": "ID001", "devName": "Test", "modelCode": 12},
    ]
    data: dict[str, dict[str, object]] = {"SN001": dict(FULL_DEVICE_DATA)}
    coordinator = _make_coordinator(data=data, devices=devices)
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackeryBinarySensorEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    device_sns = {e._device_sn for e in entities}
    assert device_sns == {"SN001"}


async def test_async_setup_entry_only_creates_sensors_for_available_properties():
    data: dict[str, dict[str, object]] = {"SN001": {"wss": 0}}
    coordinator = _make_coordinator(
        data=data,
        devices=[FAKE_DEVICES[0]],
    )
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackeryBinarySensorEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    keys = {e.entity_description.key for e in entities}
    assert keys == {"wss"}
