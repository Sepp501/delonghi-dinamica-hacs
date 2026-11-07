# DeLonghi Dinamica Plus – Home Assistant

Custom Home Assistant integration for the DeLonghi Dinamica Plus ECAM370.95.T.

## Status

Development preview (0.1.x). Not yet tested inside Home Assistant.

## Features

- Read user profiles
- Read custom drink names
- Read coffee quantities
- Read milk durations and coffee strength
- Bluetooth communication through Home Assistant
- ESPHome Bluetooth proxy support (testing pending)
- Read-only: no brewing or configuration changes

## Installation via HACS

1. Open HACS in Home Assistant.
2. Add this GitHub repository as a custom repository.
3. Select category "Integration".
4. Download DeLonghi Dinamica Plus.
5. Restart Home Assistant.
6. Add the integration under Settings > Devices & Services.

## Important

Do not run this integration alongside another active Bluetooth
integration controlling the same coffee machine.

The mapping between custom drink names and recipe IDs
is still experimental.

## Supported hardware

- DeLonghi Dinamica Plus ECAM370.95.T
- Home Assistant Bluetooth / ESPHome Bluetooth proxy
