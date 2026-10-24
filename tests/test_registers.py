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


def _reg(register: int, **kwargs):
    return r.Register(register=register, **kwargs)


def test_documented_address_offset():
    # "register number 1 ... in the memory address is position 0"
    assert _reg(30001).span == range(0, 1)
    assert _reg(30011, words=2).span == range(10, 12)


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
    assert _reg(30032).decode(image) == 447
    assert _reg(30033, scale=0.01).decode(image) == 1.42
    assert _reg(30034).decode(image) == 634
    assert _reg(30038, signed=True).decode(image) == 613
    assert _reg(30040, signed=True, scale=0.001).decode(image) == 0.995
    assert _reg(30041, scale=0.1).decode(image) == 54.6
    assert _reg(30051, scale=0.01).decode(image) == 49.97
    assert _reg(30058, signed=True, scale=0.1).decode(image) == 41.9


def test_signed_registers_go_negative():
    image = _image({30039: -61, 30019: -250})
    assert _reg(30039, signed=True).decode(image) == -61
    assert _reg(30019, signed=True, scale=0.01).decode(image) == -2.5
    # The same word read as unsigned stays large.
    assert _reg(30039).decode(image) == 65475


def test_32_bit_values_are_low_word_first():
    # Same order as the previous integration, which was run against the hardware.
    image = _image({30011: 0x0001, 30012: 0x0002})
    assert _reg(30011, words=2).decode(image) == 0x00020001


def test_power_is_split_into_positive_and_negative_parts():
    discharging = _reg(30020, sign=1)
    charging = _reg(30020, sign=-1)

    image = _image({30020: 1500})
    assert discharging.decode(image) == 1500
    assert charging.decode(image) == 0

    image = _image({30020: -800})
    assert discharging.decode(image) == 0
    assert charging.decode(image) == 800

    image = _image({30020: 0})
    assert discharging.decode(image) == 0
    assert charging.decode(image) == 0


def test_plan_chunks_respects_the_request_limit():
    spans = [range(a, a + 1) for a in range(r.FULL_SIZE)]
    chunks = r.plan_chunks(spans)
    assert all(1 <= count <= 10 for _, count in chunks)
    assert len(chunks) == 9
    covered = [a for start, count in chunks for a in range(start, start + count)]
    assert covered == list(range(r.FULL_SIZE))


def test_plan_chunks_only_reads_what_is_needed():
    assert r.plan_chunks([]) == ()
    # Battery block 30018..30031 is addresses 17..30.
    battery = [range(a, a + 1) for a in range(17, 31)]
    assert r.plan_chunks(battery) == ((17, 10), (27, 4))
    # Two distant registers do not drag the gap in between along.
    assert r.plan_chunks([range(15, 16), range(70, 71)]) == ((15, 1), (70, 1))
    # Close registers share one request.
    assert r.plan_chunks([range(15, 16), range(17, 18)]) == ((15, 3),)


def test_plan_chunks_never_splits_a_32_bit_value():
    # The second word of 10..11 would fall into the first request's window.
    assert r.plan_chunks([range(1, 2), range(10, 12)]) == ((1, 1), (10, 2))
    # When both words fit they share the request.
    assert r.plan_chunks([range(1, 2), range(9, 11)]) == ((1, 10),)


def test_plan_chunks_handles_duplicates_and_overlaps():
    spans = [range(30, 31), range(30, 31), range(28, 32)]
    assert r.plan_chunks(spans) == ((28, 4),)


def test_covers():
    chunks = ((0, 10), (17, 4))
    assert r.covers(chunks, range(0, 2))
    assert r.covers(chunks, range(17, 21))
    assert not r.covers(chunks, range(9, 11))
    assert not r.covers(chunks, range(21, 22))


def test_firmware_steps_end_at_documented_registers():
    # 30069, 30073, 30077, 30080 and 30081 as protocol addresses.
    assert r.FIRMWARE_STEPS == (68, 72, 76, 79, 80)
    assert r.BASE_LAST_ADDRESS == 67


def test_state_labels_are_the_ones_the_previous_integration_used():
    assert r.INVERTER_STATUS[3] == "On-grid"
    assert r.POWER_REDUCTION_REASON[11] == "Self-Consumption Mode"
    assert r.ON_OFF == {0: "Off", 1: "On"}


def test_active_bits():
    assert r.active_bits(0b101, r.BMS_ALARM_BITS) == ["High charge current", "Low voltage"]
    assert r.active_bits(0, r.BMS_FLAG_BITS) == []


def test_identity_check():
    assert r.plausible_identity(10, 3)
    assert not r.plausible_identity(0, 3)
    assert not r.plausible_identity(13, 3)
    assert not r.plausible_identity(10, 11)
