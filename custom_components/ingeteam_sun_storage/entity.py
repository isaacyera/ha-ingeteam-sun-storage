"""Base entity for the Ingeteam Sun Storage integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IngeteamConfigEntry, IngeteamCoordinator
from .registers import Register


class IngeteamEntity(CoordinatorEntity[IngeteamCoordinator]):
    """An entity backed by one value of the register map."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: IngeteamConfigEntry,
        description: EntityDescription,
        register: Register,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data.coordinator)
        self.entity_description = description
        self._register = register
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Ingeteam",
            model="INGECON SUN STORAGE 1Play TL M",
            name=entry.title,
        )

    @property
    def raw_value(self) -> int:
        """Return the unscaled register value."""
        return self._register.raw(self.coordinator.data)
