"""What each entity reads, and which option switches it on.

Names, keys, units and the way values are split follow the previous
``ingeteam_modbus`` integration, so that entity IDs and recorded history carry
over. The exceptions are units that Home Assistant does not accept for their
device class (``C``, ``Var``), which are the standard ones here.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.typing import StateType

from .const import GROUP_BATTERY, GROUP_CORE, GROUP_METER
from .registers import (
    BATTERY_LIMIT_REASON,
    BATTERY_STATUS,
    BMS_ALARM_BITS,
    BMS_FLAG_BITS,
    INVERTER_STATUS,
    ON_OFF,
    POWER_REDUCTION_REASON,
    REACTIVE_SETPOINT_TYPE,
    Register,
    active_bits,
)

type Data = Sequence[int]

DC = SensorDeviceClass
MEASUREMENT = SensorStateClass.MEASUREMENT
V = UnitOfElectricPotential.VOLT
A = UnitOfElectricCurrent.AMPERE
W = UnitOfPower.WATT
VAR = UnitOfReactivePower.VOLT_AMPERE_REACTIVE
HZ = UnitOfFrequency.HERTZ
CELSIUS = UnitOfTemperature.CELSIUS


@dataclass(frozen=True, kw_only=True)
class IngeteamSensorDescription(SensorEntityDescription):
    """A sensor, the registers it reads and how it turns them into a state."""

    registers: tuple[Register, ...]
    value_fn: Callable[[Data], StateType]
    attrs_fn: Callable[[Data], dict[str, Any]] | None = None
    group: str = GROUP_CORE

    @property
    def spans(self) -> tuple[range, ...]:
        """Return the addresses this sensor needs, one span per value."""
        return tuple(register.span for register in self.registers)

    def is_served(self, last_address: int) -> bool:
        """Whether the firmware has every register this sensor reads."""
        return all(span.stop - 1 <= last_address for span in self.spans)


@dataclass(frozen=True, kw_only=True)
class IngeteamEnergyDescription(SensorEntityDescription):
    """An energy sensor that integrates one of the power sensors."""

    source: str
    group: str = GROUP_CORE


def _flags(extra: bool) -> dict[str, Any]:
    if not extra:
        return {}
    return {
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    }


def _num(
    key: str,
    name: str,
    register: int,
    *,
    words: int = 1,
    signed: bool = False,
    scale: float = 1.0,
    sign: int = 0,
    unit: str | None = None,
    device_class: SensorDeviceClass | None = None,
    state_class: SensorStateClass | None = MEASUREMENT,
    icon: str | None = None,
    group: str = GROUP_CORE,
    extra: bool = False,
) -> IngeteamSensorDescription:
    reg = Register(register=register, words=words, signed=signed, scale=scale, sign=sign)
    return IngeteamSensorDescription(
        key=key,
        name=name,
        registers=(reg,),
        value_fn=reg.decode,
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=state_class,
        icon=icon,
        group=group,
        **_flags(extra),
    )


def _enum(
    key: str,
    name: str,
    register: int,
    states: Mapping[int, str],
    *,
    group: str = GROUP_CORE,
    extra: bool = False,
) -> IngeteamSensorDescription:
    reg = Register(register=register)
    return IngeteamSensorDescription(
        key=key,
        name=name,
        registers=(reg,),
        value_fn=lambda data: states.get(reg.raw(data)),
        device_class=DC.ENUM,
        options=list(states.values()),
        group=group,
        **_flags(extra),
    )


def _code(
    key: str,
    name: str,
    register: int,
    *,
    words: int = 1,
    labels: Mapping[int, str] | None = None,
    bits: Mapping[int, str] | None = None,
    group: str = GROUP_CORE,
    extra: bool = False,
) -> IngeteamSensorDescription:
    """A numeric code, with what it means as attributes."""
    reg = Register(register=register, words=words)

    attrs_fn: Callable[[Data], dict[str, Any]] | None = None
    if labels is not None:
        attrs_fn = lambda data: {"description": labels.get(reg.raw(data))}  # noqa: E731
    elif bits is not None:
        attrs_fn = lambda data: {"active": active_bits(reg.raw(data), bits)}  # noqa: E731

    return IngeteamSensorDescription(
        key=key,
        name=name,
        registers=(reg,),
        value_fn=reg.decode,
        attrs_fn=attrs_fn,
        state_class=MEASUREMENT,
        group=group,
        **_flags(extra),
    )


def _hex(key: str, name: str, register: int, group: str) -> IngeteamSensorDescription:
    reg = Register(register=register)
    return IngeteamSensorDescription(
        key=key,
        name=name,
        registers=(reg,),
        value_fn=lambda data: f"0x{reg.raw(data):04X}",
        group=group,
        **_flags(True),
    )


def _sum(
    key: str, name: str, sources: Sequence[IngeteamSensorDescription]
) -> IngeteamSensorDescription:
    return IngeteamSensorDescription(
        key=key,
        name=name,
        registers=tuple(reg for source in sources for reg in source.registers),
        value_fn=lambda data: sum(source.value_fn(data) for source in sources),
        native_unit_of_measurement=W,
        device_class=DC.POWER,
        state_class=MEASUREMENT,
    )


def _pv(n: int, first: int) -> list[IngeteamSensorDescription]:
    return [
        _num(f"pv{n}_voltage", f"PV{n} Voltage", first, unit=V, device_class=DC.VOLTAGE),
        _num(f"pv{n}_current", f"PV{n} Current", first + 1, scale=0.01, unit=A,
             device_class=DC.CURRENT, icon="mdi:current-dc"),
        _num(f"pv{n}_power", f"PV{n} Power", first + 2, unit=W, device_class=DC.POWER),
    ]


_PV1 = _pv(1, 30032)
_PV2 = _pv(2, 30035)
_PV_EXTERNAL = _num("external_pv_power", "PV External Power", 30080, unit=W,
                    device_class=DC.POWER)
_PV_INTERNAL_TOTAL = _sum("pv_internal_total_power", "PV Internal Total Power",
                          [_PV1[2], _PV2[2]])
_PV_TOTAL = _sum("pv_total_power", "PV Total Power", [_PV_INTERNAL_TOTAL, _PV_EXTERNAL])

SENSORS: tuple[IngeteamSensorDescription, ...] = (
    # --- Status ---------------------------------------------------------------
    _code("stop_code", "Stop event code", 30010),
    _code("alarm_code", "Alarm code", 30011, words=2),
    _enum("status", "Status", 30016, INVERTER_STATUS),
    _num("waiting_time", "Waiting Time to Connect to Grid", 30017,
         unit=UnitOfTime.SECONDS, device_class=DC.DURATION),
    # --- Inverter output -----------------------------------------------------------
    _num("active_power", "Active Power", 30038, signed=True, unit=W, device_class=DC.POWER),
    _num("reactive_power", "Reactive Power", 30039, signed=True, unit=VAR,
         device_class=DC.REACTIVE_POWER),
    _num("power_factor", "Power factor Cosφ", 30040, signed=True, scale=0.001,
         device_class=DC.POWER_FACTOR),
    _num("ap_reduction_ratio", "Active Power Reduction Ratio", 30041, scale=0.1,
         unit=PERCENTAGE),
    _enum("ap_reduction_reason", "Active Power Reduction Reason", 30042,
          POWER_REDUCTION_REASON),
    _code("reactive_setpoint_type", "Reactive Power Set-Point Type", 30043,
          labels=REACTIVE_SETPOINT_TYPE),
    # --- Critical loads ------------------------------------------------------------
    _num("cl_voltage", "Critical Loads Voltage", 30044, unit=V, device_class=DC.VOLTAGE),
    _num("cl_current", "Critical Loads Current", 30045, scale=0.01, unit=A,
         device_class=DC.CURRENT, icon="mdi:current-ac"),
    _num("cl_freq", "Critical Loads Frequency", 30046, scale=0.01, unit=HZ,
         device_class=DC.FREQUENCY),
    _num("cl_active_power", "Critical Loads Active Power", 30047, signed=True, unit=W,
         device_class=DC.POWER),
    _num("cl_reactive_power", "Critical Loads Reactive Power", 30048, signed=True,
         unit=VAR, device_class=DC.REACTIVE_POWER),
    # --- Internal grid meter ----------------------------------------------------------
    _num("im_voltage", "Internal Meter Voltage", 30049, unit=V, device_class=DC.VOLTAGE),
    _num("im_current", "Internal Meter Current", 30050, scale=0.01, unit=A,
         device_class=DC.CURRENT, icon="mdi:current-ac"),
    _num("im_freq", "Internal Meter Frequency", 30051, scale=0.01, unit=HZ,
         device_class=DC.FREQUENCY),
    _num("im_active_power", "Internal Active Power", 30052, signed=True, unit=W,
         device_class=DC.POWER),
    _num("im_reactive_power", "Internal Reactive Power", 30053, signed=True, unit=VAR,
         device_class=DC.REACTIVE_POWER),
    _num("im_power_factor", "Internal Power Factor Cosφ", 30054, signed=True,
         scale=0.001, device_class=DC.POWER_FACTOR),
    # --- Internals ------------------------------------------------------------------------
    _num("dc_bus_voltage", "DC Bus Voltage", 30055, unit=V, device_class=DC.VOLTAGE),
    _num("temp_mod_1", "Temperature Module 1", 30056, signed=True, scale=0.1,
         unit=CELSIUS, device_class=DC.TEMPERATURE),
    _num("temp_mod_2", "Temperature Module 2", 30057, signed=True, scale=0.1,
         unit=CELSIUS, device_class=DC.TEMPERATURE),
    _num("temp_pcb", "Internal Temperature", 30058, signed=True, scale=0.1,
         unit=CELSIUS, device_class=DC.TEMPERATURE),
    _num("rms_diff_current", "RMS Differential Current", 30062, scale=0.1,
         unit=UnitOfElectricCurrent.MILLIAMPERE, icon="mdi:current-ac"),
    _enum("do_1_status", "Digital Output 1. Status", 30063, ON_OFF),
    _enum("do_2_status", "Digital Output 2. Status", 30064, ON_OFF),
    _enum("di_drm_status", "Digital Input DRM0 Status", 30065, ON_OFF),
    _enum("di_2_status", "Digital Input 2. Status", 30066, ON_OFF),
    _enum("di_3_status", "Digital Input 3. Status", 30067, ON_OFF),
    # --- PV and loads --------------------------------------------------------------------------
    *_PV1,
    *_PV2,
    _PV_EXTERNAL,
    _PV_INTERNAL_TOTAL,
    _PV_TOTAL,
    _num("total_loads_power", "Total Loads Power", 30079, unit=W, device_class=DC.POWER),
    _num("ev_power", "EV Power", 30081, signed=True, unit=W, device_class=DC.POWER),
    # --- Only the previous integration's data, off unless wanted ----------------------------------
    _num("total_operation_time", "Total Operation Time", 30007, words=2,
         unit=UnitOfTime.HOURS, device_class=DC.DURATION,
         state_class=SensorStateClass.TOTAL_INCREASING, extra=True),
    _num("positive_isolation_resistance", "Positive Isolation Resistance", 30060,
         unit="kΩ", extra=True),
    _num("negative_isolation_resistance", "Negative Isolation Resistance", 30061,
         unit="kΩ", extra=True),
    # --- External meter (read_meter) ---------------------------------------------------------------
    _num("em_voltage", "External Meter AC Voltage", 30070, unit=V, device_class=DC.VOLTAGE,
         icon="mdi:sine-wave", group=GROUP_METER),
    _num("em_freq", "External Meter AC Frequency", 30071, scale=0.1, unit=HZ,
         device_class=DC.FREQUENCY, group=GROUP_METER),
    _num("em_active_power", "External Meter AC Active Power", 30072, sign=1, unit=W,
         device_class=DC.POWER, group=GROUP_METER),
    _num("em_active_power_returned", "External Meter AC Active Power Returned", 30072,
         sign=-1, unit=W, device_class=DC.POWER, group=GROUP_METER),
    _num("em_reactive_power", "External Meter AC Reactive Power", 30073, signed=True,
         unit=VAR, device_class=DC.REACTIVE_POWER, group=GROUP_METER),
    # --- Battery (read_battery) ----------------------------------------------------------------------
    _num("battery_voltage", "Battery Voltage", 30018, scale=0.1, unit=V,
         device_class=DC.VOLTAGE, group=GROUP_BATTERY),
    _num("battery_current", "Battery Current", 30019, signed=True, scale=0.01, unit=A,
         device_class=DC.CURRENT, icon="mdi:current-dc", group=GROUP_BATTERY),
    _num("battery_charging_power", "Battery Charging Power", 30020, sign=-1, unit=W,
         device_class=DC.POWER, icon="mdi:battery-charging-100", group=GROUP_BATTERY),
    _num("battery_discharging_power", "Battery Discharging Power", 30020, sign=1,
         unit=W, device_class=DC.POWER, icon="mdi:battery-charging-100",
         group=GROUP_BATTERY),
    _num("battery_state_of_charge", "Battery State of Charge", 30021, unit=PERCENTAGE,
         device_class=DC.BATTERY, icon="mdi:battery-high", group=GROUP_BATTERY),
    _num("battery_state_of_health", "Battery State of Health", 30022, unit=PERCENTAGE,
         group=GROUP_BATTERY),
    _num("battery_charging_voltage", "Battery Charging Voltage", 30023, scale=0.1,
         unit=V, device_class=DC.VOLTAGE, group=GROUP_BATTERY),
    _num("battery_discharging_voltage", "Battery Discharging Voltage", 30024,
         scale=0.1, unit=V, device_class=DC.VOLTAGE, group=GROUP_BATTERY),
    _num("battery_charging_current_max", "Battery Max. Charging Current", 30025,
         scale=0.01, unit=A, device_class=DC.CURRENT, icon="mdi:current-dc",
         group=GROUP_BATTERY),
    _num("battery_discharging_current_max", "Battery Max. Discharging Current", 30026,
         scale=0.01, unit=A, device_class=DC.CURRENT, icon="mdi:current-dc",
         group=GROUP_BATTERY),
    _enum("battery_status", "Battery Status", 30027, BATTERY_STATUS, group=GROUP_BATTERY),
    _num("battery_temp", "Battery Temp", 30028, signed=True, scale=0.1, unit=CELSIUS,
         device_class=DC.TEMPERATURE, group=GROUP_BATTERY),
    _code("battery_bms_alarm", "Battery BMS Alarm", 30029, bits=BMS_ALARM_BITS,
          group=GROUP_BATTERY),
    _enum("battery_discharge_limitation_reason", "Battery Discharge Limitation Reason",
          30030, BATTERY_LIMIT_REASON, group=GROUP_BATTERY),
    _num("battery_voltage_internal", "Battery Voltage Internal Sensor", 30031,
         scale=0.1, unit=V, device_class=DC.VOLTAGE, group=GROUP_BATTERY),
    _code("battery_bms_flags", "Battery BMS Flags", 30069, bits=BMS_FLAG_BITS,
          group=GROUP_BATTERY, extra=True),
    _hex("battery_bms_warnings", "Battery BMS Warnings", 30074, GROUP_BATTERY),
    _hex("battery_bms_errors", "Battery BMS Errors", 30075, GROUP_BATTERY),
    _hex("battery_bms_faults", "Battery BMS Faults", 30076, GROUP_BATTERY),
    _hex("battery_bms_protections", "Battery BMS Protections", 30077, GROUP_BATTERY),
    _enum("battery_charge_limitation_reason", "Battery Charge Limitation Reason", 30078,
          BATTERY_LIMIT_REASON, group=GROUP_BATTERY, extra=True),
)

SENSOR_BY_KEY: dict[str, IngeteamSensorDescription] = {d.key: d for d in SENSORS}


def _energy(
    key: str, name: str, source: str, *, icon: str | None = None, group: str = GROUP_CORE
) -> IngeteamEnergyDescription:
    return IngeteamEnergyDescription(
        key=key, name=name, source=source, icon=icon or "mdi:chart-histogram", group=group
    )


ENERGY_SENSORS: tuple[IngeteamEnergyDescription, ...] = (
    _energy("active_energy", "Active Energy", "active_power"),
    _energy("cl_active_energy", "Critical Loads Active Energy", "cl_active_power"),
    _energy("im_active_energy", "Internal Active Energy", "im_active_power"),
    _energy("pv1_energy", "PV1 Energy", "pv1_power"),
    _energy("pv2_energy", "PV2 Energy", "pv2_power"),
    _energy("external_pv_energy", "PV External Energy", "external_pv_power"),
    _energy("pv_internal_total_energy", "PV Internal Total Energy",
            "pv_internal_total_power"),
    _energy("pv_total_energy", "PV Total Energy", "pv_total_power"),
    _energy("total_loads_energy", "Total Loads Energy", "total_loads_power"),
    _energy("ev_energy", "EV Energy", "ev_power"),
    _energy("em_active_energy", "External Meter AC Active Energy", "em_active_power",
            group=GROUP_METER),
    _energy("em_active_energy_returned", "External Meter AC Active Energy Returned",
            "em_active_power_returned", group=GROUP_METER),
    _energy("battery_charging_energy", "Battery Charging Energy",
            "battery_charging_power", icon="mdi:battery-charging-100",
            group=GROUP_BATTERY),
    _energy("battery_discharging_energy", "Battery Discharging Energy",
            "battery_discharging_power", icon="mdi:battery-charging-100",
            group=GROUP_BATTERY),
)


def select_sensors(
    groups: Collection[str], last_address: int
) -> tuple[IngeteamSensorDescription, ...]:
    """Return the sensors of the switched-on groups the firmware can serve."""
    return tuple(
        d for d in SENSORS if d.group in groups and d.is_served(last_address)
    )


def select_energy(
    groups: Collection[str], sensors: Collection[IngeteamSensorDescription]
) -> tuple[IngeteamEnergyDescription, ...]:
    """Return the energy sensors whose group is on and whose source is served."""
    keys = {d.key for d in sensors}
    return tuple(d for d in ENERGY_SENSORS if d.group in groups and d.source in keys)
