# DeLonghi Dinamica Plus — Home Assistant BLE integration

This component belongs to the public repository [Sepp501/delonghi-dinamica-hacs](https://github.com/Sepp501/delonghi-dinamica-hacs).

Current implementation supports local BLE status, power-on, warnings, statistics, six shared configurable drinks, name changes and readback-verified recipe-value saving on the **ECAM 370.95.T**. It uses a 15-second status poll and a 120-second full refresh, and works with an ESPHome Bluetooth proxy.

**No beverage-start, stop or power-off commands are exposed.** Only one BLE client should access the machine at a time.

For installation, exact capabilities, cautions, source attribution and licensing, read the [repository README](../../README.md), [third-party notices](../../THIRD_PARTY_NOTICES.md), and [Apache-2.0 license](../../LICENSE).
