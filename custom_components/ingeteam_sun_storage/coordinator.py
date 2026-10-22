"""Data update coordinator for the Ingeteam Sun Storage integration."""

from collections.abc import Sequence
from dataclasses import dataclass

from modbus_connection import ModbusError, ModbusUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL
from .registers import FULL_SIZE, Chunk

type IngeteamConfigEntry = ConfigEntry[IngeteamRuntimeData]


class IngeteamCoordinator(DataUpdateCoordinator[list[int]]):
    """Reads the input register map one small request at a time.

    The unit paces the requests (see ``MESSAGE_SPACING``), so a full pass takes
    about as many seconds as there are chunks.
    """

    config_entry: IngeteamConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IngeteamConfigEntry,
        unit: ModbusUnit,
        chunks: Sequence[Chunk],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self._unit = unit
        self._chunks = chunks

    async def _async_update_data(self) -> list[int]:
        """Fetch the registers."""
        data = [0] * FULL_SIZE
        for start, count in self._chunks:
            try:
                registers = await self._unit.read_input_registers(start, count)
            except ModbusError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="communication_error",
                    translation_placeholders={"error": str(err)},
                ) from err

            if len(registers) != count:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="short_response",
                    translation_placeholders={
                        "expected": str(count),
                        "received": str(len(registers)),
                    },
                )
            data[start : start + count] = registers
        return data


@dataclass(kw_only=True)
class IngeteamRuntimeData:
    """Runtime data for a config entry."""

    coordinator: IngeteamCoordinator
    chunks: tuple[Chunk, ...]
