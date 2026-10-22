"""Tests for the register map; they need nothing from Home Assistant."""

import importlib.util
from pathlib import Path
import sys

_PATH = (
    Path(__file__).parent.parent
    / "custom_components/ingeteam_sun_storage/registers.py"
)
_spec = importlib.util.spec_from_file_location("registers", _PATH)
r = importlib.util.module_from_spec(_spec)
sys.modules["registers"] = r
_spec.loader.exec_module(r)


def _image(values: dict[int, int]) -> list[int]:
    """A full register image from {documented register: raw value}."""
    image = [0] * r.FULL_SIZE
    for register, value in values.items():
        image[register - r.FIRST_REGISTER] = value & 0xFFFF
    return image


def test_chunks_respect_ingeteam_request_limit():
    chunks = r.BASE_CHUNKS + r.OPTIONAL_CHUNKS
    assert all(1 <= count <= 10 for _, count in chunks)
    assert len(chunks) == 9


def test_chunks_cover_every_register_exactly_once():
    addresses = [
        a for start, count in r.BASE_CHUNKS + r.OPTIONAL_CHUNKS
        for a in range(start, start + count)
    ]
    assert addresses == list(range(r.FULL_SIZE))


def test_multiword_values_are_not_split_across_requests():
    for first in (30007, 30011):  # operation time, alarms
        reg = r.Register(register=first, words=2)
        assert any(reg.is_covered([chunk]) for chunk in r.BASE_CHUNKS)


def test_optional_registers_are_dropped_with_their_chunk():
    bms_flags = r.Register(register=30069)
    ev_power = r.Register(register=30081)
    assert not bms_flags.is_covered(r.BASE_CHUNKS)
    assert bms_flags.is_covered(r.BASE_CHUNKS + r.OPTIONAL_CHUNKS)
    assert not ev_power.is_covered(r.BASE_CHUNKS + r.OPTIONAL_CHUNKS[:1])


def test_documented_address_offset():
    # "register number 1 ... in the memory address is position 0"
    assert r.Register(register=30001).raw([7]) == 7


def test_decode_matches_values_seen_in_home_assistant():
    image = _image(
        {
            30032: 447,  # PV1 voltage [V]
            30033: 142,  # PV1 current [A x100]
            30034: 634,  # PV1 power [W]
            30038: 613,  # active power [W]
            30040: 995,  # cos φ [x1000]
            30041: 546,  # reduction ratio [% x10]
            30051: 4997,  # internal wattmeter frequency [Hz x100]
            30058: 419,  # inverter temperature [°C x10]
        }
    )
    assert r.Register(register=30032).decode(image) == 447
    assert r.Register(register=30033, scale=0.01).decode(image) == 1.42
    assert r.Register(register=30034).decode(image) == 634
    assert r.Register(register=30038, signed=True).decode(image) == 613
    assert r.Register(register=30040, scale=0.001).decode(image) == 0.995
    assert r.Register(register=30041, scale=0.1).decode(image) == 54.6
    assert r.Register(register=30051, scale=0.01).decode(image) == 49.97
    assert r.Register(register=30058, signed=True, scale=0.1).decode(image) == 41.9


def test_signed_registers_go_negative():
    image = _image({30039: -61, 30020: -1500, 30019: -250})
    assert r.Register(register=30039, signed=True).decode(image) == -61
    assert r.Register(register=30020, signed=True).decode(image) == -1500
    assert r.Register(register=30019, signed=True, scale=0.01).decode(image) == -2.5
    # The same word read as unsigned stays large.
    assert r.Register(register=30039).decode(image) == 65475


def test_32_bit_values_are_high_word_first():
    image = _image({30007: 0x0001, 30008: 0x0002})
    assert r.Register(register=30007, words=2).decode(image) == 0x00010002


def test_enum_labels_are_unique_slugs():
    for states in (
        r.INVERTER_STATUS,
        r.BATTERY_STATUS,
        r.POWER_REDUCTION_REASON,
        r.REACTIVE_SETPOINT_TYPE,
        r.BATTERY_LIMIT_REASON,
    ):
        slugs = [r.slug(label) for label in states.values()]
        assert len(set(slugs)) == len(slugs)
    assert r.slug(r.INVERTER_STATUS[3]) == "on_grid"


def test_active_bits():
    assert r.active_bits(0b101, r.BMS_ALARM_BITS) == ["High charge current", "Low voltage"]
    assert r.active_bits(0, r.BMS_FLAG_BITS) == []


def test_identity_check():
    good = _image({30002: 10, 30016: 3})
    assert r.looks_like_ingeteam(good)
    assert not r.looks_like_ingeteam(_image({30002: 0, 30016: 3}))
    assert not r.looks_like_ingeteam(_image({30002: 10, 30016: 11}))
