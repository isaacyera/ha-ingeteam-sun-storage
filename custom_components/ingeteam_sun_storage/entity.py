"""Base entity for the Ingeteam Sun Storage integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IngeteamConfigEntry, IngeteamCoordinator
from .helpers import unique_id


class IngeteamEntity(CoordinatorEntity[IngeteamCoordinator]):
    """An entity of the inverter.

    The device is named after the entry, and entity IDs are built from that name
    and the entity name, which is how the previous integration named them.
    """

    _attr_has_entity_name = True

    def __init__(
        self, entry: IngeteamConfigEntry, description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data.coordinator)
        self.entity_description = description
        self._attr_unique_id = unique_id(entry.entry_id, description.key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Ingeteam",
            model="INGECON SUN STORAGE 1Play TL M",
            name=entry.title,
        )
