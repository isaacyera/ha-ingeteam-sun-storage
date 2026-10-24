"""Minimal stand-ins for the few Home Assistant types the catalog imports.

They let the entity catalog be tested without installing Home Assistant. They
only need to behave like the real classes for the fields the catalog sets.
"""

from dataclasses import dataclass
import enum
import sys
import types
from typing import Any


def install() -> None:
    """Register the stand-in modules, unless Home Assistant is really there."""
    if "homeassistant" in sys.modules:
        return

    def module(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    for name in (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.helpers",
    ):
        module(name)
    sensor = module("homeassistant.components.sensor")
    const = module("homeassistant.const")
    typing_ = module("homeassistant.helpers.typing")

    class SensorDeviceClass(enum.StrEnum):
        BATTERY = "battery"
        CURRENT = "current"
        DURATION = "duration"
        ENUM = "enum"
        FREQUENCY = "frequency"
        POWER = "power"
        POWER_FACTOR = "power_factor"
        REACTIVE_POWER = "reactive_power"
        TEMPERATURE = "temperature"
        VOLTAGE = "voltage"

    class SensorStateClass(enum.StrEnum):
        MEASUREMENT = "measurement"
        TOTAL = "total"
        TOTAL_INCREASING = "total_increasing"

    @dataclass(frozen=True, kw_only=True)
    class SensorEntityDescription:
        key: str
        name: Any = None
        icon: str | None = None
        device_class: Any = None
        state_class: Any = None
        options: list[str] | None = None
        native_unit_of_measurement: str | None = None
        entity_category: Any = None
        entity_registry_enabled_default: bool = True

    sensor.SensorDeviceClass = SensorDeviceClass
    sensor.SensorStateClass = SensorStateClass
    sensor.SensorEntityDescription = SensorEntityDescription

    class EntityCategory(enum.StrEnum):
        DIAGNOSTIC = "diagnostic"

    class UnitOfElectricCurrent(enum.StrEnum):
        AMPERE = "A"
        MILLIAMPERE = "mA"

    class UnitOfElectricPotential(enum.StrEnum):
        VOLT = "V"

    class UnitOfFrequency(enum.StrEnum):
        HERTZ = "Hz"

    class UnitOfPower(enum.StrEnum):
        WATT = "W"

    class UnitOfReactivePower(enum.StrEnum):
        VOLT_AMPERE_REACTIVE = "var"

    class UnitOfTemperature(enum.StrEnum):
        CELSIUS = "°C"

    class UnitOfTime(enum.StrEnum):
        HOURS = "h"
        SECONDS = "s"

    const.PERCENTAGE = "%"
    const.EntityCategory = EntityCategory
    const.UnitOfElectricCurrent = UnitOfElectricCurrent
    const.UnitOfElectricPotential = UnitOfElectricPotential
    const.UnitOfFrequency = UnitOfFrequency
    const.UnitOfPower = UnitOfPower
    const.UnitOfReactivePower = UnitOfReactivePower
    const.UnitOfTemperature = UnitOfTemperature
    const.UnitOfTime = UnitOfTime

    typing_.StateType = Any
