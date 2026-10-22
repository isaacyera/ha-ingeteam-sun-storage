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

Enter the inverter's host, port (default `502`) and Modbus unit ID (default `1`).
The setup checks that the device answers like an Ingeteam inverter.

## Polling and the Ingeteam limits

Ingeteam recommends a single Modbus TCP client on port 502, at least one second
between requests and no more than 10 registers per request. The integration
follows this: it reads the input registers in 9 requests of at most 10
registers with a one-second spacing, so values refresh roughly every 15 seconds.

**Do not run another client against the inverter at the same time**, including
other Home Assistant integrations or YAML `modbus:` hubs for the same address.

## Entities

Sensors for battery (voltage, current, power, SOC, SOH, temperature, status,
limitation reasons, BMS alarms and flags), PV1/PV2, inverter output, critical
loads, the internal grid meter, the external meter, total loads, external PV and
EV charger power, plus diagnostics (status codes, temperatures, isolation
resistance, operation time) and binary sensors for the digital inputs and
outputs. Registers from 30069 up exist only on newer firmware and are detected
at setup.

The register map comes from Ingeteam document ABH2010IMB08, revision I
(23/04/2025). It contains no energy counters (kWh); use an integration helper on
the power sensors if you need them.

## Disclaimer

This project is not affiliated with Ingeteam.
