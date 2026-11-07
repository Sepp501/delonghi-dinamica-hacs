# DeLonghi Dinamica Plus — experimental HA integration v0.1

This is a **read-only developer preview**, not a replacement for the working Arbuzov BLE integration.

## Included
- Manual setup by Bluetooth MAC address.
- HA Bluetooth API (including supported Bluetooth proxies), Bleak connection.
- Profile names (0xA4), custom drink names (0xAA), recipes (0xA6).
- 20 sensors: profile count, name count, and 18 coffee-volume sensors with milk seconds and strength as attributes.
- Polling every 120 seconds. No beverage start, no write/change commands beyond read requests.

## Important limits
- **Not live-tested inside HA.** BLE proxy transport and coexistence with the existing integration are unverified.
- Do **not** configure both integrations for the same machine at the same time. Both may compete for a BLE connection. Keep the existing integration installed, but disable its config entry during an agreed test window.
- A failed initial BLE read prevents setup and is retried by HA.
- No status sensors or controls yet; their exact code must be imported/reviewed from the reference integration.
- Names cannot yet be confidently assigned to recipe IDs or profiles.
- Recipe values are presently identical across profiles; profile-specificity is not established.
- Guest profile is not queried.
- The HA device registry and discovery enhancements are planned for later versions.

## Installation (later, during a test window)
Copy `custom_components/delonghi_dinamica` into HA's `/config/custom_components/`, restart HA, add integration 'DeLonghi Dinamica Plus (Development)', enter machine MAC.

## Development
The protocol module is intentionally self-contained. Preserve existing Windows test scripts and your current HA installation. Validate integration first in a test environment if possible.
