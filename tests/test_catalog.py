"""Tests for the entity catalog, using stand-ins for the Home Assistant types."""

import importlib
from pathlib import Path
import re
import sys
import types

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ha_stubs  # noqa: E402

ha_stubs.install()

_PACKAGE = Path(__file__).parent.parent / "custom_components/ingeteam_sun_storage"
_pkg = types.ModuleType("ingeteam_sun_storage")
_pkg.__path__ = [str(_PACKAGE)]
sys.modules["ingeteam_sun_storage"] = _pkg

catalog = importlib.import_module("ingeteam_sun_storage.catalog")
const = importlib.import_module("ingeteam_sun_storage.const")
registers = importlib.import_module("ingeteam_sun_storage.registers")

CORE = {const.GROUP_CORE}
WITH_METER = CORE | {const.GROUP_METER}
WITH_BATTERY = CORE | {const.GROUP_BATTERY}
ALL = CORE | {const.GROUP_METER, const.GROUP_BATTERY}
LAST = registers.FULL_SIZE - 1

# Entities the previous integration had in this installation (meter on, battery
# off), taken from the live entity registry. "Internal Temperature" is listed
# without the "_2" that a leftover entity forced onto it.
OLD_ENTITY_IDS = {
    "active_power", "active_power_reduction_ratio", "active_power_reduction_reason",
    "alarm_code", "critical_loads_active_power", "critical_loads_current",
    "critical_loads_frequency", "critical_loads_reactive_power",
    "critical_loads_voltage", "dc_bus_voltage", "digital_input_2_status",
    "digital_input_3_status", "digital_input_drm0_status", "digital_output_1_status",
    "digital_output_2_status", "ev_power", "external_meter_ac_active_power",
    "external_meter_ac_active_power_returned", "external_meter_ac_frequency",
    "external_meter_ac_reactive_power", "external_meter_ac_voltage",
    "internal_active_power", "internal_meter_current", "internal_meter_frequency",
    "internal_meter_voltage", "internal_power_factor_cosph", "internal_reactive_power",
    "internal_temperature", "power_factor_cosph", "pv1_current", "pv1_power",
    "pv1_voltage", "pv2_current", "pv2_power", "pv2_voltage", "pv_external_power",
    "pv_internal_total_power", "pv_total_power", "reactive_power",
    "reactive_power_set_point_type", "rms_differential_current", "status",
    "stop_event_code", "temperature_module_1", "temperature_module_2",
    "total_loads_power", "waiting_time_to_connect_to_grid", "active_energy",
    "critical_loads_active_energy", "ev_energy", "external_meter_ac_active_energy",
    "external_meter_ac_active_energy_returned", "internal_active_energy",
    "pv1_energy", "pv2_energy", "pv_external_energy", "pv_internal_total_energy",
    "pv_total_energy", "total_loads_energy",
}


def _entity_id(name: str) -> str:
    """The object ID Home Assistant builds from a device name and entity name."""
    text = f"ingeteam {name}".lower().replace("φ", "ph")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_").removeprefix("ingeteam_")


def _selected(groups, last=LAST):
    sensors = catalog.select_sensors(groups, last)
    return sensors, catalog.select_energy(groups, sensors)


def _image(values: dict[int, int]) -> list[int]:
    image = [0] * registers.FULL_SIZE
    for register, value in values.items():
        image[register - registers.FIRST_REGISTER] = value & 0xFFFF
    return image


def _by_key(key: str):
    return catalog.SENSOR_BY_KEY[key]


def test_keys_and_names_are_unique():
    keys = [d.key for d in catalog.SENSORS] + [d.key for d in catalog.ENERGY_SENSORS]
    assert len(keys) == len(set(keys))
    names = [d.name for d in catalog.SENSORS] + [d.name for d in catalog.ENERGY_SENSORS]
    assert len({_entity_id(n) for n in names}) == len(names)


def test_every_old_entity_is_reproduced_when_the_meter_is_on():
    sensors, energy = _selected(WITH_METER)
    ids = {_entity_id(d.name) for d in sensors + energy if d.entity_registry_enabled_default}
    assert OLD_ENTITY_IDS <= ids, sorted(OLD_ENTITY_IDS - ids)


def test_without_meter_or_battery_only_core_entities_exist():
    sensors, energy = _selected(CORE)
    assert {d.group for d in sensors + energy} == {const.GROUP_CORE}
    assert not any(d.key.startswith(("em_", "battery_")) for d in sensors + energy)


def test_meter_option_adds_meter_entities_and_their_energy():
    sensors, energy = _selected(WITH_METER)
    keys = {d.key for d in sensors}
    assert {"em_voltage", "em_freq", "em_active_power", "em_active_power_returned",
            "em_reactive_power"} <= keys
    assert {"em_active_energy", "em_active_energy_returned"} <= {d.key for d in energy}
    assert not any(k.startswith("battery_") for k in keys)


def test_battery_option_adds_battery_entities_and_their_energy():
    sensors, energy = _selected(WITH_BATTERY)
    keys = {d.key for d in sensors}
    assert {"battery_voltage", "battery_state_of_charge", "battery_charging_power",
            "battery_discharging_power", "battery_status"} <= keys
    assert {"battery_charging_energy", "battery_discharging_energy"} <= {
        d.key for d in energy
    }
    assert not any(k.startswith("em_") for k in keys)


def test_old_firmware_gets_no_sensor_that_needs_later_registers():
    sensors, energy = _selected(ALL, registers.BASE_LAST_ADDRESS)
    for description in sensors:
        assert all(span.stop - 1 <= registers.BASE_LAST_ADDRESS for span in description.spans)
    keys = {d.key for d in sensors}
    assert "total_loads_power" not in keys
    assert "pv_total_power" not in keys  # needs the external PV register
    assert "em_voltage" not in keys
    # Energy sensors need their source.
    assert "total_loads_energy" not in {d.key for d in energy}
    assert "pv1_energy" in {d.key for d in energy}


def test_firmware_in_between_serves_what_it_has():
    # Firmware that has the meter registers but not 30078 and up.
    sensors, _ = _selected(ALL, 30077 - registers.FIRST_REGISTER)
    keys = {d.key for d in sensors}
    assert "em_voltage" in keys
    assert "battery_bms_errors" in keys
    assert "battery_charge_limitation_reason" not in keys
    assert "total_loads_power" not in keys


def test_polling_plan_stays_within_ingeteam_limits_and_covers_everything():
    for groups in (CORE, WITH_METER, WITH_BATTERY, ALL):
        sensors, energy = _selected(groups)
        wanted = [d for d in sensors if d.entity_registry_enabled_default]
        spans = [s for d in wanted for s in d.spans]
        chunks = registers.plan_chunks(spans)
        assert all(1 <= count <= registers.MAX_REGISTERS_PER_REQUEST for _, count in chunks)
        assert all(registers.covers(chunks, span) for span in spans)
        assert all(
            registers.covers(chunks, s)
            for d in energy
            for s in _by_key(d.source).spans
        )


def test_switching_off_the_battery_means_fewer_requests():
    def requests(groups):
        sensors, _ = _selected(groups)
        spans = [s for d in sensors if d.entity_registry_enabled_default for s in d.spans]
        return len(registers.plan_chunks(spans))

    # The meter registers fit into requests that are needed anyway.
    assert requests(CORE) <= requests(WITH_METER)
    # The battery block is a separate stretch of registers.
    assert requests(CORE) < requests(WITH_BATTERY)
    assert requests(WITH_METER) <= requests(ALL)
    # Never the whole map: 81 registers would be 9 requests.
    assert requests(ALL) < 9


def test_nothing_uses_units_that_home_assistant_rejects():
    units = {d.native_unit_of_measurement for d in catalog.SENSORS}
    assert "C" not in units
    assert "Var" not in units
    assert "°C" in units
    assert "var" in units


def test_values_match_the_previous_integration():
    image = _image(
        {
            30016: 3,  # status On-grid
            30038: 613,
            30039: -61,
            30040: 995,
            30032: 447, 30033: 142, 30034: 634,
            30035: 40, 30036: 0, 30037: 0,
            30042: 11,  # Self-Consumption Mode
            30063: 0, 30064: 1,
            30056: 278, 30057: 286, 30058: 419,
            30072: -250,  # meter: exporting 250 W
            30080: 100,  # external PV
            30020: -800,  # battery charging 800 W
        }
    )
    v = lambda key: _by_key(key).value_fn(image)  # noqa: E731

    assert v("status") == "On-grid"
    assert v("ap_reduction_reason") == "Self-Consumption Mode"
    assert v("do_1_status") == "Off"
    assert v("do_2_status") == "On"
    assert v("active_power") == 613
    assert v("reactive_power") == -61
    assert v("power_factor") == 0.995
    assert v("pv1_current") == 1.42
    assert (v("temp_mod_1"), v("temp_mod_2"), v("temp_pcb")) == (27.8, 28.6, 41.9)
    assert v("pv_internal_total_power") == 634 + 0
    assert v("pv_total_power") == 634 + 0 + 100
    assert v("em_active_power") == 0
    assert v("em_active_power_returned") == 250
    assert v("battery_charging_power") == 800
    assert v("battery_discharging_power") == 0


def test_pv_internal_total_adds_both_strings():
    image = _image({30034: 634, 30037: 300})
    assert _by_key("pv_internal_total_power").value_fn(image) == 934


def test_unknown_codes_become_unknown_not_errors():
    image = _image({30016: 99, 30042: 99, 30063: 7})
    assert _by_key("status").value_fn(image) is None
    assert _by_key("ap_reduction_reason").value_fn(image) is None
    assert _by_key("do_1_status").value_fn(image) is None


def test_numeric_codes_keep_their_meaning_as_attributes():
    image = _image({30043: 3, 30029: 0b101, 30069: 0b11})
    setpoint = _by_key("reactive_setpoint_type")
    assert setpoint.value_fn(image) == 3
    assert setpoint.attrs_fn(image) == {"description": "Qac vs Vac algorithm"}
    alarm = _by_key("battery_bms_alarm")
    assert alarm.value_fn(image) == 5
    assert alarm.attrs_fn(image) == {"active": ["High charge current", "Low voltage"]}
    assert _by_key("battery_bms_flags").attrs_fn(image) == {
        "active": ["Stop charge", "Stop discharge"]
    }


def test_32_bit_alarm_code_is_low_word_first():
    image = _image({30011: 7, 30012: 0})
    assert _by_key("alarm_code").value_fn(image) == 7


def test_extras_are_off_by_default_and_energy_sources_exist():
    for description in catalog.SENSORS:
        if not description.entity_registry_enabled_default:
            assert description.entity_category is not None
    for description in catalog.ENERGY_SENSORS:
        assert description.source in catalog.SENSOR_BY_KEY
        assert catalog.SENSOR_BY_KEY[description.source].group == description.group or (
            description.group == const.GROUP_CORE
        )


@pytest.mark.parametrize("description", catalog.SENSORS, ids=lambda d: d.key)
def test_every_sensor_decodes_an_empty_image(description):
    # No sensor may raise on whatever the inverter sends, zeros included.
    description.value_fn([0] * registers.FULL_SIZE)
    if description.attrs_fn is not None:
        description.attrs_fn([0] * registers.FULL_SIZE)
