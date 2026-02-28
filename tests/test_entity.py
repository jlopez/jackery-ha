"""Tests for JackeryEntity base class."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from custom_components.jackery.coordinator import JackeryCoordinator
from custom_components.jackery.entity import JackeryEntity
from tests.conftest import _StubEntityDescription

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000 Plus", "modelCode": 5},
]

FAKE_DATA: dict[str, dict[str, object]] = {
    "SN001": {"rb": 85, "bt": 250, "ip": 100, "op": 50},
    "SN002": {"rb": 42, "bt": 300, "ip": 0, "op": 200},
}


def _make_coordinator() -> JackeryCoordinator:
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    coordinator = JackeryCoordinator(hass, entry)
    coordinator.data = dict(FAKE_DATA)
    coordinator.devices = list(FAKE_DEVICES)
    return coordinator


def _make_entity(
    coordinator: JackeryCoordinator | None = None,
    device_sn: str = "SN001",
    key: str = "rb",
) -> JackeryEntity:
    if coordinator is None:
        coordinator = _make_coordinator()
    description = _StubEntityDescription(key=key)
    return JackeryEntity(coordinator, device_sn, description)


# --- Tests ---


def test_unique_id():
    entity = _make_entity(device_sn="SN001", key="rb")
    assert entity._attr_unique_id == "SN001_rb"


def test_unique_id_different_device():
    entity = _make_entity(device_sn="SN002", key="bt")
    assert entity._attr_unique_id == "SN002_bt"


def test_device_info_identifiers():
    entity = _make_entity(device_sn="SN001")
    info = entity.device_info
    assert info.identifiers == {(DOMAIN, "SN001")}


def test_device_info_manufacturer():
    entity = _make_entity(device_sn="SN001")
    info = entity.device_info
    assert info.manufacturer == "Jackery"


def test_device_info_name():
    entity = _make_entity(device_sn="SN001")
    info = entity.device_info
    assert info.name == "Explorer 2000"


def test_device_info_model_known():
    entity = _make_entity(device_sn="SN001")
    info = entity.device_info
    # modelCode 12 maps to "Explorer 2000" in socketry MODEL_NAMES
    assert info.model == "Explorer 2000"


def test_device_info_model_unknown():
    coordinator = _make_coordinator()
    coordinator.devices = [
        {"devSn": "SN999", "devId": "ID999", "devName": "Mystery", "modelCode": 999},
    ]
    coordinator.data = {"SN999": {"rb": 50}}
    entity = _make_entity(coordinator=coordinator, device_sn="SN999", key="rb")
    info = entity.device_info
    assert info.model == "Unknown (999)"


def test_device_info_serial_number():
    entity = _make_entity(device_sn="SN001")
    info = entity.device_info
    assert info.serial_number == "SN001"


def test_available_when_device_in_data():
    entity = _make_entity(device_sn="SN001")
    assert entity.available is True


def test_unavailable_when_device_not_in_data():
    coordinator = _make_coordinator()
    coordinator.data = {"SN002": {"rb": 42}}
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    assert entity.available is False


def test_unavailable_when_coordinator_unavailable():
    coordinator = _make_coordinator()
    coordinator.last_update_success = False
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    assert entity.available is False


def test_prop_returns_value():
    entity = _make_entity(device_sn="SN001")
    assert entity._prop("rb") == 85
    assert entity._prop("bt") == 250


def test_prop_returns_none_for_missing_key():
    entity = _make_entity(device_sn="SN001")
    assert entity._prop("nonexistent") is None


def test_prop_returns_none_when_device_not_in_data():
    coordinator = _make_coordinator()
    coordinator.data = {}
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    assert entity._prop("rb") is None


def test_has_entity_name():
    entity = _make_entity()
    assert entity._attr_has_entity_name is True


def test_device_info_when_device_not_found():
    coordinator = _make_coordinator()
    coordinator.devices = []
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    info = entity.device_info
    assert info.name == "Jackery"
    assert info.model == "Unknown (0)"


def test_device_info_model_code_none():
    coordinator = _make_coordinator()
    coordinator.devices = [
        {"devSn": "SN001", "devId": "ID001", "devName": "Test", "modelCode": None},
    ]
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    info = entity.device_info
    assert info.model == "Unknown (0)"


def test_device_info_model_code_non_numeric_string():
    coordinator = _make_coordinator()
    coordinator.devices = [
        {"devSn": "SN001", "devId": "ID001", "devName": "Test", "modelCode": "abc"},
    ]
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    info = entity.device_info
    assert info.model == "Unknown (0)"


def test_prop_returns_falsy_value_zero():
    coordinator = _make_coordinator()
    coordinator.data = {"SN001": {"ip": 0}}
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    assert entity._prop("ip") == 0
    assert entity._prop("ip") is not None


def test_available_when_coordinator_data_is_none():
    coordinator = _make_coordinator()
    coordinator.data = None
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    assert entity.available is False


def test_prop_returns_none_when_coordinator_data_is_none():
    coordinator = _make_coordinator()
    coordinator.data = None
    entity = _make_entity(coordinator=coordinator, device_sn="SN001")
    assert entity._prop("rb") is None
