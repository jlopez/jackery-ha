"""Switch platform for Jackery integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from socketry import MqttError

from .coordinator import JackeryCoordinator
from .entity import JackeryEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class JackerySwitchEntityDescription(SwitchEntityDescription):  # type: ignore[misc]
    """Describes a Jackery switch entity."""

    property_key: str
    slug: str


SWITCH_DESCRIPTIONS: tuple[JackerySwitchEntityDescription, ...] = (
    JackerySwitchEntityDescription(
        key="oac",
        translation_key="ac_output",
        property_key="oac",
        slug="ac",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    JackerySwitchEntityDescription(
        key="odc",
        translation_key="dc_output",
        property_key="odc",
        slug="dc",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    JackerySwitchEntityDescription(
        key="odcu",
        translation_key="usb_output",
        property_key="odcu",
        slug="usb",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    JackerySwitchEntityDescription(
        key="odcc",
        translation_key="car_output",
        property_key="odcc",
        slug="car",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    JackerySwitchEntityDescription(
        key="iac",
        translation_key="ac_input",
        property_key="iac",
        slug="ac-in",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    JackerySwitchEntityDescription(
        key="idc",
        translation_key="dc_input",
        property_key="idc",
        slug="dc-in",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    JackerySwitchEntityDescription(
        key="sfc",
        translation_key="super_fast_charge",
        property_key="sfc",
        slug="sfc",
        entity_category=EntityCategory.CONFIG,
    ),
    JackerySwitchEntityDescription(
        key="ups",
        translation_key="ups_mode",
        property_key="ups",
        slug="ups",
        entity_category=EntityCategory.CONFIG,
    ),
)


class JackerySwitchEntity(JackeryEntity, SwitchEntity):  # type: ignore[misc]
    """Representation of a Jackery switch."""

    entity_description: JackerySwitchEntityDescription

    def __init__(
        self,
        coordinator: JackeryCoordinator,
        device_sn: str,
        description: JackerySwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device_sn, description)

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        raw = self._prop(self.entity_description.property_key)
        if raw is None:
            return None
        try:
            return bool(int(raw) == 1)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_state("on", 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_state("off", 0)

    async def _async_set_state(self, value: str, optimistic_value: int) -> None:
        """Send a command to the device and apply an optimistic update."""
        coordinator = self.coordinator
        sn = self._device_sn
        slug = self.entity_description.slug
        prop_key = self.entity_description.property_key

        if coordinator.client is None:
            return

        try:
            device = coordinator.client.device(sn)
            await device.set_property(slug, value)
        except (KeyError, ValueError, MqttError) as err:
            _LOGGER.error("Failed to set %s=%s for device %s: %s", slug, value, sn, err)
            return

        # Optimistic update: immediately reflect the expected state
        if coordinator.data is not None and sn in coordinator.data:
            coordinator.data[sn][prop_key] = optimistic_value
            coordinator.async_set_updated_data(coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery switch entities from a config entry."""
    coordinator: JackeryCoordinator = entry.runtime_data
    entities: list[JackerySwitchEntity] = []

    for device in coordinator.devices:
        sn = str(device.get("devSn", ""))
        if not sn:
            continue
        device_data = coordinator.data.get(sn, {})
        for description in SWITCH_DESCRIPTIONS:
            if description.property_key in device_data:
                entities.append(JackerySwitchEntity(coordinator, sn, description))

    async_add_entities(entities)
