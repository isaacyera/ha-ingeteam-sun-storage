"""Data update coordinator for the Ingeteam Sun Storage integration."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
import time

from modbus_connection import ModbusError, ModbusUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .catalog import IngeteamEnergyDescription, IngeteamSensorDescription
from .const import DOMAIN, LOGGER
from .registers import FULL_SIZE, Chunk, pause_after

type IngeteamConfigEntry = ConfigEntry[IngeteamRuntimeData]


class IngeteamCoordinator(DataUpdateCoordinator[list[int]]):
    """Reads the registers that the enabled entities need, in small requests.

    The unit paces the requests (see ``MESSAGE_SPACING``), so a pass takes about
    as many seconds as there are requests.
    """

    config_entry: IngeteamConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IngeteamConfigEntry,
        unit: ModbusUnit,
        chunks: Sequence[Chunk],
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._unit = unit
        self._chunks = chunks
        self._period = scan_interval

    async def _async_update_data(self) -> list[int]:
        """Fetch the registers, then time the pause so the period holds."""
        started = time.monotonic()
        data = await self._async_read()
        self.update_interval = timedelta(
            seconds=pause_after(self._period, time.monotonic() - started)
        )
        return data

    async def _async_read(self) -> list[int]:
        """Read every request, one after the other."""
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
    sensors: tuple[IngeteamSensorDescription, ...]
    energy: tuple[IngeteamEnergyDescription, ...]
    requests: int
