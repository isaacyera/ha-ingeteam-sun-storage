"""Sensors for the Ingeteam Sun Storage integration."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .catalog import (
    SENSOR_BY_KEY,
    IngeteamEnergyDescription,
    IngeteamSensorDescription,
)
from .const import LOGGER, MAX_INTEGRATION_GAP
from .coordinator import IngeteamConfigEntry
from .entity import IngeteamEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IngeteamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    data = entry.runtime_data
    entities: list[SensorEntity] = [
        IngeteamSensor(entry, description) for description in data.sensors
    ]
    entities.extend(
        IngeteamEnergySensor(entry, description, SENSOR_BY_KEY[description.source])
        for description in data.energy
    )
    async_add_entities(entities)


class IngeteamSensor(IngeteamEntity, SensorEntity):
    """A sensor that decodes some registers."""

    entity_description: IngeteamSensorDescription

    @property
    def native_value(self) -> Any:
        """Return the decoded value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return what a numeric code stands for."""
        if (attrs_fn := self.entity_description.attrs_fn) is None:
            return None
        return attrs_fn(self.coordinator.data)


class IngeteamEnergySensor(IngeteamEntity, RestoreSensor):
    """Energy, worked out from a power sensor by trapezoidal integration.

    The inverter has no energy counters, so the total is kept here and restored
    after a restart. Time the inverter could not be read is not integrated.
    """

    entity_description: IngeteamEnergyDescription

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        entry: IngeteamConfigEntry,
        description: IngeteamEnergyDescription,
        source: IngeteamSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry, description)
        self._source = source
        self._total = Decimal(0)
        self._last_power: Decimal | None = None
        self._last_time: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the running total."""
        await super().async_added_to_hass()

        restored: Decimal | None = None
        if (data := await self.async_get_last_sensor_data()) is not None:
            restored = _to_decimal(data.native_value)
        if restored is None and (state := await self.async_get_last_state()):
            if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                restored = _to_decimal(state.state)

        if restored is None:
            LOGGER.debug("%s: no earlier total to restore, starting at 0", self.entity_id)
            return
        self._total = restored

    @property
    def native_value(self) -> Decimal:
        """Return the energy in kWh."""
        return round(self._total, 2)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Add the energy since the last reading."""
        if not self.coordinator.last_update_success:
            self._last_power = None
            self._last_time = None
            super()._handle_coordinator_update()
            return

        now = dt_util.utcnow()
        power = Decimal(str(self._source.value_fn(self.coordinator.data)))
        if self._last_power is not None and self._last_time is not None:
            elapsed = (now - self._last_time).total_seconds()
            if elapsed <= MAX_INTEGRATION_GAP:
                hours = Decimal(str(elapsed)) / 3600
                self._total += (self._last_power + power) / 2 * hours / 1000
        self._last_power = power
        self._last_time = now
        super()._handle_coordinator_update()


def _to_decimal(value: Any) -> Decimal | None:
    """Return the value as a Decimal, or None if it is not a number."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
