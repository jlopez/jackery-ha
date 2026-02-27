"""Number platform for Jackery integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import JackeryCoordinator
from .entity import JackeryEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class JackeryNumberEntityDescription(NumberEntityDescription):  # type: ignore[misc]
    """Describes a Jackery number entity."""

    property_key: str
    slug: str


NUMBER_DESCRIPTIONS: tuple[JackeryNumberEntityDescription, ...] = (
    JackeryNumberEntityDescription(
        key="ast",
        translation_key="auto_shutdown",
        property_key="ast",
        slug="auto-shutdown",
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=0,
        native_max_value=24,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    JackeryNumberEntityDescription(
        key="pm",
        translation_key="energy_saving",
        property_key="pm",
        slug="energy-saving",
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=0,
        native_max_value=24,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    JackeryNumberEntityDescription(
        key="sltb",
        translation_key="screen_timeout",
        property_key="sltb",
        slug="screen-timeout",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=300,
        native_step=10,
        entity_category=EntityCategory.CONFIG,
    ),
)


class JackeryNumberEntity(JackeryEntity, NumberEntity):  # type: ignore[misc]
    """Representation of a Jackery number."""

    entity_description: JackeryNumberEntityDescription

    def __init__(
        self,
        coordinator: JackeryCoordinator,
        device_sn: str,
        description: JackeryNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, device_sn, description)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        raw = self._prop(self.entity_description.property_key)
        if raw is None:
            return None
        try:
            return float(int(raw))  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value via socketry."""
        coordinator = self.coordinator
        sn = self._device_sn
        slug = self.entity_description.slug
        prop_key = self.entity_description.property_key

        if coordinator.client is None:
            return

        int_value = int(value)
        try:
            device = coordinator.client.device(sn)
            await device.set_property(slug, int_value)
        except (KeyError, ValueError, OSError) as err:
            _LOGGER.error("Failed to set %s=%s for device %s: %s", slug, int_value, sn, err)
            return

        # Optimistic update: immediately reflect the expected state
        if coordinator.data is not None and sn in coordinator.data:
            coordinator.data[sn][prop_key] = int_value
            coordinator.async_set_updated_data(coordinator.data)

        await coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery number entities from a config entry."""
    coordinator: JackeryCoordinator = entry.runtime_data
    entities: list[JackeryNumberEntity] = []

    for device in coordinator.devices:
        sn = str(device.get("devSn", ""))
        if not sn:
            continue
        device_data = coordinator.data.get(sn, {})
        for description in NUMBER_DESCRIPTIONS:
            if description.property_key in device_data:
                entities.append(JackeryNumberEntity(coordinator, sn, description))

    async_add_entities(entities)
