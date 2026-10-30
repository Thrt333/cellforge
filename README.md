# Cellforge

Minimal tooling for cellular modules, starting with the DJI first-generation
4G dongle (Baiwang QDC507).

The initial goal is to provide USB cellular internet to a Wi-Fi-only iPad, then
add module-level data usage and upload/download speed monitoring. This is an
independent project and is not affiliated with DJI, Quectel, or any carrier.

## Current status

This repository currently contains documentation and a verified hardware
baseline, plus a narrowly scoped macOS ECM configuration tool. It does not
contain an installer, a module service, a web dashboard or a custom firmware image.

On one QDC507 running `QDC507GLEFM21`, we have verified:

- Changing the existing USB network setting from mode 0 to mode 1 (CDC ECM)
  exposes a USB Ethernet adapter without replacing the factory firmware.
- macOS acquires an IPv4 address, gateway and DNS through DHCP.
- HTTPS access explicitly bound to that adapter succeeds with Wi-Fi disabled.
- The module answers native sent/received-byte counter queries.

These observations apply to the tested device only. iPad compatibility, lock and
wake behavior, power consumption, and long-term stability remain unverified.
See [the hardware baseline](docs/hardware-baseline.md) for the evidence and limits.

## ECM configuration tool

Read the [usage guide](docs/ecm-tool.md) before changing a device.

    python3 scripts/cellforge.py status
    python3 scripts/cellforge.py enable-ecm
    python3 scripts/cellforge.py disable-ecm

The default is read-only. Changes require explicit confirmation, one mode write,
readback and one restart request. Already in the target mode is a no-op.
The tool does not wait for reconnection or verify networking. disable-ecm selects
mode 0 (QMI); it does not turn off cellular service. Run host checks with `make check`.

## Intended use

The iPad connects to the dongle over USB; the dongle connects to the carrier over
LTE. The iPad sees an Ethernet connection rather than gaining native iPadOS
cellular hardware or settings.

Target devices for upcoming validation:

- iPad mini (A17 Pro), commonly called iPad mini 7.
- iPad Pro 12.9-inch (2020).

The iPadOS versions have not yet been recorded.

## Direction

1. Preserve the working factory firmware and CDC ECM connection.
2. Validate both iPads before adding module-side software.
3. Investigate a small read-only module-local dashboard for data usage and
   upload/download rates.
4. Confirm shell access, writable storage, resource limits and recovery before
   deploying any service.
5. Add keepalive behavior only if a reproduced problem demonstrates a need.

The first version excludes SMS, calls, eSIM management and a resident Mac
management application. There is no decision to fork the full DJOneHub platform.

## Development boundaries

- Identify the device and capture its current configuration before changing it.
- Change one setting at a time; read it back and check behavior after restart.
- Keep an accessible control interface and a concrete recovery procedure.
- Treat USB composition, network configuration and counters as shared device
  state; do not run competing management tools.
- Distinguish hardware observations from documentation, inference and plans.
- Do not publish phone numbers, SIM identifiers, activation codes, credentials,
  device dumps or packet captures.
- Keep generated binaries, local logs and backups outside version control.
- Do not expose a future module management service to the cellular WAN.
- Review all staged content before committing to this public repository.

## References

- [DJOneHub](https://github.com/ZenGeekLabs/DJOneHub)
- [DJOneHub mac enhanced](https://github.com/rogerbush007-a11y/DJOneHub-mac-enhanced)
- [Apple: USB-C connections on iPad](https://support.apple.com/en-ie/108894)

The referenced projects are research inputs. Their source and runtime binaries
are not included in this repository.
