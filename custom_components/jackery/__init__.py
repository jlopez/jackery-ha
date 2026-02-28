"""Jackery Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import JackeryCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
]

type JackeryConfigEntry = ConfigEntry[JackeryCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: JackeryConfigEntry) -> bool:
    """Set up Jackery from a config entry."""
    coordinator = JackeryCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JackeryConfigEntry) -> bool:
    """Unload a Jackery config entry."""
    coordinator: JackeryCoordinator = entry.runtime_data
    await coordinator.async_unload()

    result: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return result
