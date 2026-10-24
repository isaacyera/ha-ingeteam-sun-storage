"""Ingeteam INGECON SUN STORAGE 1Play TL M over Modbus TCP.

The connection is not owned here: a unit is borrowed from the core ``modbus``
integration, which shares one connection per device between its users.
"""

from modbus_connection import ModbusError

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import entity_registry as er

from .catalog import SENSOR_BY_KEY, select_energy, select_sensors
from .const import (
    CONF_READ_BATTERY,
    CONF_READ_METER,
    CONF_UNIT_ID,
    DOMAIN,
    GROUP_BATTERY,
    GROUP_CORE,
    GROUP_METER,
)
from .coordinator import IngeteamConfigEntry, IngeteamCoordinator, IngeteamRuntimeData
from .helpers import (
    NotIngeteamError,
    async_probe,
    create_modbus_params,
    flag,
    is_enabled,
)
from .registers import plan_chunks

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IngeteamConfigEntry) -> bool:
    """Set up the inverter from a config entry."""
    try:
        unit = async_get_unit(
            hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT_ID]
        )
    except HomeAssistantError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    try:
        last_address = await async_probe(unit)
    except ModbusError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except NotIngeteamError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="unknown_device"
        ) from err

    groups = {GROUP_CORE}
    if flag(entry, CONF_READ_METER):
        groups.add(GROUP_METER)
    if flag(entry, CONF_READ_BATTERY):
        groups.add(GROUP_BATTERY)

    sensors = select_sensors(groups, last_address)
    energy = select_energy(groups, sensors)

    # Only registers that an enabled entity needs are read, since every request
    # costs a second.
    registry = er.async_get(hass)
    spans = [
        span
        for description in sensors
        if is_enabled(registry, entry.entry_id, description)
        for span in description.spans
    ]
    spans += [
        span
        for description in energy
        if is_enabled(registry, entry.entry_id, description)
        for span in SENSOR_BY_KEY[description.source].spans
    ]

    coordinator = IngeteamCoordinator(hass, entry, unit, plan_chunks(spans))
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = IngeteamRuntimeData(
        coordinator=coordinator, sensors=sensors, energy=energy
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IngeteamConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
