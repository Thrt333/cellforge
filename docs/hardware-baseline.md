# Hardware baseline

Recorded on 2026-10-30. No device serial number or SIM identifier is included.

## Tested module

| Item | Observed value |
| --- | --- |
| Device | DJI first-generation 4G dongle |
| USB manufacturer / product | BAIWANG / Baiwang |
| USB VID:PID | `2ca3:4006` |
| AT model | `QDC507` |
| AT firmware revision | `QDC507GLEFM21` |
| Original USB network mode | `0` |
| Current USB network mode | `1` (CDC ECM) |
| USB composition | `0x2CA3,0x4006,1,1,1,1,1,0,0` |

Read-only USB enumeration before the change showed five vendor-specific
interfaces, with no standard ECM, ADB or audio interface. After changing the
network mode and restarting, macOS recognized a Baiwang Ethernet adapter.

The USB composition, APN and other SIM/network settings were not modified.
No firmware image, voice runtime, keepalive script or management application was
installed. The host used an existing libusb library for temporary USB queries;
no new driver or package was installed.

## Authorized change and verification

The only configuration write was the USB network mode change from 0 to 1,
followed by a module restart. Querying the setting after restart confirmed mode
1; the USB identity and composition remained unchanged.

On the test Mac:

- The new interface was `en7`; this name is host-specific.
- DHCP assigned `192.168.225.29/24`, with gateway and DNS
  `192.168.225.1`. The client address is a lease, not a fixed setting.
- A DNS query directed to the module succeeded.
- An HTTPS request explicitly bound to `en7`, bypassing explicit HTTP proxies,
  reached Apple's connectivity test page with HTTP 200 and successful TLS
  certificate verification.
- Wi-Fi was then confirmed off, and the directed HTTPS request succeeded again.
- macOS automatically selected the module as the default route. Network service
  priorities were not manually changed.

This is bounded connectivity evidence. It is not a throughput benchmark, a
long-term stability test, or a complete audit of VPN and proxy behavior.

## Native data counters

The tested firmware responds to:

- `AT+QGDCNT?`: sent and received byte counters.
- `AT+QAUGDCNT?`: automatic counter-save configuration.
- Corresponding capability queries.

Automatic saving reported `0` (disabled). No counter reset, manual save or
auto-save configuration was issued. Counter continuity across power loss, scope
across data contexts, overflow behavior and agreement with carrier accounting
have not been validated.

A future rate display can calculate byte deltas over elapsed time, but that
implementation does not exist yet. It must handle resets, missing samples and
counter discontinuities.

## Resource observations

A read-only `AT+QCFG="usage/apmem"` query returned:

| Field | Raw value | Approximate interpretation |
| --- | ---: | ---: |
| MemTotal | 43460 | 42.44 MiB |
| MemFree | 2008 | 1.96 MiB |
| MemAvailable | 16008 | 15.63 MiB |

The conversions assume the usual Linux KiB units. These are application-side
memory observations, not a measurement of total physical DRAM, and available
memory changes during operation.

A read-only `AT+QFLDS="UFS"` query returned:

| Field | Bytes | MiB |
| --- | ---: | ---: |
| Free AT file storage | 15867904 | 15.13 |
| Total AT file storage | 16089088 | 15.34 |

This is the AT-exposed user file-storage area, not total NAND capacity. Its
suitability as an executable service location has not been established.

## Recovery boundary

The original network-mode value is known, and the USB AT control interface
remained accessible after the mode change. Restoring mode 0 and restarting is
the intended configuration rollback, but it has not been exercised.

There is no full firmware backup or validated raw-flash recovery procedure for
this device in this project. Do not substitute generic EG25 firmware or an
unverified flashing tool.

## Pending hardware validation

- Record each iPad's iPadOS version.
- Verify enumeration, DHCP, DNS and HTTPS with Wi-Fi off on each iPad.
- Check lock/unlock, reconnect, module power cycles and prolonged operation.
- Observe power supply, battery impact and temperature.
- Determine whether module shell access is available without disrupting ECM.
- Inspect actual writable partitions, permissions, ABI and available commands.
- Define install, startup, stop, uninstall and recovery before deploying a service.

A module-local dashboard and optional keepalive remain proposals, not verified
features.
