"""Tests for Jackery __init__.py and constants."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.jackery import PLATFORMS, async_setup_entry, async_unload_entry
from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD, DEFAULT_POLL_INTERVAL, DOMAIN


def test_domain_constant():
    assert DOMAIN == "jackery"


def test_poll_interval_constant():
    assert DEFAULT_POLL_INTERVAL == 300


def test_conf_constants():
    assert CONF_EMAIL == "email"
    assert CONF_PASSWORD == "password"


def test_platforms_list():
    assert "sensor" in PLATFORMS
    assert "binary_sensor" in PLATFORMS
    assert "switch" in PLATFORMS
    assert "select" in PLATFORMS
    assert "number" in PLATFORMS


async def test_async_setup_entry():
    """Test that async_setup_entry creates coordinator and forwards platforms."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret123",
    }

    fake_devices = [{"devSn": "SN001", "devId": "ID001", "devName": "Test"}]
    fake_props = {"properties": {"rb": 80}}

    mock_client = MagicMock()
    mock_client.fetch_devices = AsyncMock(return_value=fake_devices)
    mock_client.subscribe = AsyncMock(return_value=MagicMock())

    device_mock = MagicMock()
    device_mock.get_all_properties = AsyncMock(return_value=fake_props)
    mock_client.device.return_value = device_mock

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert entry.runtime_data is not None
    hass.config_entries.async_forward_entry_setups.assert_called_once_with(entry, PLATFORMS)


async def test_async_unload_entry():
    """Test that async_unload_entry stops the MQTT subscription and unloads platforms."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    mock_sub = MagicMock()
    mock_sub.stop = AsyncMock()

    coordinator = MagicMock()
    coordinator._subscription = mock_sub

    entry = MagicMock()
    entry.runtime_data = coordinator

    result = await async_unload_entry(hass, entry)

    assert result is True
    mock_sub.stop.assert_called_once()
    hass.config_entries.async_unload_platforms.assert_called_once_with(entry, PLATFORMS)


async def test_async_unload_entry_no_subscription():
    """Test that async_unload_entry handles missing subscription gracefully."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    coordinator = MagicMock()
    coordinator._subscription = None

    entry = MagicMock()
    entry.runtime_data = coordinator

    result = await async_unload_entry(hass, entry)

    assert result is True
    hass.config_entries.async_unload_platforms.assert_called_once_with(entry, PLATFORMS)
