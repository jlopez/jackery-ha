"""Select platform for Jackery integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from socketry import MqttError

from .coordinator import JackeryCoordinator
from .entity import JackeryEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class JackerySelectEntityDescription(SelectEntityDescription):  # type: ignore[misc]
    """Describes a Jackery select entity."""

    property_key: str
    slug: str


SELECT_DESCRIPTIONS: tuple[JackerySelectEntityDescription, ...] = (
    JackerySelectEntityDescription(
        key="lm",
        translation_key="light_mode",
        property_key="lm",
        slug="light",
        options=["off", "low", "high", "sos"],
    ),
    JackerySelectEntityDescription(
        key="cs",
        translation_key="charge_speed",
        property_key="cs",
        slug="charge-speed",
        entity_category=EntityCategory.CONFIG,
        options=["fast", "mute"],
    ),
    JackerySelectEntityDescription(
        key="lps",
        translation_key="battery_protection",
        property_key="lps",
        slug="battery-protection",
        entity_category=EntityCategory.CONFIG,
        options=["full", "eco"],
    ),
)


class JackerySelectEntity(JackeryEntity, SelectEntity):  # type: ignore[misc]
    """Representation of a Jackery select."""

    entity_description: JackerySelectEntityDescription

    def __init__(
        self,
        coordinator: JackeryCoordinator,
        device_sn: str,
        description: JackerySelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device_sn, description)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        raw = self._prop(self.entity_description.property_key)
        if raw is None:
            return None
        try:
            idx = int(raw)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return None
        options = self.entity_description.options
        if options is None or idx < 0 or idx >= len(options):
            return None
        result: str = options[idx]
        return result

    async def async_select_option(self, option: str) -> None:
        """Set the selected option via socketry."""
        coordinator = self.coordinator
        sn = self._device_sn
        slug = self.entity_description.slug
        prop_key = self.entity_description.property_key

        if coordinator.client is None:
            return

        try:
            device = coordinator.client.device(sn)
            await device.set_property(slug, option)
        except (KeyError, ValueError, MqttError) as err:
            _LOGGER.error("Failed to set %s=%s for device %s: %s", slug, option, sn, err)
            return

        # Optimistic update: map option string back to index
        options = self.entity_description.options
        if options is not None and option in options:
            optimistic_value = options.index(option)
            if coordinator.data is not None and sn in coordinator.data:
                coordinator.data[sn][prop_key] = optimistic_value
                coordinator.async_set_updated_data(coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery select entities from a config entry."""
    coordinator: JackeryCoordinator = entry.runtime_data
    entities: list[JackerySelectEntity] = []

    for device in coordinator.devices:
        sn = str(device.get("devSn", ""))
        if not sn:
            continue
        device_data = coordinator.data.get(sn, {})
        for description in SELECT_DESCRIPTIONS:
            if description.property_key in device_data:
                entities.append(JackerySelectEntity(coordinator, sn, description))

    async_add_entities(entities)
