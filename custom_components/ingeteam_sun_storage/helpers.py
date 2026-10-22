"""Helpers shared by the config flow and the setup."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import IllegalDataAddressError, ModbusTcpParams, ModbusUnit

from homeassistant.const import CONF_HOST, CONF_PORT

from .registers import (
    BASE_CHUNKS,
    MESSAGE_SPACING,
    OPTIONAL_CHUNKS,
    Chunk,
    looks_like_ingeteam,
)


class NotIngeteamError(Exception):
    """The device answered, but its registers do not look like an inverter's."""


def create_modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


async def async_probe(unit: ModbusUnit) -> tuple[Chunk, ...]:
    """Check the device and return the read requests this firmware serves.

    Raises a ``ModbusError`` when the device cannot be reached and
    ``NotIngeteamError`` when whatever answers is not this inverter.
    """
    unit.set_message_spacing(MESSAGE_SPACING)

    # The clock month and the inverter status sit in the first two requests.
    head: list[int] = []
    for start, count in BASE_CHUNKS[:2]:
        head += await unit.read_input_registers(start, count)
    if len(head) < 20 or not looks_like_ingeteam(head):
        raise NotIngeteamError

    # Older firmware refuses reads past the base map, so ask for each extra
    # request in turn and keep the ones it answers.
    supported = list(BASE_CHUNKS)
    for chunk in OPTIONAL_CHUNKS:
        try:
            await unit.read_input_registers(*chunk)
        except IllegalDataAddressError:
            continue
        supported.append(chunk)
    return tuple(supported)
