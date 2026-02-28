"""Tests for Jackery switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator
from custom_components.jackery.switch import (
    SWITCH_DESCRIPTIONS,
    JackerySwitchEntity,
    JackerySwitchEntityDescription,
    async_setup_entry,
)

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000 Plus", "modelCode": 5},
]

FULL_DEVICE_DATA: dict[str, object] = {
    "oac": 1,
    "odc": 0,
    "odcu": 1,
    "odcc": 0,
    "iac": 1,
    "idc": 0,
    "sfc": 1,
    "ups": 0,
}

FAKE_DATA: dict[str, dict[str, object]] = {
    "SN001": dict(FULL_DEVICE_DATA),
    "SN002": {"oac": 0, "odc": 1},
}


def _make_coordinator(
    data: dict[str, dict[str, object]] | None = None,
    devices: list[dict[str, object]] | None = None,
) -> JackeryCoordinator:
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    coordinator = JackeryCoordinator(hass, entry)
    # Deep-copy to prevent test mutations from bleeding across tests
    if data is not None:
        coordinator.data = {sn: dict(props) for sn, props in data.items()}
    else:
        coordinator.data = {sn: dict(props) for sn, props in FAKE_DATA.items()}
    coordinator.devices = devices if devices is not None else list(FAKE_DEVICES)
    coordinator.client = MagicMock()
    coordinator.client.device.return_value.set_property = AsyncMock()
    return coordinator


def _find_description(key: str) -> JackerySwitchEntityDescription:
    for desc in SWITCH_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise ValueError(f"No switch description with key '{key}'")


def _make_switch(
    key: str,
    device_sn: str = "SN001",
    coordinator: JackeryCoordinator | None = None,
) -> JackerySwitchEntity:
    if coordinator is None:
        coordinator = _make_coordinator()
    description = _find_description(key)
    entity = JackerySwitchEntity(coordinator, device_sn, description)
    entity.hass = MagicMock()
    return entity


def _mock_client(coordinator: JackeryCoordinator) -> MagicMock:
    """Return the coordinator's mock client, asserting it is not None."""
    assert coordinator.client is not None
    client: MagicMock = coordinator.client  # type: ignore[assignment]
    return client


# --- Description tests ---


def test_switch_descriptions_count():
    assert len(SWITCH_DESCRIPTIONS) == 8


def test_all_descriptions_have_property_key_and_slug():
    for desc in SWITCH_DESCRIPTIONS:
        assert hasattr(desc, "property_key"), f"Missing property_key on {desc.key}"
        assert isinstance(desc.property_key, str)
        assert hasattr(desc, "slug"), f"Missing slug on {desc.key}"
        assert isinstance(desc.slug, str)


def test_outlet_switches_have_outlet_device_class():
    outlet_keys = {"oac", "odc", "odcu", "odcc", "iac", "idc"}
    for desc in SWITCH_DESCRIPTIONS:
        if desc.key in outlet_keys:
            assert desc.device_class == "outlet", f"{desc.key} should have OUTLET device class"


def test_config_switches_have_config_category():
    config_keys = {"sfc", "ups"}
    for desc in SWITCH_DESCRIPTIONS:
        if desc.key in config_keys:
            assert desc.entity_category == "config", f"{desc.key} should have CONFIG category"


def test_slugs_match_plan():
    expected_slugs = {
        "oac": "ac",
        "odc": "dc",
        "odcu": "usb",
        "odcc": "car",
        "iac": "ac-in",
        "idc": "dc-in",
        "sfc": "sfc",
        "ups": "ups",
    }
    for desc in SWITCH_DESCRIPTIONS:
        assert desc.slug == expected_slugs[desc.key], (
            f"Slug mismatch for {desc.key}: expected {expected_slugs[desc.key]}, got {desc.slug}"
        )


# --- is_on tests ---


def test_is_on_true_when_value_is_1():
    switch = _make_switch("oac")
    # oac=1 -> True
    assert switch.is_on is True


def test_is_on_false_when_value_is_0():
    switch = _make_switch("odc")
    # odc=0 -> False
    assert switch.is_on is False


def test_is_on_device_2():
    switch = _make_switch("oac", device_sn="SN002")
    # SN002 oac=0 -> False
    assert switch.is_on is False


def test_is_on_device_2_dc():
    switch = _make_switch("odc", device_sn="SN002")
    # SN002 odc=1 -> True
    assert switch.is_on is True


def test_is_on_none_when_property_missing():
    coordinator = _make_coordinator(data={"SN001": {}})
    switch = _make_switch("oac", coordinator=coordinator)
    assert switch.is_on is None


def test_is_on_none_when_device_not_in_data():
    coordinator = _make_coordinator(data={})
    switch = _make_switch("oac", coordinator=coordinator)
    assert switch.is_on is None


def test_is_on_false_for_value_2():
    coordinator = _make_coordinator(data={"SN001": {"oac": 2}})
    switch = _make_switch("oac", coordinator=coordinator)
    # value == 1 is False for 2
    assert switch.is_on is False


def test_is_on_none_for_non_numeric():
    coordinator = _make_coordinator(data={"SN001": {"oac": "abc"}})
    switch = _make_switch("oac", coordinator=coordinator)
    assert switch.is_on is None


# --- turn_on / turn_off tests ---


async def test_turn_on_calls_set_property_with_slug():
    coordinator = _make_coordinator()
    switch = _make_switch("oac", coordinator=coordinator)

    await switch.async_turn_on()

    client = _mock_client(coordinator)
    client.device.assert_called_once_with("SN001")
    client.device.return_value.set_property.assert_called_once_with("ac", "on")


async def test_turn_off_calls_set_property_with_slug():
    coordinator = _make_coordinator()
    switch = _make_switch("odc", coordinator=coordinator)

    await switch.async_turn_off()

    client = _mock_client(coordinator)
    client.device.assert_called_once_with("SN001")
    client.device.return_value.set_property.assert_called_once_with("dc", "off")


async def test_turn_on_routes_to_correct_device_sn():
    coordinator = _make_coordinator()
    switch = _make_switch("oac", device_sn="SN002", coordinator=coordinator)

    await switch.async_turn_on()

    client = _mock_client(coordinator)
    client.device.assert_called_once_with("SN002")
    client.device.return_value.set_property.assert_called_once_with("ac", "on")


async def test_turn_on_applies_optimistic_update():
    coordinator = _make_coordinator()
    switch = _make_switch("odc", coordinator=coordinator)

    # odc starts at 0
    assert switch.is_on is False

    await switch.async_turn_on()

    # After turn_on, optimistic update should set odc to 1
    assert coordinator.data["SN001"]["odc"] == 1


async def test_turn_off_applies_optimistic_update():
    coordinator = _make_coordinator()
    switch = _make_switch("oac", coordinator=coordinator)

    # oac starts at 1
    assert switch.is_on is True

    await switch.async_turn_off()

    # After turn_off, optimistic update should set oac to 0
    assert coordinator.data["SN001"]["oac"] == 0


async def test_turn_on_config_switch():
    coordinator = _make_coordinator()
    switch = _make_switch("sfc", coordinator=coordinator)

    # sfc starts at 1 (on) -- turn off then on
    await switch.async_turn_off()
    client = _mock_client(coordinator)
    client.device.return_value.set_property.assert_called_with("sfc", "off")

    client.device.reset_mock()
    client.device.return_value.set_property = AsyncMock()
    await switch.async_turn_on()
    client.device.return_value.set_property.assert_called_with("sfc", "on")


async def test_turn_on_logs_error_and_skips_optimistic_on_failure():
    coordinator = _make_coordinator()
    switch = _make_switch("oac", coordinator=coordinator)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.side_effect = OSError("connection lost")

    # oac starts at 1
    assert switch.is_on is True

    # Should not raise
    await switch.async_turn_on()

    # Optimistic update should NOT have been applied (still 1, not changed)
    assert coordinator.data["SN001"]["oac"] == 1


async def test_turn_on_handles_key_error():
    coordinator = _make_coordinator()
    switch = _make_switch("oac", coordinator=coordinator)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.side_effect = KeyError("Unknown setting 'ac'")

    await switch.async_turn_on()

    # Optimistic update should NOT have been applied
    assert coordinator.data["SN001"]["oac"] == 1


async def test_turn_on_noop_when_client_is_none():
    coordinator = _make_coordinator()
    coordinator.client = None
    switch = _make_switch("oac", coordinator=coordinator)

    # Should not raise
    await switch.async_turn_on()


async def test_turn_on_noop_when_device_not_found():
    coordinator = _make_coordinator()
    switch = _make_switch("oac", coordinator=coordinator)
    _mock_client(coordinator).device.side_effect = KeyError("SN001")

    # Should not raise - KeyError is caught and logged
    await switch.async_turn_on()


async def test_turn_on_noop_when_device_list_empty():
    coordinator = _make_coordinator()
    switch = _make_switch("oac", coordinator=coordinator)
    _mock_client(coordinator).device.side_effect = IndexError("device list is empty")

    # Should not raise - IndexError is caught and logged
    await switch.async_turn_on()


async def test_turn_on_does_not_trigger_refresh():
    coordinator = _make_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    switch = _make_switch("oac", coordinator=coordinator)

    await switch.async_turn_on()

    coordinator.async_request_refresh.assert_not_called()


# --- unique_id ---


def test_unique_id():
    switch = _make_switch("oac", device_sn="SN001")
    assert switch._attr_unique_id == "SN001_oac"


# --- async_setup_entry ---


async def test_async_setup_entry_creates_switches_per_device():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySwitchEntity] = []

    def add_entities(new_entities: list[JackerySwitchEntity]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(MagicMock(), entry, add_entities)
    # SN001 has all 8 properties; SN002 has 2 (oac, odc)
    sn001_entities = [e for e in entities if e._device_sn == "SN001"]
    sn002_entities = [e for e in entities if e._device_sn == "SN002"]

    assert len(sn001_entities) == 8
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

    entities: list[JackerySwitchEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    device_sns = {e._device_sn for e in entities}
    assert device_sns == {"SN001"}


async def test_async_setup_entry_only_creates_switches_for_available_properties():
    data: dict[str, dict[str, object]] = {"SN001": {"oac": 1, "ups": 0}}
    coordinator = _make_coordinator(
        data=data,
        devices=[FAKE_DEVICES[0]],
    )
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySwitchEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    keys = {e.entity_description.key for e in entities}
    assert keys == {"oac", "ups"}
