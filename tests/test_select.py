"""Tests for Jackery select entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator
from custom_components.jackery.select import (
    SELECT_DESCRIPTIONS,
    JackerySelectEntity,
    JackerySelectEntityDescription,
    async_setup_entry,
)

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000 Plus", "modelCode": 5},
]

FULL_DEVICE_DATA: dict[str, object] = {
    "lm": 0,
    "cs": 1,
    "lps": 0,
}

FAKE_DATA: dict[str, dict[str, object]] = {
    "SN001": dict(FULL_DEVICE_DATA),
    "SN002": {"lm": 2},
}


def _make_coordinator(
    data: dict[str, dict[str, object]] | None = None,
    devices: list[dict[str, object]] | None = None,
) -> JackeryCoordinator:
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    coordinator = JackeryCoordinator(hass, entry)
    if data is not None:
        coordinator.data = {sn: dict(props) for sn, props in data.items()}
    else:
        coordinator.data = {sn: dict(props) for sn, props in FAKE_DATA.items()}
    coordinator.devices = devices if devices is not None else list(FAKE_DEVICES)
    coordinator.client = MagicMock()
    coordinator.client.device.return_value.set_property = AsyncMock()
    return coordinator


def _find_description(key: str) -> JackerySelectEntityDescription:
    for desc in SELECT_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise ValueError(f"No select description with key '{key}'")


def _make_select(
    key: str,
    device_sn: str = "SN001",
    coordinator: JackeryCoordinator | None = None,
) -> JackerySelectEntity:
    if coordinator is None:
        coordinator = _make_coordinator()
    description = _find_description(key)
    entity = JackerySelectEntity(coordinator, device_sn, description)
    entity.hass = MagicMock()
    return entity


def _mock_client(coordinator: JackeryCoordinator) -> MagicMock:
    """Return the coordinator's mock client, asserting it is not None."""
    assert coordinator.client is not None
    client: MagicMock = coordinator.client  # type: ignore[assignment]
    return client


# --- Description tests ---


def test_select_descriptions_count():
    assert len(SELECT_DESCRIPTIONS) == 3


def test_all_descriptions_have_property_key_and_slug():
    for desc in SELECT_DESCRIPTIONS:
        assert hasattr(desc, "property_key"), f"Missing property_key on {desc.key}"
        assert isinstance(desc.property_key, str)
        assert hasattr(desc, "slug"), f"Missing slug on {desc.key}"
        assert isinstance(desc.slug, str)


def test_all_descriptions_have_options():
    for desc in SELECT_DESCRIPTIONS:
        assert desc.options is not None, f"Missing options on {desc.key}"
        assert len(desc.options) >= 2, f"Too few options on {desc.key}"


def test_config_selects_have_config_category():
    config_keys = {"cs", "lps"}
    for desc in SELECT_DESCRIPTIONS:
        if desc.key in config_keys:
            assert desc.entity_category == "config", f"{desc.key} should have CONFIG category"


def test_slugs_match_plan():
    expected_slugs = {
        "lm": "light",
        "cs": "charge-speed",
        "lps": "battery-protection",
    }
    for desc in SELECT_DESCRIPTIONS:
        assert desc.slug == expected_slugs[desc.key], (
            f"Slug mismatch for {desc.key}: expected {expected_slugs[desc.key]}, got {desc.slug}"
        )


def test_options_match_plan():
    expected_options: dict[str, list[str]] = {
        "lm": ["off", "low", "high", "sos"],
        "cs": ["fast", "mute"],
        "lps": ["full", "eco"],
    }
    for desc in SELECT_DESCRIPTIONS:
        assert list(desc.options or []) == expected_options[desc.key], (
            f"Options mismatch for {desc.key}"
        )


# --- current_option tests ---


def test_current_option_maps_index_to_option():
    # lm=0 -> "off"
    select = _make_select("lm")
    assert select.current_option == "off"


def test_current_option_second_index():
    # cs=1 -> "mute"
    select = _make_select("cs")
    assert select.current_option == "mute"


def test_current_option_device_2():
    # SN002 lm=2 -> "high"
    select = _make_select("lm", device_sn="SN002")
    assert select.current_option == "high"


def test_current_option_none_when_property_missing():
    coordinator = _make_coordinator(data={"SN001": {}})
    select = _make_select("lm", coordinator=coordinator)
    assert select.current_option is None


def test_current_option_none_when_device_not_in_data():
    coordinator = _make_coordinator(data={})
    select = _make_select("lm", coordinator=coordinator)
    assert select.current_option is None


def test_current_option_none_for_out_of_range_index():
    coordinator = _make_coordinator(data={"SN001": {"lm": 99}})
    select = _make_select("lm", coordinator=coordinator)
    assert select.current_option is None


def test_current_option_none_for_negative_index():
    coordinator = _make_coordinator(data={"SN001": {"lm": -1}})
    select = _make_select("lm", coordinator=coordinator)
    assert select.current_option is None


def test_current_option_none_for_non_numeric():
    coordinator = _make_coordinator(data={"SN001": {"lm": "abc"}})
    select = _make_select("lm", coordinator=coordinator)
    assert select.current_option is None


# --- async_select_option tests ---


async def test_select_option_calls_set_property_with_slug():
    coordinator = _make_coordinator()
    select = _make_select("lm", coordinator=coordinator)

    await select.async_select_option("high")

    client = _mock_client(coordinator)
    client.device.assert_called_once_with("SN001")
    client.device.return_value.set_property.assert_called_once_with("light", "high")


async def test_select_option_routes_to_correct_device_sn():
    coordinator = _make_coordinator()
    select = _make_select("lm", device_sn="SN002", coordinator=coordinator)

    await select.async_select_option("sos")

    client = _mock_client(coordinator)
    client.device.assert_called_once_with("SN002")
    client.device.return_value.set_property.assert_called_once_with("light", "sos")


async def test_select_option_applies_optimistic_update():
    coordinator = _make_coordinator()
    select = _make_select("lm", coordinator=coordinator)

    # lm starts at 0 ("off")
    assert select.current_option == "off"

    await select.async_select_option("high")

    # After select, optimistic update should set lm to 2 (index of "high")
    assert coordinator.data["SN001"]["lm"] == 2
    assert select.current_option == "high"


async def test_select_option_charge_speed():
    coordinator = _make_coordinator()
    select = _make_select("cs", coordinator=coordinator)

    await select.async_select_option("fast")

    client = _mock_client(coordinator)
    client.device.return_value.set_property.assert_called_once_with("charge-speed", "fast")
    # Optimistic update: "fast" is index 0
    assert coordinator.data["SN001"]["cs"] == 0


async def test_select_option_battery_protection():
    coordinator = _make_coordinator()
    select = _make_select("lps", coordinator=coordinator)

    await select.async_select_option("eco")

    client = _mock_client(coordinator)
    client.device.return_value.set_property.assert_called_once_with("battery-protection", "eco")
    # Optimistic update: "eco" is index 1
    assert coordinator.data["SN001"]["lps"] == 1


async def test_select_option_logs_error_and_skips_optimistic_on_failure():
    coordinator = _make_coordinator()
    select = _make_select("lm", coordinator=coordinator)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.side_effect = OSError("connection lost")

    # lm starts at 0 ("off")
    assert select.current_option == "off"

    await select.async_select_option("high")

    # Optimistic update should NOT have been applied
    assert coordinator.data["SN001"]["lm"] == 0
    assert select.current_option == "off"


async def test_select_option_handles_key_error():
    coordinator = _make_coordinator()
    select = _make_select("lm", coordinator=coordinator)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.side_effect = KeyError("Unknown setting 'light'")

    await select.async_select_option("high")

    # Optimistic update should NOT have been applied
    assert coordinator.data["SN001"]["lm"] == 0


async def test_select_option_noop_when_client_is_none():
    coordinator = _make_coordinator()
    coordinator.client = None
    select = _make_select("lm", coordinator=coordinator)

    # Should not raise
    await select.async_select_option("high")


async def test_select_option_noop_when_device_not_found():
    coordinator = _make_coordinator()
    select = _make_select("lm", coordinator=coordinator)
    _mock_client(coordinator).device.side_effect = KeyError("SN001")

    # Should not raise - KeyError is caught and logged
    await select.async_select_option("high")


async def test_select_option_noop_when_device_list_empty():
    coordinator = _make_coordinator()
    select = _make_select("lm", coordinator=coordinator)
    _mock_client(coordinator).device.side_effect = IndexError("device list is empty")

    # Should not raise - IndexError is caught and logged
    await select.async_select_option("high")


async def test_select_option_does_not_trigger_refresh():
    coordinator = _make_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    select = _make_select("lm", coordinator=coordinator)

    await select.async_select_option("high")

    coordinator.async_request_refresh.assert_not_called()


# --- unique_id ---


def test_unique_id():
    select = _make_select("lm", device_sn="SN001")
    assert select._attr_unique_id == "SN001_lm"


# --- async_setup_entry ---


async def test_async_setup_entry_creates_selects_per_device():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySelectEntity] = []

    def add_entities(new_entities: list[JackerySelectEntity]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(MagicMock(), entry, add_entities)
    # SN001 has all 3 properties; SN002 has 1 (lm)
    sn001_entities = [e for e in entities if e._device_sn == "SN001"]
    sn002_entities = [e for e in entities if e._device_sn == "SN002"]

    assert len(sn001_entities) == 3
    assert len(sn002_entities) == 1


async def test_async_setup_entry_skips_devices_without_sn():
    devices: list[dict[str, object]] = [
        {"devId": "ID_NOSN", "devName": "NoSN"},
        {"devSn": "SN001", "devId": "ID001", "devName": "Test", "modelCode": 12},
    ]
    data: dict[str, dict[str, object]] = {"SN001": dict(FULL_DEVICE_DATA)}
    coordinator = _make_coordinator(data=data, devices=devices)
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySelectEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    device_sns = {e._device_sn for e in entities}
    assert device_sns == {"SN001"}


async def test_async_setup_entry_only_creates_selects_for_available_properties():
    data: dict[str, dict[str, object]] = {"SN001": {"lm": 0, "lps": 1}}
    coordinator = _make_coordinator(
        data=data,
        devices=[FAKE_DEVICES[0]],
    )
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackerySelectEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    keys = {e.entity_description.key for e in entities}
    assert keys == {"lm", "lps"}
