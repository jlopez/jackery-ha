[![CI](https://github.com/jlopez/jackery-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/jlopez/jackery-ha/actions/workflows/ci.yml)
![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)

# jackery-ha

Home Assistant custom integration for Jackery power stations, distributed via [HACS](https://hacs.xyz/).

## Features

- **18 sensors** — battery level, power input/output, temperature, voltage, frequency, charge timers, diagnostics
- **3 binary sensors** — wireless charging status, temperature & power alarms
- **8 switches** — AC/DC/USB/car output, AC/DC input, super fast charge, UPS mode
- **3 selects** — light mode, charge speed, battery protection level
- **3 numbers** — auto shutdown timer, energy saving timer, screen timeout
- **Diagnostics** — debug data export with automatic credential redaction

All communication goes through the [socketry](https://pypi.org/project/socketry/) PyPI package — no direct HTTP or MQTT calls.

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Add this repository as a custom repository (Integration type)
3. Search for "Jackery Power Stations" and install
4. Restart Home Assistant

### Manual

Copy the `custom_components/jackery/` directory into your Home Assistant `custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Jackery Power Stations**
3. Enter your Jackery app email and password
4. The integration will discover all devices on your account

## Entities

### Sensors

| Entity | Device Class | Unit | Notes |
|--------|-------------|------|-------|
| Battery | battery | % | |
| Battery temperature | temperature | °C | Scaled ÷10 |
| Battery state | enum | — | idle / charging / discharging |
| Input power | power | W | |
| Output power | power | W | |
| Time to full | duration | h | Scaled ÷10, unknown when 0 |
| Time remaining | duration | h | Scaled ÷10, unknown when 0 |
| AC input power | power | W | |
| Car input power | power | W | |
| AC voltage | voltage | V | Scaled ÷10 |
| AC frequency | frequency | Hz | |
| AC power | power | W | |
| AC power (secondary) | power | W | |
| AC socket power | power | W | |
| Error code | — | — | Diagnostic |
| Power mode battery | — | — | Diagnostic |
| Total temperature | temperature | °C | Diagnostic |
| System status | — | — | Diagnostic |

### Binary Sensors

| Entity | Device Class | Notes |
|--------|-------------|-------|
| Wireless charging | battery_charging | On when active |
| Temperature alarm | problem | Diagnostic |
| Power alarm | problem | Diagnostic |

### Switches

| Entity | Device Class | Notes |
|--------|-------------|-------|
| AC output | outlet | |
| DC output | outlet | |
| USB output | outlet | |
| Car output | outlet | |
| AC input | outlet | |
| DC input | outlet | |
| Super fast charge | — | Config |
| UPS mode | — | Config |

### Selects

| Entity | Options | Notes |
|--------|---------|-------|
| Light mode | off, low, high, sos | |
| Charge speed | fast, mute | Config |
| Battery protection | full, eco | Config |

### Numbers

| Entity | Range | Unit | Notes |
|--------|-------|------|-------|
| Auto shutdown | 0–24 | hours | Config |
| Energy saving | 0–24 | hours | Config |
| Screen timeout | 0–300 | seconds | Config |

## Development

```bash
# Install dependencies
uv sync

# Run checks
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```
