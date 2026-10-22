"""Input register map of the INGECON SUN STORAGE 1Play TL M.

Source: Ingeteam ABH2010IMB08 "Input registers", revision _I (23/04/2025).
The document numbers registers from 30001, which is protocol address 0.
This module has no Home Assistant imports so it can be tested on its own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re

FIRST_REGISTER = 30001
# 30001..30068 exist on every firmware; 30069..30081 were added in later ones
# (_B and up) and are probed at setup.
BASE_LAST_REGISTER = 30068
FULL_LAST_REGISTER = 30081
FULL_SIZE = FULL_LAST_REGISTER - FIRST_REGISTER + 1

# Ingeteam (manual, "Monitoring by Modbus-TCP"): one client on port 502, at
# least one second between requests, and no more than 10 registers per request.
MAX_REGISTERS_PER_REQUEST = 10
MESSAGE_SPACING = 1.0

type Chunk = tuple[int, int]
"""A read request: protocol start address and register count."""


def _split(first_address: int, last_address: int) -> tuple[Chunk, ...]:
    """Cut an address range into requests of at most the allowed size."""
    return tuple(
        (start, min(MAX_REGISTERS_PER_REQUEST, last_address - start + 1))
        for start in range(first_address, last_address + 1, MAX_REGISTERS_PER_REQUEST)
    )


BASE_CHUNKS = _split(0, BASE_LAST_REGISTER - FIRST_REGISTER)
OPTIONAL_CHUNKS = _split(
    BASE_LAST_REGISTER - FIRST_REGISTER + 1, FULL_LAST_REGISTER - FIRST_REGISTER
)

# Documented ranges that a real inverter must respect.
STATUS_REGISTER = 30016
MONTH_REGISTER = 30002
MAX_STATUS = 10


def slug(label: str) -> str:
    """Turn a label into a translation key."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


@dataclass(frozen=True, kw_only=True)
class Register:
    """One value in the input register space."""

    register: int
    words: int = 1
    signed: bool = False
    scale: float = 1.0

    def is_covered(self, chunks: Sequence[Chunk]) -> bool:
        """Whether the chunks that get read include every word of the value."""
        first = self.register - FIRST_REGISTER
        return all(
            any(start <= address < start + count for start, count in chunks)
            for address in range(first, first + self.words)
        )

    def raw(self, registers: Sequence[int]) -> int:
        """Return the unscaled integer. Multi-word values are high word first."""
        offset = self.register - FIRST_REGISTER
        value = 0
        for word in registers[offset : offset + self.words]:
            value = (value << 16) | word
        bits = 16 * self.words
        if self.signed and value >= 1 << (bits - 1):
            value -= 1 << bits
        return value

    def decode(self, registers: Sequence[int]) -> int | float:
        """Return the scaled value."""
        value = self.raw(registers)
        if self.scale == 1:
            return value
        return round(value * self.scale, 3)


def active_bits(value: int, bits: Mapping[int, str]) -> list[str]:
    """Return the labels of the bits that are set."""
    return [label for bit, label in bits.items() if value >> bit & 1]


def looks_like_ingeteam(registers: Sequence[int]) -> bool:
    """Cheap identity check: the clock month and inverter status are in range."""
    month = registers[MONTH_REGISTER - FIRST_REGISTER]
    status = registers[STATUS_REGISTER - FIRST_REGISTER]
    return 1 <= month <= 12 and status <= MAX_STATUS


# Labels are the single source for the entity state translations.
INVERTER_STATUS: dict[int, str] = {
    0: "Stopped",
    1: "Starting",
    2: "Off-grid",
    3: "On-grid",
    4: "On-grid (battery standby)",
    5: "Waiting to connect to grid",
    6: "Critical loads bypassed to grid",
    7: "Emergency charge from PV",
    8: "Emergency charge from grid",
    9: "Locked, waiting for reset",
    10: "Error",
}

BATTERY_STATUS: dict[int, str] = {
    0: "Standby",
    1: "Discharging",
    2: "Constant current charging",
    3: "Constant voltage charging",
    4: "Floating",
    5: "Equalizing",
    6: "BMS communication error",
    7: "Not configured",
    8: "Capacity calibration (step 1)",
    9: "Capacity calibration (step 2)",
    10: "Standby (manual)",
}

POWER_REDUCTION_REASON: dict[int, str] = {
    0: "No limitation",
    1: "Communication",
    2: "PCB temperature",
    3: "Heat sink temperature",
    4: "Pac vs Fac algorithm",
    5: "Soft start",
    6: "Charge power configured",
    7: "PV surplus injected to loads",
    8: "Pac vs Vac algorithm",
    9: "Battery power limited",
    10: "AC grid power limited",
    11: "Self-consumption mode",
    12: "High bus voltage protection",
    13: "LVRT or HVRT process",
    14: "Nominal AC current",
    15: "Grid consumption protection",
    16: "PV surplus injected to grid",
}

REACTIVE_SETPOINT_TYPE: dict[int, str] = {
    0: "Cos(φ) configuration",
    1: "Qac communication",
    2: "Cos(φ) communication",
    3: "Qac vs Vac algorithm",
    4: "Cos(φ) vs Pac algorithm",
}

BATTERY_LIMIT_REASON: dict[int, str] = {
    0: "No limitation",
    1: "Heat sink temperature",
    2: "PT100 temperature",
    3: "Low bus voltage protection",
    4: "Battery settings",
    5: "BMS communication",
    6: "SOC max configured",
    7: "SOC min configured",
    8: "Maximum battery power",
    9: "Modbus command",
    10: "Digital input 2",
    11: "Digital input 3",
    12: "PV charging scheduling",
    13: "EMS strategy",
}

BMS_ALARM_BITS: dict[int, str] = {
    0: "High charge current",
    1: "High voltage",
    2: "Low voltage",
    3: "High temperature",
    4: "Low temperature",
    5: "BMS internal",
    6: "Cell imbalance",
    7: "High discharge current",
    8: "System BMS error",
}

BMS_FLAG_BITS: dict[int, str] = {
    0: "Stop charge",
    1: "Stop discharge",
    2: "Forced charge (BMS)",
    3: "Calibration",
    4: "Forced charge (SOC)",
}
