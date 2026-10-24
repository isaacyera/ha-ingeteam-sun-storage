# Ingeteam Sun Storage 1Play TL M for Home Assistant

Read-only Home Assistant integration for the **INGECON SUN STORAGE 1Play TL M**
hybrid inverter over Modbus TCP. It is built on Home Assistant's core `modbus`
integration, which shares one connection per device, instead of opening its own
socket.

> **Status:** early version (0.1.0). Read-only; there are no control entities yet.

> [!WARNING]
> **This is a vibe-coded component.** It was written with an AI assistant
> (Claude Code), working from Ingeteam's published register document, and has
> not been reviewed line by line or tested extensively on real hardware. Use it
> at your own risk, check the values against your inverter's own display, and
> report problems in the issue tracker.

## Requirements

- Home Assistant **2026.10.0** or newer (needs the core `modbus` connection layer).
- Modbus TCP enabled on the inverter (inverter web interface: *Comms > Firewall*).

## Installation

### HACS

1. HACS > three-dot menu > **Custom repositories**.
2. Add `https://github.com/isaacyera/ha-ingeteam-sun-storage` with category **Integration**.
3. Download **Ingeteam Sun Storage 1Play TL M** and restart Home Assistant.
4. **Settings > Devices & services > Add integration** and search for *Ingeteam*.

### Manual

Copy `custom_components/ingeteam_sun_storage` into your Home Assistant
`custom_components` folder and restart.

## Configuration

Enter a **name prefix** (default `ingeteam`), the inverter's host, port (default
`502`) and Modbus unit ID (default `1`). The setup checks that the device
answers like an Ingeteam inverter.

The name prefix is the device name, so it becomes the start of every entity ID
(`sensor.ingeteam_active_power`).

Two checkboxes say which optional hardware is installed. Change them later with
the **Configure** button of the integration; it reloads when you save.

| Option | Adds |
| --- | --- |
| *Read meter data* | External meter AC voltage, frequency, active power (import), active power returned (export), reactive power, and their energy sensors. |
| *Read battery data* | Battery voltage, current, charging and discharging power, SOC, SOH, status, temperature, limits, BMS alarm, and the charging and discharging energy sensors. |

Both are off by default. Registers of a part that is switched off are not read.

## Polling and the Ingeteam limits

Ingeteam recommends a single Modbus TCP client on port 502, at least one second
between requests and no more than 10 registers per request. The integration
follows this: only the registers that an enabled entity needs are read, in as
few requests of at most 10 registers as possible, with a one-second spacing.

| Switched on | Requests per refresh |
| --- | --- |
| Defaults | 6 (44 registers) |
| Meter | 6 (55 registers) |
| Battery | 7 (58 registers) |
| Meter and battery | 7 (69 registers) |

A refresh takes about as many seconds as there are requests, plus a 5 second
pause, so values update roughly every 11 to 12 seconds. Disabling an entity you
do not use can reduce the requests further.

**Do not run another client against the inverter at the same time**, including
other Home Assistant integrations or YAML `modbus:` hubs for the same address.

## Entities

Entity names, units and the way values are split follow the earlier
`ingeteam_modbus` integration:

- Status, alarm and the other state sensors report text such as `On-grid`.
- The external meter active power is the imported part and *Active Power
  Returned* the exported part, both positive.
- Battery charging and discharging power are separate positive sensors.
- PV Internal Total, PV Total, and the digital inputs and outputs are sensors.
- Temperatures use `°C` and reactive power uses `var`.

Registers from 30069 up exist only on newer firmware and are detected at setup.
A few extra diagnostics (total operation time, isolation resistance, BMS flags,
warnings and errors) are created disabled.

### Energy sensors

The inverter has no energy counters, so the energy sensors (for example
*Active Energy*, *PV Total Energy*) integrate the matching power sensor with the
trapezoidal rule, in kWh. They keep their total across restarts. Power is not
integrated across a gap longer than 10 minutes or while the inverter cannot be
read.

The register map comes from Ingeteam document ABH2010IMB08, revision I
(23/04/2025). Registers 30056 and 30057 (*Temperature Module 1 and 2*) are
marked reserved there but are read, as the earlier integration did.

## Replacing `ingeteam_modbus`

The entity IDs are the same, so history, dashboards and automations carry over
if the old entities are gone before the new ones are created. Both integrations
cannot run at once, as they would be two clients on the inverter.

1. Make a Home Assistant backup, and note the current value of the energy
   sensors.
2. Delete the **Ingeteam Modbus** integration entry.
3. Add **Ingeteam Sun Storage 1Play TL M** with the same name prefix, and tick
   *Read meter data* if you have the external meter.
4. Check that no entity ended up with a `_2` suffix, and that the energy sensors
   kept their totals.
5. Home Assistant may report changed units for temperature and reactive power
   under **Settings > System > Repairs**. They are the same quantities with the
   correct unit, so choose to update the unit and keep the history.

## Disclaimer

This project is not affiliated with Ingeteam.
