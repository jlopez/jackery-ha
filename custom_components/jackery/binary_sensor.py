"""Binary sensor platform for Jackery integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import JackeryCoordinator
from .entity import JackeryEntity


@dataclass(frozen=True, kw_only=True)
class JackeryBinarySensorEntityDescription(BinarySensorEntityDescription):  # type: ignore[misc]
    """Describes a Jackery binary sensor entity."""

    property_key: str
    is_on_fn: Callable[[object], bool | None]


def _eq_one(raw: object) -> bool | None:
    """Return True when value equals 1."""
    if raw is None:
        return None
    try:
        return bool(int(raw) == 1)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _neq_zero(raw: object) -> bool | None:
    """Return True when value is not zero."""
    if raw is None:
        return None
    try:
        return bool(int(raw) != 0)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


BINARY_SENSOR_DESCRIPTIONS: tuple[JackeryBinarySensorEntityDescription, ...] = (
    JackeryBinarySensorEntityDescription(
        key="wss",
        translation_key="wireless_charging",
        property_key="wss",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=_eq_one,
    ),
    JackeryBinarySensorEntityDescription(
        key="ta",
        translation_key="temperature_alarm",
        property_key="ta",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_neq_zero,
    ),
    JackeryBinarySensorEntityDescription(
        key="pal",
        translation_key="power_alarm",
        property_key="pal",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_neq_zero,
    ),
)


class JackeryBinarySensorEntity(JackeryEntity, BinarySensorEntity):  # type: ignore[misc]
    """Representation of a Jackery binary sensor."""

    entity_description: JackeryBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: JackeryCoordinator,
        device_sn: str,
        description: JackeryBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, device_sn, description)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        raw = self._prop(self.entity_description.property_key)
        if raw is None:
            return None
        return self.entity_description.is_on_fn(raw)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery binary sensor entities from a config entry."""
    coordinator: JackeryCoordinator = entry.runtime_data
    entities: list[JackeryBinarySensorEntity] = []

    for device in coordinator.devices:
        sn = str(device.get("devSn", ""))
        if not sn:
            continue
        device_data = coordinator.data.get(sn, {})
        for description in BINARY_SENSOR_DESCRIPTIONS:
            if description.property_key in device_data:
                entities.append(JackeryBinarySensorEntity(coordinator, sn, description))

    async_add_entities(entities)
