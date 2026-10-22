"""Sensors for the Ingeteam Sun Storage integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IngeteamConfigEntry
from .entity import IngeteamEntity
from .registers import (
    BATTERY_LIMIT_REASON,
    BATTERY_STATUS,
    BMS_ALARM_BITS,
    BMS_FLAG_BITS,
    INVERTER_STATUS,
    POWER_REDUCTION_REASON,
    REACTIVE_SETPOINT_TYPE,
    Register,
    active_bits,
    slug,
)

PARALLEL_UPDATES = 0

NONE_ACTIVE = "None"


@dataclass(frozen=True, kw_only=True)
class IngeteamSensorDescription(SensorEntityDescription):
    """Describes a sensor and the register it reads."""

    register: Register
    states: Mapping[int, str] | None = None
    bits: Mapping[int, str] | None = None
    hex_text: bool = False


def _num(
    key: str,
    name: str,
    register: int,
    *,
    words: int = 1,
    signed: bool = False,
    scale: float = 1.0,
    unit: str | None = None,
    device_class: SensorDeviceClass | None = None,
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    precision: int | None = None,
    diagnostic: bool = False,
    enabled: bool = True,
) -> IngeteamSensorDescription:
    return IngeteamSensorDescription(
        key=key,
        name=name,
        register=Register(register=register, words=words, signed=signed, scale=scale),
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=state_class,
        suggested_display_precision=precision,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
        entity_registry_enabled_default=enabled,
    )


def _enum(
    key: str, name: str, register: int, states: Mapping[int, str]
) -> IngeteamSensorDescription:
    return IngeteamSensorDescription(
        key=key,
        name=name,
        register=Register(register=register),
        device_class=SensorDeviceClass.ENUM,
        options=[slug(label) for label in states.values()],
        translation_key=key,
        states=states,
    )


def _bits(
    key: str, name: str, register: int, bits: Mapping[int, str]
) -> IngeteamSensorDescription:
    return IngeteamSensorDescription(
        key=key,
        name=name,
        register=Register(register=register),
        entity_category=EntityCategory.DIAGNOSTIC,
        bits=bits,
    )


def _hex(key: str, name: str, register: int) -> IngeteamSensorDescription:
    return IngeteamSensorDescription(
        key=key,
        name=name,
        register=Register(register=register),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hex_text=True,
    )


V = UnitOfElectricPotential.VOLT
A = UnitOfElectricCurrent.AMPERE
W = UnitOfPower.WATT
VAR = UnitOfReactivePower.VOLT_AMPERE_REACTIVE
HZ = UnitOfFrequency.HERTZ
C = UnitOfTemperature.CELSIUS
DC = SensorDeviceClass


def _pv(n: int, first: int) -> list[IngeteamSensorDescription]:
    return [
        _num(f"pv{n}_voltage", f"PV{n} voltage", first, unit=V, device_class=DC.VOLTAGE),
        _num(
            f"pv{n}_current",
            f"PV{n} current",
            first + 1,
            scale=0.01,
            unit=A,
            device_class=DC.CURRENT,
            precision=2,
        ),
        _num(f"pv{n}_power", f"PV{n} power", first + 2, unit=W, device_class=DC.POWER),
    ]


def _ac_block(
    prefix: str,
    label: str,
    first: int,
    *,
    freq_scale: float,
    cos_phi: bool,
    enabled: bool = True,
) -> list[IngeteamSensorDescription]:
    """Voltage, current, frequency, P, Q (and cos φ) of one AC measurement."""
    sensors = [
        _num(f"{prefix}_voltage", f"{label} voltage", first, unit=V,
             device_class=DC.VOLTAGE, enabled=enabled),
        _num(f"{prefix}_current", f"{label} current", first + 1, scale=0.01, unit=A,
             device_class=DC.CURRENT, precision=2, enabled=enabled),
        _num(f"{prefix}_frequency", f"{label} frequency", first + 2,
             scale=freq_scale, unit=HZ, device_class=DC.FREQUENCY, precision=2,
             enabled=enabled),
        _num(f"{prefix}_active_power", f"{label} active power", first + 3,
             signed=True, unit=W, device_class=DC.POWER, enabled=enabled),
        _num(f"{prefix}_reactive_power", f"{label} reactive power", first + 4,
             signed=True, unit=VAR, device_class=DC.REACTIVE_POWER, enabled=enabled),
    ]
    if cos_phi:
        sensors.append(
            _num(f"{prefix}_cos_phi", f"{label} cos φ", first + 5, scale=0.001,
                 device_class=DC.POWER_FACTOR, precision=3, enabled=enabled)
        )
    return sensors


SENSORS: tuple[IngeteamSensorDescription, ...] = (
    # --- Status and diagnostics ---------------------------------------------
    _enum("inverter_status", "Status", 30016, INVERTER_STATUS),
    _num("operation_time", "Operation time", 30007, words=2, unit=UnitOfTime.HOURS,
         device_class=DC.DURATION, state_class=SensorStateClass.TOTAL_INCREASING,
         diagnostic=True),
    _num("stop_event", "Stop event code", 30010, state_class=None, diagnostic=True),
    _num("alarms", "Alarm code", 30011, words=2, state_class=None, diagnostic=True),
    _num("alarm_code_1", "Alarm code 1", 30013, state_class=None, diagnostic=True,
         enabled=False),
    _num("alarm_code_2", "Alarm code 2", 30014, state_class=None, diagnostic=True,
         enabled=False),
    _num("alarm_code_3", "Alarm code 3", 30015, state_class=None, diagnostic=True,
         enabled=False),
    _num("waiting_time_to_connect", "Waiting time to connect to grid", 30017,
         unit=UnitOfTime.SECONDS, device_class=DC.DURATION, diagnostic=True),
    # --- Battery --------------------------------------------------------------
    _num("battery_voltage", "Battery voltage", 30018, scale=0.1, unit=V,
         device_class=DC.VOLTAGE, precision=1),
    _num("battery_current", "Battery current", 30019, signed=True, scale=0.01, unit=A,
         device_class=DC.CURRENT, precision=2),
    _num("battery_power", "Battery power", 30020, signed=True, unit=W,
         device_class=DC.POWER),
    _num("battery_soc", "Battery SOC", 30021, unit=PERCENTAGE,
         device_class=DC.BATTERY),
    _num("battery_soh", "Battery SOH", 30022, unit=PERCENTAGE, diagnostic=True),
    _num("battery_charging_voltage", "Battery charging voltage", 30023, scale=0.1,
         unit=V, device_class=DC.VOLTAGE, precision=1, diagnostic=True),
    _num("battery_discharging_voltage", "Battery discharging voltage", 30024,
         scale=0.1, unit=V, device_class=DC.VOLTAGE, precision=1, diagnostic=True),
    _num("battery_max_charge_current", "Battery max charge current", 30025,
         scale=0.01, unit=A, device_class=DC.CURRENT, precision=2, diagnostic=True),
    _num("battery_max_discharge_current", "Battery max discharge current", 30026,
         scale=0.01, unit=A, device_class=DC.CURRENT, precision=2, diagnostic=True),
    _enum("battery_status", "Battery status", 30027, BATTERY_STATUS),
    _num("battery_temperature", "Battery temperature", 30028, signed=True, scale=0.1,
         unit=C, device_class=DC.TEMPERATURE, precision=1),
    _bits("battery_bms_alarms", "Battery BMS alarms", 30029, BMS_ALARM_BITS),
    _enum("battery_discharge_limit_reason", "Battery discharge limitation reason",
          30030, BATTERY_LIMIT_REASON),
    _num("battery_internal_voltage", "Battery internal sensor voltage", 30031,
         scale=0.1, unit=V, device_class=DC.VOLTAGE, precision=1, diagnostic=True,
         enabled=False),
    # --- PV -------------------------------------------------------------------
    *_pv(1, 30032),
    *_pv(2, 30035),
    # --- Inverter output ---------------------------------------------------------
    _num("active_power", "Active power", 30038, signed=True, unit=W,
         device_class=DC.POWER),
    _num("reactive_power", "Reactive power", 30039, signed=True, unit=VAR,
         device_class=DC.REACTIVE_POWER),
    _num("cos_phi", "Cos φ", 30040, scale=0.001, device_class=DC.POWER_FACTOR,
         precision=3),
    _num("power_reduction_ratio", "Active power reduction ratio", 30041, scale=0.1,
         unit=PERCENTAGE, precision=1, diagnostic=True),
    _enum("power_reduction_reason", "Active power reduction reason", 30042,
          POWER_REDUCTION_REASON),
    _enum("reactive_setpoint_type", "Reactive power set-point type", 30043,
          REACTIVE_SETPOINT_TYPE),
    # --- Critical loads and internal grid meter -------------------------------------
    *_ac_block("critical_loads", "Critical loads", 30044, freq_scale=0.01,
               cos_phi=False),
    *_ac_block("grid", "Grid", 30049, freq_scale=0.01, cos_phi=True),
    # --- Internals ---------------------------------------------------------------
    _num("dc_bus_voltage", "DC bus voltage", 30055, unit=V, device_class=DC.VOLTAGE,
         diagnostic=True),
    _num("inverter_temperature", "Inverter temperature", 30058, signed=True,
         scale=0.1, unit=C, device_class=DC.TEMPERATURE, precision=1,
         diagnostic=True),
    _num("positive_isolation_resistance", "Positive isolation resistance", 30060,
         unit="kΩ", diagnostic=True),
    _num("negative_isolation_resistance", "Negative isolation resistance", 30061,
         unit="kΩ", diagnostic=True),
    _num("rms_differential_current", "RMS differential current", 30062, scale=0.1,
         unit=UnitOfElectricCurrent.MILLIAMPERE, device_class=DC.CURRENT,
         precision=1, diagnostic=True),
    # --- Firmware-dependent (30069 and up) ---------------------------------------------
    _bits("battery_bms_flags", "Battery BMS flags", 30069, BMS_FLAG_BITS),
    _num("external_meter_voltage", "External meter voltage", 30070, unit=V,
         device_class=DC.VOLTAGE),
    _num("external_meter_frequency", "External meter frequency", 30071, scale=0.1,
         unit=HZ, device_class=DC.FREQUENCY, precision=1),
    _num("external_meter_active_power", "External meter active power", 30072,
         signed=True, unit=W, device_class=DC.POWER),
    _num("external_meter_reactive_power", "External meter reactive power", 30073,
         signed=True, unit=VAR, device_class=DC.REACTIVE_POWER),
    _hex("battery_bms_warnings", "Battery BMS warnings", 30074),
    _hex("battery_bms_errors", "Battery BMS errors", 30075),
    _hex("battery_bms_faults", "Battery BMS faults", 30076),
    _hex("battery_bms_protections", "Battery BMS protections", 30077),
    _enum("battery_charge_limit_reason", "Battery charge limitation reason", 30078,
          BATTERY_LIMIT_REASON),
    _num("total_loads_power", "Total loads power", 30079, unit=W,
         device_class=DC.POWER),
    _num("external_pv_power", "External PV power", 30080, unit=W,
         device_class=DC.POWER),
    _num("ev_charger_power", "EV charger power", 30081, signed=True, unit=W,
         device_class=DC.POWER),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IngeteamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    chunks = entry.runtime_data.chunks
    async_add_entities(
        IngeteamSensor(entry, description)
        for description in SENSORS
        if description.register.is_covered(chunks)
    )


class IngeteamSensor(IngeteamEntity, SensorEntity):
    """A sensor backed by one value of the register map."""

    entity_description: IngeteamSensorDescription

    def __init__(
        self, entry: IngeteamConfigEntry, description: IngeteamSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry, description, description.register)

    @property
    def native_value(self) -> str | int | float | None:
        """Return the decoded value."""
        description = self.entity_description
        if description.states is not None:
            label = description.states.get(self.raw_value)
            return slug(label) if label else None
        if description.bits is not None:
            return ", ".join(active_bits(self.raw_value, description.bits)) or NONE_ACTIVE
        if description.hex_text:
            return f"0x{self.raw_value:04X}"
        return description.register.decode(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the raw value of the bit fields for use in templates."""
        if self.entity_description.bits is None:
            return None
        return {"raw": self.raw_value}
