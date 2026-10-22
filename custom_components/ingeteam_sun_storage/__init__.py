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

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import IngeteamConfigEntry, IngeteamCoordinator, IngeteamRuntimeData
from .helpers import NotIngeteamError, async_probe, create_modbus_params

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


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
        chunks = await async_probe(unit)
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

    coordinator = IngeteamCoordinator(hass, entry, unit, chunks)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = IngeteamRuntimeData(coordinator=coordinator, chunks=chunks)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IngeteamConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
