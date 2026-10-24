"""Helpers shared by the config flow and the setup."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import IllegalDataAddressError, ModbusTcpParams, ModbusUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityDescription

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .registers import (
    BASE_LAST_ADDRESS,
    FIRMWARE_STEPS,
    MESSAGE_SPACING,
    MONTH_ADDRESS,
    STATUS_ADDRESS,
    plausible_identity,
)


class NotIngeteamError(Exception):
    """The device answered, but its registers do not look like an inverter's."""


def create_modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def flag(entry: ConfigEntry, key: str) -> bool:
    """Return a switch from the options, falling back to the setup answers."""
    return bool(entry.options.get(key, entry.data.get(key, False)))


def scan_interval(entry: ConfigEntry) -> int:
    """Return the pause between passes, in seconds, within the allowed range."""
    value = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    return max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, int(value)))


def unique_id(entry_id: str, key: str) -> str:
    """Return the unique ID of an entity of an entry."""
    return f"{entry_id}_{key}"


def is_enabled(
    registry: er.EntityRegistry, entry_id: str, description: EntityDescription
) -> bool:
    """Whether the entity is switched on, so its registers are worth reading.

    An entity that is not registered yet is on unless it is disabled by default.
    """
    entity_id = registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, unique_id(entry_id, description.key)
    )
    if entity_id is None or (entity := registry.async_get(entity_id)) is None:
        return description.entity_registry_enabled_default
    return not entity.disabled


async def async_probe(unit: ModbusUnit) -> int:
    """Check that the device is the inverter and what its firmware serves.

    Returns the highest address served. Later firmware added registers in steps
    (see the revision history of the register document), so the last register
    of each step is asked for in turn. Raises a ``ModbusError`` when the device
    cannot be reached and ``NotIngeteamError`` when whatever answers is not this
    inverter.
    """
    unit.set_message_spacing(MESSAGE_SPACING)

    # The clock month and the inverter status sit in the first two requests.
    head: list[int] = []
    for start in (0, 10):
        head += await unit.read_input_registers(start, 10)
    if len(head) < 20 or not plausible_identity(
        head[MONTH_ADDRESS], head[STATUS_ADDRESS]
    ):
        raise NotIngeteamError

    last = BASE_LAST_ADDRESS
    for address in FIRMWARE_STEPS:
        try:
            await unit.read_input_registers(address, 1)
        except IllegalDataAddressError:
            break
        last = address
    return last
