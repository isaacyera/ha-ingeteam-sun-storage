"""Binary sensors for the Ingeteam Sun Storage integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IngeteamConfigEntry
from .entity import IngeteamEntity
from .registers import Register

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IngeteamBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a binary sensor and the register it reads."""

    register: Register


def _io(key: str, name: str, register: int) -> IngeteamBinarySensorDescription:
    return IngeteamBinarySensorDescription(
        key=key,
        name=name,
        register=Register(register=register),
        entity_category=EntityCategory.DIAGNOSTIC,
    )


BINARY_SENSORS: tuple[IngeteamBinarySensorDescription, ...] = (
    _io("digital_output_1", "Digital output 1", 30063),
    _io("digital_output_2", "Digital output 2", 30064),
    _io("digital_input_drm0", "Digital input DRM0", 30065),
    _io("digital_input_2", "Digital input 2", 30066),
    _io("digital_input_3", "Digital input 3", 30067),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IngeteamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities(
        IngeteamBinarySensor(entry, description) for description in BINARY_SENSORS
    )


class IngeteamBinarySensor(IngeteamEntity, BinarySensorEntity):
    """A binary sensor backed by one register."""

    entity_description: IngeteamBinarySensorDescription

    def __init__(
        self, entry: IngeteamConfigEntry, description: IngeteamBinarySensorDescription
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(entry, description, description.register)

    @property
    def is_on(self) -> bool:
        """Return whether the input or output is on."""
        return bool(self.raw_value)
