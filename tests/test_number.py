"""Tests for Jackery number entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator
from custom_components.jackery.number import (
    NUMBER_DESCRIPTIONS,
    JackeryNumberEntity,
    JackeryNumberEntityDescription,
    async_setup_entry,
)

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000 Plus", "modelCode": 5},
]

FULL_DEVICE_DATA: dict[str, object] = {
    "ast": 12,
    "pm": 6,
    "sltb": 60,
}

FAKE_DATA: dict[str, dict[str, object]] = {
    "SN001": dict(FULL_DEVICE_DATA),
    "SN002": {"ast": 0},
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


def _find_description(key: str) -> JackeryNumberEntityDescription:
    for desc in NUMBER_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise ValueError(f"No number description with key '{key}'")


def _make_number(
    key: str,
    device_sn: str = "SN001",
    coordinator: JackeryCoordinator | None = None,
) -> JackeryNumberEntity:
    if coordinator is None:
        coordinator = _make_coordinator()
    description = _find_description(key)
    entity = JackeryNumberEntity(coordinator, device_sn, description)
    entity.hass = MagicMock()
    return entity


def _mock_client(coordinator: JackeryCoordinator) -> MagicMock:
    """Return the coordinator's mock client, asserting it is not None."""
    assert coordinator.client is not None
    client: MagicMock = coordinator.client  # type: ignore[assignment]
    return client


# --- Description tests ---


def test_number_descriptions_count():
    assert len(NUMBER_DESCRIPTIONS) == 3


def test_all_descriptions_have_property_key_and_slug():
    for desc in NUMBER_DESCRIPTIONS:
        assert hasattr(desc, "property_key"), f"Missing property_key on {desc.key}"
        assert isinstance(desc.property_key, str)
        assert hasattr(desc, "slug"), f"Missing slug on {desc.key}"
        assert isinstance(desc.slug, str)


def test_all_descriptions_have_config_category():
    for desc in NUMBER_DESCRIPTIONS:
        assert desc.entity_category == "config", f"{desc.key} should have CONFIG category"


def test_slugs_match_plan():
    expected_slugs = {
        "ast": "auto-shutdown",
        "pm": "energy-saving",
        "sltb": "screen-timeout",
    }
    for desc in NUMBER_DESCRIPTIONS:
        assert desc.slug == expected_slugs[desc.key], (
            f"Slug mismatch for {desc.key}: expected {expected_slugs[desc.key]}, got {desc.slug}"
        )


def test_min_max_step_auto_shutdown():
    desc = _find_description("ast")
    assert desc.native_min_value == 0
    assert desc.native_max_value == 24
    assert desc.native_step == 1


def test_min_max_step_energy_saving():
    desc = _find_description("pm")
    assert desc.native_min_value == 0
    assert desc.native_max_value == 24
    assert desc.native_step == 1


def test_min_max_step_screen_timeout():
    desc = _find_description("sltb")
    assert desc.native_min_value == 0
    assert desc.native_max_value == 300
    assert desc.native_step == 10


def test_units_hours_for_timers():
    for key in ("ast", "pm"):
        desc = _find_description(key)
        assert desc.native_unit_of_measurement == "h", f"{key} should use hours"


def test_unit_seconds_for_screen_timeout():
    desc = _find_description("sltb")
    assert desc.native_unit_of_measurement == "s"


# --- native_value tests ---


def test_native_value_reads_from_coordinator():
    number = _make_number("ast")
    # ast=12 -> 12.0
    assert number.native_value == 12.0


def test_native_value_energy_saving():
    number = _make_number("pm")
    # pm=6 -> 6.0
    assert number.native_value == 6.0


def test_native_value_screen_timeout():
    number = _make_number("sltb")
    # sltb=60 -> 60.0
    assert number.native_value == 60.0


def test_native_value_zero():
    coordinator = _make_coordinator(data={"SN001": {"ast": 0}})
    number = _make_number("ast", coordinator=coordinator)
    assert number.native_value == 0.0


def test_native_value_device_2():
    number = _make_number("ast", device_sn="SN002")
    # SN002 ast=0 -> 0.0
    assert number.native_value == 0.0


def test_native_value_none_when_property_missing():
    coordinator = _make_coordinator(data={"SN001": {}})
    number = _make_number("ast", coordinator=coordinator)
    assert number.native_value is None


def test_native_value_none_when_device_not_in_data():
    coordinator = _make_coordinator(data={})
    number = _make_number("ast", coordinator=coordinator)
    assert number.native_value is None


def test_native_value_none_for_non_numeric():
    coordinator = _make_coordinator(data={"SN001": {"ast": "abc"}})
    number = _make_number("ast", coordinator=coordinator)
    assert number.native_value is None


# --- async_set_native_value tests ---


async def test_set_value_calls_set_property_with_slug():
    coordinator = _make_coordinator()
    number = _make_number("ast", coordinator=coordinator)

    await number.async_set_native_value(10.0)

    client = _mock_client(coordinator)
    client.device.assert_called_once_with("SN001")
    client.device.return_value.set_property.assert_called_once_with("auto-shutdown", 10)


async def test_set_value_energy_saving():
    coordinator = _make_coordinator()
    number = _make_number("pm", coordinator=coordinator)

    await number.async_set_native_value(8.0)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.assert_called_once_with("energy-saving", 8)


async def test_set_value_screen_timeout():
    coordinator = _make_coordinator()
    number = _make_number("sltb", coordinator=coordinator)

    await number.async_set_native_value(120.0)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.assert_called_once_with("screen-timeout", 120)


async def test_set_value_routes_to_correct_device_sn():
    coordinator = _make_coordinator()
    number = _make_number("ast", device_sn="SN002", coordinator=coordinator)

    await number.async_set_native_value(5.0)

    client = _mock_client(coordinator)
    client.device.assert_called_once_with("SN002")
    client.device.return_value.set_property.assert_called_once_with("auto-shutdown", 5)


async def test_set_value_applies_optimistic_update():
    coordinator = _make_coordinator()
    number = _make_number("ast", coordinator=coordinator)

    # ast starts at 12
    assert number.native_value == 12.0

    await number.async_set_native_value(18.0)

    # After set, optimistic update should set ast to 18
    assert coordinator.data["SN001"]["ast"] == 18
    assert number.native_value == 18.0


async def test_set_value_logs_error_and_skips_optimistic_on_failure():
    coordinator = _make_coordinator()
    number = _make_number("ast", coordinator=coordinator)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.side_effect = OSError("connection lost")

    # ast starts at 12
    assert number.native_value == 12.0

    await number.async_set_native_value(18.0)

    # Optimistic update should NOT have been applied
    assert coordinator.data["SN001"]["ast"] == 12
    assert number.native_value == 12.0


async def test_set_value_handles_key_error():
    coordinator = _make_coordinator()
    number = _make_number("ast", coordinator=coordinator)

    client = _mock_client(coordinator)
    client.device.return_value.set_property.side_effect = KeyError("auto-shutdown")

    await number.async_set_native_value(18.0)

    # Optimistic update should NOT have been applied
    assert coordinator.data["SN001"]["ast"] == 12


async def test_set_value_noop_when_client_is_none():
    coordinator = _make_coordinator()
    coordinator.client = None
    number = _make_number("ast", coordinator=coordinator)

    # Should not raise
    await number.async_set_native_value(18.0)


async def test_set_value_noop_when_device_not_found():
    coordinator = _make_coordinator()
    number = _make_number("ast", coordinator=coordinator)
    _mock_client(coordinator).device.side_effect = KeyError("SN001")

    # Should not raise - KeyError is caught and logged
    await number.async_set_native_value(18.0)


async def test_set_value_noop_when_device_list_empty():
    coordinator = _make_coordinator()
    number = _make_number("ast", coordinator=coordinator)
    _mock_client(coordinator).device.side_effect = IndexError("device list is empty")

    # Should not raise - IndexError is caught and logged
    await number.async_set_native_value(18.0)


async def test_set_value_does_not_trigger_refresh():
    coordinator = _make_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    number = _make_number("ast", coordinator=coordinator)

    await number.async_set_native_value(18.0)

    coordinator.async_request_refresh.assert_not_called()


# --- unique_id ---


def test_unique_id():
    number = _make_number("ast", device_sn="SN001")
    assert number._attr_unique_id == "SN001_ast"


# --- async_setup_entry ---


async def test_async_setup_entry_creates_numbers_per_device():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackeryNumberEntity] = []

    def add_entities(new_entities: list[JackeryNumberEntity]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(MagicMock(), entry, add_entities)
    # SN001 has all 3 properties; SN002 has 1 (ast)
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

    entities: list[JackeryNumberEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    device_sns = {e._device_sn for e in entities}
    assert device_sns == {"SN001"}


async def test_async_setup_entry_only_creates_numbers_for_available_properties():
    data: dict[str, dict[str, object]] = {"SN001": {"ast": 12, "sltb": 60}}
    coordinator = _make_coordinator(
        data=data,
        devices=[FAKE_DEVICES[0]],
    )
    entry = MagicMock()
    entry.runtime_data = coordinator

    entities: list[JackeryNumberEntity] = []
    await async_setup_entry(MagicMock(), entry, entities.extend)
    keys = {e.entity_description.key for e in entities}
    assert keys == {"ast", "sltb"}
