# Third-party research and license notices

This repository is an unofficial community integration for De'Longhi Dinamica Plus machines. It is not sponsored or endorsed by De'Longhi.

## Sources informing the BLE implementation

1. **Arbuzov — home_assistant_delonghi_primadonna**  
   Source: https://github.com/Arbuzov/home_assistant_delonghi_primadonna  
   License: **Apache License 2.0**. Original authors retain their copyright.  
   Relevant research: BLE machine status, power-on command, known alarm/status values, statistics, and GATT connection behavior. Some protocol documentation and command patterns in this project were informed by that earlier implementation. Any portions actually copied/adapted from the Apache-licensed code remain subject to its original license and attribution. A copy of Apache-2.0 is included in `LICENSE`.

2. **Assaf Akiva / asaf5767 — barista**  
   Source: https://github.com/asaf5767/barista  
   License: **MIT** (Copyright © 2026 Assaf Akiva).  
   Relevant research: community BLE protocol interpretation and recipe-command handling. This repository does not claim that Barista's full source, software, or assets are bundled. If an identifiable source-code excerpt is subsequently incorporated, its MIT copyright/license notice must be retained with that use.

3. **Home Assistant, Bleak, bleak-retry-connector, ESPHome**  
   - https://github.com/home-assistant/core
   - https://github.com/hbldh/bleak
   - https://github.com/Bluetooth-Devices/bleak-retry-connector
   - https://github.com/esphome/esphome

   The integration uses Home Assistant and BLE APIs. These are separately maintained libraries/projects, not relicensed by this repository. Consult their own licenses for redistribution of their source.

## Coffee Link protocol investigation

The `0xAB` custom-drink name packet layout, UTF-16BE name format and 20-byte GATT write chunking were investigated by inspecting the publicly available Android Coffee Link application (v4.9.6) and testing against an ECAM 370.95.T. The **proprietary Android application, its DEX files and its code are not included** in this repository. Reverse-engineered protocol observations are documented for interoperability only.

## Copyright and compliance

The project is distributed under Apache-2.0 (see `LICENSE`). That does **not** remove any original copyright or license obligations for incorporated third-party source. This attribution is a provenance summary, **not a line-by-line code-origin audit**. Contributors should preserve original headers and make source-level attribution explicit when directly copying or modifying another project's protected code.

If you identify omitted credits or notice requirements, please open a GitHub issue with the relevant source and file paths.

## Maintainer verification (2026-11-08)

The reviewed public repository is a Home Assistant integration, not a copy of
the upstream applications or of the proprietary Android app. Relevant files:

- `monitor.py`, `statistics.py`, `dinamica_protocol/*`: local BLE packet
  encoders/decoders. Their command fields, status interpretation, CRC and
  counter mapping were informed by Arbuzov's Apache-2.0 project.
- `recipe_save_probe.py`: implementation of the observed `0x83` save-operation
  format. The filtering of non-brewing metadata tags was informed by
  Barista's MIT-licensed protocol research. Barista's application is not bundled.
- `recipe_name_write.py`: locally written encoder for the observed `0xAB`
  format from Coffee Link v4.9.6 interoperability investigation.

This identifies known research sources and implementation files. It does not
certify independent authorship or constitute a complete line-by-line provenance
or legal audit of previous revisions. If verbatim/adapted third-party source
is identified later, its original copyright and applicable license notices
must be retained alongside that code.
