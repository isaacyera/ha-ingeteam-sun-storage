"""Input register map of the INGECON SUN STORAGE 1Play TL M.

Source: Ingeteam ABH2010IMB08 "Input registers", revision _I (23/04/2025).
The document numbers registers from 30001, which is protocol address 0.
This module has no Home Assistant imports so it can be tested on its own.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import math

FIRST_REGISTER = 30001
# 30001..30068 exist on every firmware; 30069..30081 were added in later ones.
BASE_LAST_ADDRESS = 30068 - FIRST_REGISTER
FULL_SIZE = 30081 - FIRST_REGISTER + 1
# Last register added by each later firmware step: 30069 (_B), 30073 (_D),
# 30077 (_E), 30080 (_G) and 30081 (_H), as protocol addresses.
FIRMWARE_STEPS = (30069 - FIRST_REGISTER, 30073 - FIRST_REGISTER,
                  30077 - FIRST_REGISTER, 30080 - FIRST_REGISTER,
                  30081 - FIRST_REGISTER)

# Ingeteam (manual, "Monitoring by Modbus-TCP"): one client on port 502, at
# least one second between requests, and no more than 10 registers per request.
MAX_REGISTERS_PER_REQUEST = 10
MESSAGE_SPACING = 1.0

type Chunk = tuple[int, int]
"""A read request: protocol start address and register count."""

# Home Assistant treats an update interval of 0 as "do not poll", so a pause is
# always a little above it. The spacing between requests is what keeps the
# inverter from being asked too often, not this.
MIN_PAUSE = 0.1


def minimum_period(request_count: int) -> float:
    """Return the fewest seconds between the starts of two refreshes.

    Each request waits ``MESSAGE_SPACING`` after the one before it, the first
    request of a refresh included, so a refresh of N requests starts no more
    often than every N spacings.
    """
    return request_count * MESSAGE_SPACING


def minimum_scan_interval(request_count: int, lowest: int) -> int:
    """Return the smallest scan interval worth offering, in whole seconds."""
    return max(lowest, math.ceil(minimum_period(request_count)))


def pause_after(period: float, pass_seconds: float) -> float:
    """Return the pause that starts the next refresh ``period`` after this one."""
    return max(period - pass_seconds, MIN_PAUSE)

# Registers with documented ranges, used to recognise the inverter.
MONTH_ADDRESS = 30002 - FIRST_REGISTER
STATUS_ADDRESS = 30016 - FIRST_REGISTER
MAX_STATUS = 10


def plan_chunks(spans: Iterable[range]) -> tuple[Chunk, ...]:
    """Cover the address spans with as few requests as the request limit allows.

    A span is the addresses of one value and is never split across requests.
    Requests only reach as far as the last address that is needed.
    """
    chunks: list[Chunk] = []
    start = end = -1
    for span in sorted(spans, key=lambda s: s.start):
        if start >= 0 and span.stop - 1 - start < MAX_REGISTERS_PER_REQUEST:
            end = max(end, span.stop - 1)
            continue
        if start >= 0:
            chunks.append((start, end - start + 1))
        start, end = span.start, span.stop - 1
    if start >= 0:
        chunks.append((start, end - start + 1))
    return tuple(chunks)


def covers(chunks: Sequence[Chunk], span: range) -> bool:
    """Whether the requests include every address of the span."""
    return all(
        any(start <= address < start + count for start, count in chunks)
        for address in span
    )


def plausible_identity(month: int, status: int) -> bool:
    """Cheap identity check: the clock month and inverter status are in range."""
    return 1 <= month <= 12 and status <= MAX_STATUS


@dataclass(frozen=True, kw_only=True)
class Register:
    """One value in the input register space."""

    register: int
    words: int = 1
    signed: bool = False
    scale: float = 1.0
    # +1 keeps only the positive part of the value, -1 only the negative part
    # as a positive number. 0 keeps the value as it is.
    sign: int = 0

    @property
    def span(self) -> range:
        """Return the protocol addresses of every word."""
        first = self.register - FIRST_REGISTER
        return range(first, first + self.words)

    def raw(self, registers: Sequence[int]) -> int:
        """Return the unscaled integer. Multi-word values are low word first."""
        value = 0
        for index, word in enumerate(registers[self.span.start : self.span.stop]):
            value |= word << (16 * index)
        bits = 16 * self.words
        if (self.signed or self.sign) and value >= 1 << (bits - 1):
            value -= 1 << bits
        return value

    def decode(self, registers: Sequence[int]) -> int | float:
        """Return the scaled value."""
        value = self.raw(registers)
        if self.sign:
            value = max(0, self.sign * value)
        if self.scale == 1:
            return value
        return round(value * self.scale, 3)


def active_bits(value: int, bits: Mapping[int, str]) -> list[str]:
    """Return the labels of the bits that are set."""
    return [label for bit, label in bits.items() if value >> bit & 1]


# Entity states. They are the strings the previous integration used, so
# automations and templates that compare them keep working.
ON_OFF: dict[int, str] = {0: "Off", 1: "On"}

INVERTER_STATUS: dict[int, str] = {
    0: "Inverter Stopped",
    1: "Starting",
    2: "Off-grid",
    3: "On-grid",
    4: "On-grid (Standby Battery)",
    5: "Waiting to connect to Grid",
    6: "Critical Loads Bypassed to Grid",
    7: "Emergency Charge from PV",
    8: "Emergency Charge from Grid",
    9: "Inverter Locked waiting for Reset",
    10: "Error Mode",
}

BATTERY_STATUS: dict[int, str] = {
    0: "Standby",
    1: "Discharging",
    2: "Constant Current Charging",
    3: "Constant Voltage Charging",
    4: "Floating",
    5: "Equalizing",
    6: "Error Communication with BMS",
    7: "No Configured",
    8: "Capacity Calibration (Step 1)",
    9: "Capacity Calibration (Step 2)",
    10: "Standby Manual",
}

POWER_REDUCTION_REASON: dict[int, str] = {
    0: "No limitation",
    1: "Communication",
    2: "PCB Temperature",
    3: "Heat Sink Temperature",
    4: "Pac vs Fac Algorithm",
    5: "Soft Start",
    6: "Charge Power Configured",
    7: "PV Surplus injected to the Loads",
    8: "Pac vs Vac Algorithm",
    9: "Battery Power Limited",
    10: "AC Grid Power Limited",
    11: "Self-Consumption Mode",
    12: "High Bus Voltage Protection",
    13: "LVRT or HVRT Process",
    14: "Nominal AC Current",
    15: "Grid Consumption Protection",
    16: "PV Surplus Injected to the Grid",
}

BATTERY_LIMIT_REASON: dict[int, str] = {
    0: "No limitation",
    1: "Heat Sink Temperature",
    2: "PT100 Temperature",
    3: "Low Bus Voltage Protection",
    4: "Battery Settings",
    5: "BMS Communication",
    6: "SOC Max Configured",
    7: "SOC Min Configured",
    8: "Maximum Battery Power",
    9: "Modbus command",
    10: "Digital Input 2",
    11: "Digital Input 3",
    12: "PV Charging scheduling",
    13: "EMS Strategy",
}

# Shown as an attribute next to the numeric code the previous integration used.
REACTIVE_SETPOINT_TYPE: dict[int, str] = {
    0: "Cos(φ) configuration",
    1: "Qac communication",
    2: "Cos(φ) communication",
    3: "Qac vs Vac algorithm",
    4: "Cos(φ) vs Pac algorithm",
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
