"""Tests for JackeryCoordinator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator

# Re-import the stub exceptions so we can assert on them
from tests.conftest import _ConfigEntryAuthFailed, _UpdateFailed

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000", "modelCode": 5},
]

FAKE_PROPS_SN001: dict[str, object] = {
    "device": {"devSn": "SN001"},
    "properties": {"rb": 85, "bt": 250, "ip": 100, "op": 50},
}

FAKE_PROPS_SN002: dict[str, object] = {
    "device": {"devSn": "SN002"},
    "properties": {"rb": 42, "bt": 300, "ip": 0, "op": 200},
}


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret123",
    }
    return entry


def _make_hass() -> MagicMock:
    hass = MagicMock()

    async def _add_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = _add_executor_job
    return hass


def _make_mock_client(
    devices: list[dict[str, object]] | None = None,
    props_by_index: dict[int, dict[str, object]] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.fetch_devices.return_value = devices or FAKE_DEVICES

    # Track which device is selected and return correct properties
    selected_index: list[int] = [0]

    def select_device(idx: int) -> dict[str, object]:
        selected_index[0] = idx
        devs = devices or FAKE_DEVICES
        return devs[idx]

    default_props = {0: FAKE_PROPS_SN001, 1: FAKE_PROPS_SN002}
    actual_props = props_by_index or default_props

    def get_all_properties() -> dict[str, object]:
        return actual_props[selected_index[0]]

    client.select_device.side_effect = select_device
    client.get_all_properties.side_effect = get_all_properties

    return client


# --- Tests ---


async def test_first_refresh_populates_data():
    """First refresh should login, fetch devices, and populate data for all devices."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        return_value=mock_client,
    ):
        await coordinator.async_config_entry_first_refresh()

    assert "SN001" in coordinator.data
    assert "SN002" in coordinator.data
    assert coordinator.data["SN001"]["rb"] == 85
    assert coordinator.data["SN001"]["bt"] == 250
    assert coordinator.data["SN002"]["rb"] == 42
    assert coordinator.data["SN002"]["op"] == 200


async def test_first_refresh_stores_client_and_devices():
    """First refresh should store the client and device list on the coordinator."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        return_value=mock_client,
    ):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.client is mock_client
    assert coordinator.devices == FAKE_DEVICES


async def test_subsequent_poll_fetches_fresh_data():
    """Subsequent update (HTTP poll) should fetch fresh data for all devices."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        return_value=mock_client,
    ):
        await coordinator.async_config_entry_first_refresh()

    # Change mock to return updated data on second poll
    updated_props: dict[str, object] = {
        "device": {"devSn": "SN001"},
        "properties": {"rb": 90, "bt": 240, "ip": 50, "op": 25},
    }
    mock_client.get_all_properties.side_effect = None
    mock_client.get_all_properties.return_value = updated_props

    await coordinator.async_request_refresh()

    assert coordinator.data["SN001"]["rb"] == 90


async def test_auth_failure_on_login_raises_config_entry_auth_failed():
    """Login failure (RuntimeError) should raise ConfigEntryAuthFailed."""
    hass = _make_hass()
    entry = _make_entry()

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            side_effect=RuntimeError("Login failed: invalid credentials"),
        ),
        pytest.raises(_ConfigEntryAuthFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_auth_failure_on_fetch_raises_config_entry_auth_failed():
    """RuntimeError during property fetch should raise ConfigEntryAuthFailed."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = MagicMock()
    mock_client.fetch_devices.return_value = FAKE_DEVICES
    mock_client.select_device.return_value = FAKE_DEVICES[0]
    mock_client.get_all_properties.side_effect = RuntimeError(
        "Property fetch failed: token expired"
    )

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            return_value=mock_client,
        ),
        pytest.raises(_ConfigEntryAuthFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_transient_error_on_login_raises_update_failed():
    """Network error during login should raise UpdateFailed."""
    hass = _make_hass()
    entry = _make_entry()

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ),
        pytest.raises(_UpdateFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_transient_error_on_fetch_raises_update_failed():
    """Network error during property fetch should raise UpdateFailed."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = MagicMock()
    mock_client.fetch_devices.return_value = FAKE_DEVICES
    mock_client.select_device.return_value = FAKE_DEVICES[0]
    mock_client.get_all_properties.side_effect = requests.exceptions.Timeout("Request timed out")

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            return_value=mock_client,
        ),
        pytest.raises(_UpdateFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_devices_without_sn_are_skipped():
    """Devices with missing devSn should be skipped gracefully."""
    hass = _make_hass()
    entry = _make_entry()

    bad_devices: list[dict[str, object]] = [
        {"devId": "ID_NOSN", "devName": "NoSN"},
        {"devSn": "SN001", "devId": "ID001", "devName": "Good", "modelCode": 12},
    ]
    mock_client = _make_mock_client(
        devices=bad_devices,
        props_by_index={
            1: FAKE_PROPS_SN001,
        },
    )
    # The device at index 0 has no SN, so select_device(0) should not be called
    # for property fetching. We only need index 1.
    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        return_value=mock_client,
    ):
        await coordinator.async_config_entry_first_refresh()

    assert "SN001" in coordinator.data
    assert "" not in coordinator.data


async def test_transient_error_on_one_device_does_not_block_others():
    """When one device fails with a transient error, the other devices should still be polled."""
    hass = _make_hass()
    entry = _make_entry()

    call_count: list[int] = [0]

    def select_device(idx: int) -> dict[str, object]:
        return FAKE_DEVICES[idx]

    def get_all_properties() -> dict[str, object]:
        call_count[0] += 1
        if call_count[0] == 1:
            # First device fails
            raise requests.exceptions.Timeout("Request timed out")
        # Second device succeeds
        return FAKE_PROPS_SN002

    mock_client = MagicMock()
    mock_client.fetch_devices.return_value = FAKE_DEVICES
    mock_client.select_device.side_effect = select_device
    mock_client.get_all_properties.side_effect = get_all_properties

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        return_value=mock_client,
    ):
        await coordinator.async_config_entry_first_refresh()

    # SN001 failed but SN002 should still be present
    assert "SN001" not in coordinator.data
    assert "SN002" in coordinator.data
    assert coordinator.data["SN002"]["rb"] == 42


async def test_all_devices_transient_error_raises_update_failed():
    """When all devices fail with transient errors, UpdateFailed should be raised."""
    hass = _make_hass()
    entry = _make_entry()

    mock_client = MagicMock()
    mock_client.fetch_devices.return_value = FAKE_DEVICES
    mock_client.select_device.side_effect = lambda idx: FAKE_DEVICES[idx]
    mock_client.get_all_properties.side_effect = requests.exceptions.Timeout("Timed out")

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            return_value=mock_client,
        ),
        pytest.raises(_UpdateFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_properties_without_nested_properties_key():
    """When get_all_properties returns a flat dict (no 'properties' key), use it directly."""
    hass = _make_hass()
    entry = _make_entry()

    flat_props: dict[str, object] = {"rb": 70, "bt": 200}
    devices = [FAKE_DEVICES[0]]
    mock_client = _make_mock_client(
        devices=devices,
        props_by_index={0: flat_props},
    )

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        return_value=mock_client,
    ):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.data["SN001"]["rb"] == 70
    assert coordinator.data["SN001"]["bt"] == 200
